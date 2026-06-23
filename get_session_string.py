"""
Запустите этот скрипт ОДИН РАЗ локально чтобы получить SESSION_STRING.
Полученную строку добавьте как переменную окружения на Railway.
"""
import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")


async def main():
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    if not await client.is_user_authorized():
        await client.send_code_request(PHONE)
        code = input("Введите код из Telegram: ").strip()
        await client.sign_in(PHONE, code)
    session_string = client.session.save()
    await client.disconnect()
    print("\n" + "=" * 60)
    print("SESSION_STRING:")
    print(session_string)
    print("=" * 60)
    print("\nСкопируйте строку выше и добавьте в .env как SESSION_STRING=...")

    from dotenv import set_key
    set_key(".env", "SESSION_STRING", session_string)
    print("✓ SESSION_STRING автоматически сохранён в .env")


asyncio.run(main())
