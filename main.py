
import asyncio
from playwright.async_api import async_playwright
import os
import time
import requests
from threading import Thread
from flask import Flask, request

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
PORT = int(os.getenv("PORT", 10000))
CHECK_INTERVAL_SECONDS = 60

# Bot control state
is_running = False
last_status = "Not started"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Telegram send error:", e)

async def check_appointment(playwright):
    global last_status
    browser = await playwright.chromium.launch(headless=True, slow_mo=200)
    context = await browser.new_context()
    page = await context.new_page()

    try:
        await page.goto("https://www.ecsc-expat.sy/login", timeout=60000)
        await page.wait_for_selector('input[name="email"]', timeout=60000)
        await page.fill('input[name="email"]', EMAIL)
        await page.fill('input[name="password"]', PASSWORD)
        await page.click('button:has-text("تسجيل الدخول")')
        await page.wait_for_timeout(5000)

        while is_running:
            try:
                await page.goto("https://www.ecsc-expat.sy/appointments/create", timeout=60000)
                await page.wait_for_timeout(3000)

                await page.select_option('select[name="embassy_id"]', label="بعثة الرياض")
                await page.wait_for_timeout(1000)
                await page.select_option('select[name="service_id"]', label="اصدار أو تجديد جواز سفر (مستعجل)")
                await page.wait_for_timeout(2000)

                content = await page.content()
                if "لا يوجد حجز متاح" in content:
                    print("No appointments available now.")
                    last_status = "No appointments (last checked: " + time.strftime('%H:%M:%S') + ")"
                else:
                    send_telegram("📢 Appointment available! Attempting to book...")
                    try:
                        await page.click('input[name="appointment_date"]')
                        await page.wait_for_timeout(1000)
                        await page.click('button:has-text("حفظ وتثبيت")')
                        send_telegram("✅ Appointment booked successfully!")
                        break
                    except Exception as e:
                        send_telegram("❌ Failed to book the appointment!")
                        print(str(e))
                        last_status = "Failed to book"
            except Exception as inner:
                print("Inner error:", str(inner))
                last_status = f"Error: {str(inner)}"

            await asyncio.sleep(CHECK_INTERVAL_SECONDS)

    except Exception as e:
        print("Fatal error:", str(e))
        send_telegram(f"❌ Bot crashed:\n{str(e)}")
        last_status = "Bot crashed"

    finally:
        await browser.close()

def run_checker():
    asyncio.run(start_checker())

async def start_checker():
    global is_running
    if is_running:
        return
    is_running = True
    async with async_playwright() as playwright:
        await check_appointment(playwright)
    is_running = False

app = Flask(__name__)

@app.route(f"/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    global is_running, last_status
    data = request.json

    if not data or "message" not in data:
        return "ok"

    chat_id = str(data["message"]["chat"]["id"])
    text = data["message"].get("text", "")

    if chat_id != TELEGRAM_CHAT_ID:
        return "unauthorized"

    if text == "/start":
        if not is_running:
            Thread(target=run_checker).start()
            send_telegram("🔄 Bot started checking.")
        else:
            send_telegram("🔄 Bot is already running.")
    elif text == "/stop":
        is_running = False
        send_telegram("⛔ Bot stopped.")
    elif text == "/status":
        send_telegram(f"📊 Bot status: {'Running' if is_running else 'Stopped'}\n{last_status}")
    elif text == "/check":
        Thread(target=run_checker).start()
        send_telegram("🔍 Manual check started.")

    return "ok"

def set_webhook():
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/{TELEGRAM_BOT_TOKEN}"
    try:
        res = requests.post(url, data={"url": webhook_url})
        print("Webhook set:", res.text)
    except Exception as e:
        print("Failed to set webhook:", e)

if __name__ == "__main__":
    set_webhook()
    app.run(host="0.0.0.0", port=PORT)
