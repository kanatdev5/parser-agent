"""
Удалить вакансию с сайта по ID.
Использование:
    python delete_vacancy.py 42
    python delete_vacancy.py 42 55 78
"""
import asyncio
import sys
import os

import httpx
from dotenv import load_dotenv, set_key

load_dotenv(override=True)

BACKEND_URL = os.getenv("BACKEND_URL", "").rstrip("/")
BACKEND_PHONE = os.getenv("BACKEND_PHONE", "")
ENV_FILE = ".env"


async def get_token(http) -> str:
    refresh = os.getenv("BACKEND_REFRESH_TOKEN", "")
    if refresh:
        r = await http.post(f"{BACKEND_URL}/auth/refresh", cookies={"refresh_token": refresh})
        if r.status_code in (200, 201):
            new_refresh = r.cookies.get("refresh_token")
            if new_refresh:
                set_key(ENV_FILE, "BACKEND_REFRESH_TOKEN", new_refresh)
            return r.json()["access_token"]

    print("Refresh token истёк — отправляю код на WhatsApp...")
    r = await http.post(f"{BACKEND_URL}/auth/login", json={"phoneNumber": BACKEND_PHONE})
    if not r.is_success:
        raise RuntimeError(f"Ошибка отправки кода: {r.status_code}")
    print(f"Код отправлен на {BACKEND_PHONE}. Введите код:")
    code = input("Код: ").strip()

    r = await http.post(f"{BACKEND_URL}/auth/confirm-phone", json={"phoneNumber": BACKEND_PHONE, "code": code})
    r.raise_for_status()
    token = r.json().get("access_token", "")
    new_refresh = r.cookies.get("refresh_token", "")
    if new_refresh:
        set_key(ENV_FILE, "BACKEND_REFRESH_TOKEN", new_refresh)
        print("Новый токен сохранён.")
    return token


async def delete_vacancies(ids: list[int]):
    async with httpx.AsyncClient(timeout=15) as http:
        token = await get_token(http)
        for vid in ids:
            r = await http.delete(
                f"{BACKEND_URL}/vacancy/{vid}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if r.status_code in (200, 204):
                print(f"OK — вакансия #{vid} удалена")
            elif r.status_code == 404:
                print(f"НЕ НАЙДЕНА — вакансия #{vid}")
            elif r.status_code == 403:
                print(f"НЕТ ДОСТУПА — вакансия #{vid}")
            else:
                print(f"ERROR {r.status_code} — вакансия #{vid}: {r.text[:100]}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Укажите ID вакансии: python delete_vacancy.py 42")
        print("Или несколько:       python delete_vacancy.py 42 55 78")
        sys.exit(1)

    ids = [int(x) for x in sys.argv[1:]]
    asyncio.run(delete_vacancies(ids))
