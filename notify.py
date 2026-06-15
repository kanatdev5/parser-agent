import traceback

import httpx

from config import BOT_TOKEN, ADMIN_CHAT_ID


async def notify_admin_error(message: str, exc: Exception = None):
    if not BOT_TOKEN or not ADMIN_CHAT_ID:
        return
    text = f"🚨 Ошибка бота:\n{message}"
    if exc:
        tb = traceback.format_exc()
        if tb and tb.strip() != "NoneType: None":
            text += f"\n\n```\n{tb[-800:]}\n```"
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            await http.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": ADMIN_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            )
    except Exception:
        pass
