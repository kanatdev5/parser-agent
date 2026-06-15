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
    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        await client.start(phone=PHONE)
        session_string = client.session.save()
        print("\n" + "=" * 60)
        print("SESSION_STRING:")
        print(session_string)
        print("=" * 60)
        print("\nСкопируйте строку выше и добавьте в Railway как переменную SESSION_STRING")


asyncio.run(main())
