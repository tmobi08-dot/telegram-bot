from telethon import TelegramClient, events
import os
import logging

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))  # تأكد أنه int إذا كان معرف رقمي

client = TelegramClient("session_name", API_ID, API_HASH)

async def send_message(text):
    try:
        await client.send_message(TELEGRAM_CHAT_ID, text, parse_mode="md", link_preview=False)
    except Exception as e:
        logging.error(f"خطأ في إرسال الرسالة: {e}")

def start_channel_monitor(handler_func):
    @client.on(events.NewMessage(chats=CHANNEL_USERNAME))
    async def handler(event):
        await handler_func(event)