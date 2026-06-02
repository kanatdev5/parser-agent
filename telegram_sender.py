import json

import httpx

from config import BOT_TOKEN, CHAT_ID


async def send_to_telegram(original: str, vacancy: dict):
    pretty_json = json.dumps(vacancy, ensure_ascii=False, indent=2)
    message = f"""✅ Найдена вакансия!

{pretty_json}

Оригинал:
{original[:600]}"""

    async with httpx.AsyncClient() as http:
        await http.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message}
        )
