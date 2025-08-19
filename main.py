import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

# تحميل متغيرات البيئة أولًا
load_dotenv()
from news_fetcher import (
    get_all_news_async,
    rewrite_with_gemini,
    is_arabic,
    translate_to_ar
)
from forex_prices import fetch_forex_prices, fetch_oil_price, fetch_silver_price
from telegram_bot import send_message, client, start_channel_monitor
from scheduler import schedule_task, start_scheduler
from googletrans import Translator

logging.basicConfig(level=logging.INFO)

sent_news_ids = set()
SHARE_MESSAGE = "إذا استفدت من هذا المحتوى شاركه لتعم الفائدة https://t.me/majd_iforex"

translator = Translator()

async def send_forex_prices(event_text):
    """دالة إرسال أسعار العملات مع الذهب والفضة والنفط"""
    prices = fetch_forex_prices()
    oil_price = fetch_oil_price()
    silver_price = fetch_silver_price()

    # إضافة أسعار النفط والفضة إلى القاموس
    prices["نفط برنت"] = oil_price
    prices["XAG/USD"] = silver_price

    today = datetime.utcnow().weekday()  # 0=Monday, 5=Saturday, 6=Sunday

    # التحقق من أن هناك على الأقل سعر واحد صحيح
    if not any(v is not None for v in prices.values()):
        logging.error("فشل في جلب أي أسعار. لا توجد بيانات متاحة للإرسال.")
        error_msg = f"⚠️ فشل في جلب أسعار العملات والسلع.\n\n_{SHARE_MESSAGE}_"
        await send_message(error_msg)
        return

    lines = []
    for p, v in prices.items():
        if v is not None:
            if p == "XAU/USD":
                p_name = "الذهب"
            elif p == "XAG/USD":
                p_name = "الفضة"
            elif p == "نفط برنت":
                p_name = "النفط"
            else:
                p_name = p
            # تنسيق السعر بناءً على الزوج
            lines.append(f"*{p_name}:* {v:.4f} USD" if "/" in p else f"*{p_name}:* {v:.2f} USD")
    
    # رسالة العطلة مع آخر الأسعار
    if today == 5 or today == 6:
        msg = (
            f"الأسواق المالية مغلقة اليوم (عطلة نهاية الأسبوع).\n"
            f"آخر أسعار الإغلاق:\n"
            f"{'—'*20}\n"
            f"{'\n'.join(lines)}\n"
            f"{'—'*20}\n"
            f"_{SHARE_MESSAGE}_"
        )
    else: # رسالة العمل
        msg = (
            f"💰 {event_text} - أسعار العملات والسلع الحالية:\n"
            f"{'—'*20}\n"
            f"{'\n'.join(lines)}\n"
            f"{'—'*20}\n"
            f"_{SHARE_MESSAGE}_"
        )

    await send_message(msg)
    logging.info(f"✅ أسعار {event_text} أرسلت بنجاح.")

# ---------- دالة إرسال الأخبار بعد تلخيصها وترجمتها ----------
async def send_news():
    logging.info("بدء جلب الأخبار...")
    news_items = await get_all_news_async()

    if not news_items:
        logging.info("لا توجد أخبار جديدة متاحة.")
        return

    for item in news_items:
        news_id = item.get("link", "")
        if news_id in sent_news_ids:
            continue

        title = item.get("title", "")
        summary = item.get("summary", "")
        link = item.get("link", "")

        if not title:
            continue

        # إذا أردت استخدام إعادة الصياغة والترجمة مباشرة من news_fetcher:
        if not is_arabic(title):
            translated_title = translate_to_ar(title)
        else:
            translated_title = title

        if not is_arabic(summary):
            translated_summary = translate_to_ar(summary)
        else:
            translated_summary = summary

        # إعادة الصياغة النهائية
        rewritten = await rewrite_with_gemini(f"{translated_title}\n{translated_summary}")

        msg = (
            f"📰 *خبر عاجل:*\n"
            f"{rewritten}\n\n"
            f"[قراءة الخبر كاملاً]({link})\n\n"
            f"_{SHARE_MESSAGE}_"
        )
        await send_message(msg)
        sent_news_ids.add(news_id)
        await asyncio.sleep(5)  # تأخير لإرسال الخبر التالي
    logging.info("✅ الأخبار أرسلت.")

# ---------- دالة إعادة نشر رسائل قناة أخرى بنفس التذييل ----------
async def relay_channel_message(event):
    text = event.text
    if not text:
        return

    LINK_TO_REMOVE = "https://t.me/fx_news_34"  # عدل هذا إذا تغير الرابط الثابت مستقبلاً

    lines = text.strip().split('\n')
    # إذا كان آخر سطر هو الرابط الثابت
    if len(lines) >= 2 and lines[-1].strip() == LINK_TO_REMOVE:
        # احذف الرابط والسطر الذي قبله (عادة التذييل القديم)
        cleaned_text = '\n'.join(lines[:-2]).strip()
    else:
        cleaned_text = text.strip()

    # أضف التذييل الخاص بك فقط
    msg = f"{cleaned_text}\n\n_{SHARE_MESSAGE}_"
    await send_message(msg)

# ---------- جدولة المهام بالأوقات العالمية ----------
async def main():
    # بدء عميل Telethon أولاً لضمان الاتصال
    await client.start()

    # أوقات افتتاح/إغلاق الأسواق (بتوقيت UTC)
    schedule_task(lambda: send_forex_prices("افتتاح السوق الآسيوي"), trigger="cron", hour=23, minute=0, timezone="UTC")
    schedule_task(lambda: send_forex_prices("إغلاق السوق الآسيوي"), trigger="cron", hour=8, minute=0, timezone="UTC")
    schedule_task(lambda: send_forex_prices("افتتاح السوق الأوروبي"), trigger="cron", hour=7, minute=0, timezone="UTC")
    schedule_task(lambda: send_forex_prices("إغلاق السوق الأوروبي"), trigger="cron", hour=16, minute=0, timezone="UTC")
    schedule_task(lambda: send_forex_prices("افتتاح السوق الأمريكي"), trigger="cron", hour=13, minute=0, timezone="UTC")
    schedule_task(lambda: send_forex_prices("إغلاق السوق الأمريكي"), trigger="cron", hour=20, minute=0, timezone="UTC")

    # جدولة مهمة إرسال الأخبار كل 15 دقيقة
    schedule_task(send_news, trigger="interval", minutes=15)

    start_scheduler()
    start_channel_monitor(relay_channel_message)
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
