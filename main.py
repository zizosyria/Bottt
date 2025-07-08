
import asyncio
from playwright.async_api import async_playwright
import os
import time
import requests

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CHECK_INTERVAL_SECONDS = 60

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Telegram send error:", e)

async def check_appointment(playwright):
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()

    try:
        await page.goto("https://www.ecsc-expat.sy/login")
        await page.fill('input[name="email"]', EMAIL)
        await page.fill('input[name="password"]', PASSWORD)
        await page.click('button:has-text("تسجيل الدخول")')
        await page.wait_for_timeout(3000)

        while True:
            try:
                await page.goto("https://www.ecsc-expat.sy/appointments/create")
                await page.wait_for_timeout(3000)

                await page.select_option('select[name="embassy_id"]', label="بعثة الرياض")
                await page.wait_for_timeout(1000)
                await page.select_option('select[name="service_id"]', label="اصدار أو تجديد جواز سفر (مستعجل)")
                await page.wait_for_timeout(2000)

                content = await page.content()
                if "لا يوجد حجز متاح" in content:
                    print("No appointments available now.")
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

            except Exception as inner:
                print("Inner error:", str(inner))

            await asyncio.sleep(CHECK_INTERVAL_SECONDS)

    except Exception as e:
        print("Fatal error:", str(e))
        send_telegram(f"❌ Bot crashed:\n{str(e)}")

    finally:
        await browser.close()

async def main():
    async with async_playwright() as playwright:
        await check_appointment(playwright)

if __name__ == "__main__":
    asyncio.run(main())
