"""
Запустите этот скрипт ОДИН РАЗ локально чтобы получить refresh_token.
Полученные значения добавьте как переменные окружения на Railway.
"""
import asyncio
import os
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv, set_key

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "").rstrip("/")
BACKEND_PHONE = os.getenv("BACKEND_PHONE", "")
ENV_FILE = ".env"


async def main():
    if not BACKEND_URL or not BACKEND_PHONE:
        print("✗ Заполните BACKEND_URL и BACKEND_PHONE в .env")
        return

    async with httpx.AsyncClient() as http:
        print(f"Запрашиваем код для {BACKEND_PHONE}...")
        r1 = await http.post(f"{BACKEND_URL}/auth/login",
                             json={"phoneNumber": BACKEND_PHONE})
        if not r1.is_success:
            print(f"✗ Ошибка {r1.status_code}: {r1.text[:1000]}")
            return
        r1.raise_for_status()
        print("✓ Код отправлен на WhatsApp")

        code = input("Введите код из WhatsApp: ").strip()

        r2 = await http.post(f"{BACKEND_URL}/auth/confirm-phone",
                             json={"phoneNumber": BACKEND_PHONE, "code": code})
        r2.raise_for_status()

        refresh_token = r2.cookies.get("refresh_token")
        if not refresh_token:
            # некоторые бэкенды возвращают токен в теле
            refresh_token = r2.json().get("refresh_token", "")

        if not refresh_token:
            print("✗ refresh_token не найден ни в cookie, ни в теле ответа")
            print("Headers:", dict(r2.headers))
            print("Body:", r2.text[:500])
            return

        expires = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        set_key(ENV_FILE, "BACKEND_REFRESH_TOKEN", refresh_token)
        set_key(ENV_FILE, "BACKEND_REFRESH_TOKEN_EXPIRES", expires)

        print("\n" + "=" * 60)
        print("Сохранено в .env и Railway нужно добавить вручную:")
        print(f"BACKEND_REFRESH_TOKEN={refresh_token}")
        print(f"BACKEND_REFRESH_TOKEN_EXPIRES={expires}")
        print("=" * 60)
        print(f"\n✓ Готово! Токен истекает {expires}")
        print("Бот пришлёт напоминание за 3 дня до истечения.")


asyncio.run(main())
