import re
import time

import httpx

from config import BACKEND_URL, BACKEND_PHONE, CATEGORIES, SCHEDULE_ENUM
from utils import jwt_exp

_ROTATION_RE = re.compile(r'\d+/\d+')

_token_cache = {"token": None, "exp": 0}


def to_backend_schedule(text: str) -> str:
    t = (text or "").lower()
    if not t:
        return "Не указано"
    if "гибк" in t:
        return "Гибкий график"
    if any(k in t for k in ["смен", "2/2", "1/2", "сутки", "вахт", "ночн", "ноч", "21:0", "12 час"]):
        return "Сменный график"
    if any(k in t for k in ["неполн", "подработ", "пол дня", "4 час", "половин", "part"]):
        return "Неполный день"
    return "Не указано"


def to_backend_period(period: str) -> str:
    p = (period or "").lower()
    if "час" in p:
        return "Час"
    if "смен" in p or "день" in p or "недел" in p:
        return "Смена"
    if "месяц" in p or "оклад" in p:
        return "Месяц"
    return "Договорная"


def build_backend_payload(final: dict) -> dict:
    schedule_raw = (final.get("work_schedule") or "").strip()
    schedule_enum = to_backend_schedule(schedule_raw)

    description = (final.get("description") or "").strip()
    extras = []
    if schedule_raw and schedule_raw not in SCHEDULE_ENUM and schedule_raw.lower() not in description.lower():
        rotation = _ROTATION_RE.search(schedule_raw)
        schedule_label = rotation.group(0) if rotation else schedule_raw
        extras.append(f"График: {schedule_label}")
    if (final.get("payment_period") or "") == "В неделю":
        extras.append("Оплата раз в неделю")
    if extras:
        joined = "; ".join(extras)
        description = f"{description}. {joined}".strip(". ").strip() if description else joined
    if not description:
        description = final.get("position") or "Вакансия"

    experience = (final.get("experience_work") or "").strip() or "Не указан"
    category = final.get("category") if final.get("category") in CATEGORIES else "other"

    salary = int(final.get("salary_net") or 0)
    if salary < 0:
        salary = 0

    return {
        "position": final.get("position") or "Сотрудник",
        "company": final.get("company") or "Частный работодатель",
        "description": description,
        "city": final.get("city") or "Бишкек",
        "region": final.get("region") or "",
        "work_address": final.get("work_address") or "",
        "work_schedule": schedule_enum,
        "experience_work": experience,
        "remote_work": bool(final.get("remote_work", False)),
        "payment_period": to_backend_period(final.get("payment_period")),
        "salary_net": salary,
        "category": category,
        "requirements": final.get("requirements") or "",
        "conditions": final.get("conditions") or "",
        "company_description": final.get("company_description") or "",
    }


async def get_backend_token(http) -> str:
    now = time.time()
    if _token_cache["token"] and _token_cache["exp"] - 60 > now:
        return _token_cache["token"]

    r1 = await http.post(f"{BACKEND_URL}/auth/login",
                         json={"phoneNumber": BACKEND_PHONE})
    r1.raise_for_status()
    sms_code = r1.json().get("smsCode")
    if not sms_code:
        raise RuntimeError("Бэкенд не вернул smsCode — похоже это не dev-режим, логин нужно делать вручную")

    r2 = await http.post(f"{BACKEND_URL}/auth/confirm-phone",
                         json={"phoneNumber": BACKEND_PHONE, "code": str(sms_code)})
    r2.raise_for_status()
    token = r2.json().get("access_token")
    if not token:
        raise RuntimeError("Бэкенд не вернул access_token")

    _token_cache["token"] = token
    _token_cache["exp"] = jwt_exp(token) or (now + 3600)
    print("🔑 Залогинились в бэкенд")
    return token


async def post_to_backend(final: dict):
    if not BACKEND_URL or not BACKEND_PHONE:
        print("ℹ Бэкенд не настроен (BACKEND_URL/BACKEND_PHONE) — на сайт не отправляем")
        return

    payload = build_backend_payload(final)

    async with httpx.AsyncClient(timeout=20) as http:
        try:
            token = await get_backend_token(http)
            r = await http.post(f"{BACKEND_URL}/vacancy",
                                headers={"Authorization": f"Bearer {token}"},
                                json=payload)

            if r.status_code == 401:
                _token_cache["token"] = None
                token = await get_backend_token(http)
                r = await http.post(f"{BACKEND_URL}/vacancy",
                                    headers={"Authorization": f"Bearer {token}"},
                                    json=payload)

            if r.status_code in (200, 201):
                note = " (зарплата договорная)" if payload["salary_net"] == 0 else ""
                print(f"🌐 Отправлено на сайт!{note}")
            else:
                try:
                    detail = r.json().get("message", "")
                except Exception:
                    detail = r.text[:200]
                print(f"✗ Бэкенд {r.status_code}: {detail}")

        except Exception as e:
            print(f"✗ Ошибка отправки на бэкенд: {e}")
