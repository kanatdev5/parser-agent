import asyncio
from datetime import datetime

import httpx
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from config import API_ID, API_HASH, PHONE, SESSION_STRING, GROUPS, BOT_TOKEN, CHAT_ID, BACKEND_REFRESH_TOKEN_EXPIRES, BACKEND_URL, BACKEND_PHONE
from utils import load_seen, save_seen, make_hash, strip_tg_mentions, extract_contact, as_bool
from filters import is_job_offer, has_enough_data
from parser import parse_vacancy_safe, postprocess_vacancy, finalize
from backend import post_to_backend, delete_from_backend, reauth_via_code, set_reauth_callback
from telegram_sender import send_to_telegram
from notify import notify_admin_error

if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient("session", API_ID, API_HASH)


async def _notify_token_expiry():
    if not BACKEND_REFRESH_TOKEN_EXPIRES:
        return
    try:
        expires = datetime.strptime(BACKEND_REFRESH_TOKEN_EXPIRES, "%Y-%m-%d")
        days_left = (expires - datetime.now()).days
        if days_left <= 3:
            async with httpx.AsyncClient() as http:
                await http.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": CHAT_ID,
                        "text": (
                            f"⚠️ BACKEND_REFRESH_TOKEN истекает через {days_left} дн!\n"
                            "Запустите get_backend_auth.py локально и обновите "
                            "BACKEND_REFRESH_TOKEN + BACKEND_REFRESH_TOKEN_EXPIRES на Railway."
                        ),
                    },
                )
            print(f"⚠ Напоминание об истечении токена отправлено ({days_left} дн)")
    except Exception as e:
        print(f"✗ Ошибка проверки токена: {e}")


async def token_expiry_loop():
    while True:
        await asyncio.sleep(24 * 3600)
        await _notify_token_expiry()

seen_hashes: set = load_seen()

# Ожидание WhatsApp кода от админа при переавторизации
_reauth_future: asyncio.Future | None = None


async def _send_admin(text: str):
    async with httpx.AsyncClient(timeout=10) as http:
        await http.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text},
        )


async def _reauth_callback() -> str | None:
    global _reauth_future
    await _send_admin(
        "⚠️ Refresh token истёк!\n"
        f"Код отправлен на WhatsApp {BACKEND_PHONE}.\n"
        "Ответьте: reauth XXXX"
    )
    async with httpx.AsyncClient(timeout=10) as http:
        await http.post(
            f"{BACKEND_URL}/auth/login",
            json={"phoneNumber": BACKEND_PHONE},
        )
    loop = asyncio.get_event_loop()
    _reauth_future = loop.create_future()
    try:
        token = await asyncio.wait_for(_reauth_future, timeout=300)
        return token
    except asyncio.TimeoutError:
        await _send_admin("❌ Код не получен в течение 5 минут. Переавторизация отменена.")
        return None
    finally:
        _reauth_future = None


set_reauth_callback(_reauth_callback)


@client.on(events.NewMessage(incoming=True, from_users=[int(CHAT_ID)]))
async def handle_admin_command(event):
    global _reauth_future
    text = (event.message.text or "").strip()

    # reauth XXXX — передать WhatsApp код
    if text.lower().startswith("reauth "):
        code = text.split(maxsplit=1)[1].strip()
        try:
            token = await reauth_via_code(code)
            if _reauth_future and not _reauth_future.done():
                _reauth_future.set_result(token)
            await event.reply("✅ Переавторизация успешна!")
        except Exception as e:
            await event.reply(f"❌ Ошибка: {e}")
        return

    # delete 42 55 78 — удалить вакансии
    if text.lower().startswith("delete "):
        parts = text.split()[1:]
        ids = [int(p) for p in parts if p.isdigit()]
        if not ids:
            await event.reply("❌ Укажите ID: delete 42")
            return
        results = []
        for vid in ids:
            try:
                res = await delete_from_backend(vid)
                results.append(res)
            except Exception as e:
                results.append(f"❌ #{vid}: {e}")
        await event.reply("\n".join(results))
        return

    # help
    if text.lower() in ("help", "помощь", "/help"):
        await event.reply(
            "Команды:\n"
            "delete 42 — удалить вакансию #42\n"
            "delete 42 55 78 — удалить несколько\n"
            "reauth XXXX — ввести WhatsApp код при переавторизации"
        )


@client.on(events.NewMessage(chats=GROUPS))
async def handle_new_message(event):
    text = event.message.text
    if not text:
        return

    clean = strip_tg_mentions(text)
    contact = extract_contact(clean)

    print(f"\n📨 Сообщение: {clean[:50]}...")

    if not is_job_offer(clean):
        print("🗑 Спам / услуги / зарубеж / поиск работы / реклама группы — пропускаем")
        return

    if not has_enough_data(clean):
        print("⚠ Непонятно кого ищут или нет контакта — пропускаем")
        return

    print("✓ Вакансия — парсим...")

    try:
        parsed = parse_vacancy_safe(clean)

        if not as_bool(parsed.get("is_real_job"), default=True):
            print("🗑 Непонятная работа / не предложение работы (GPT) — пропускаем")
            return

        if not as_bool(parsed.get("has_enough_info"), default=True):
            print("🗑 Мало информации о вакансии (только должность + номер) — пропускаем")
            return

        parsed = postprocess_vacancy(clean, parsed, contact)
        final = finalize(parsed)

        if not final["position"]:
            print("🗑 Не удалось определить должность — пропускаем")
            return

        VAGUE_POSITIONS = {"сотрудник", "работник", "разнорабочий", "помощник"}
        if final["position"].lower() in VAGUE_POSITIONS:
            print(f"🗑 Размытая должность без конкретики ({final['position']}) — пропускаем")
            return

        if not final["company_description"]:
            final["company_description"] = contact

        if not final["company_description"]:
            print("⚠ Нет контакта — пропускаем")
            return

        vacancy_hash = make_hash(clean)

        if vacancy_hash in seen_hashes:
            print(f"🔁 Дубль — {final['position']}")
            return

        seen_hashes.add(vacancy_hash)
        save_seen(seen_hashes)

        print(f"📋 {final['position']} [{final['category']}]")

        await send_to_telegram(text, final)
        print("📤 Отправлено в ТГ!")

        await post_to_backend(final)

    except Exception as e:
        print(f"✗ Ошибка: {e}")
        await notify_admin_error(f"Ошибка обработки вакансии:\n{e}", exc=e)


async def _reply_bot(chat_id, text: str, reply_to_message_id: int = None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    async with httpx.AsyncClient(timeout=10) as http:
        await http.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json=payload,
        )


async def _handle_bot_message(text: str, chat_id, message_id: int):
    global _reauth_future

    if text.lower().startswith("reauth "):
        code = text.split(maxsplit=1)[1].strip()
        try:
            token = await reauth_via_code(code)
            if _reauth_future and not _reauth_future.done():
                _reauth_future.set_result(token)
            await _reply_bot(chat_id, "✅ Переавторизация успешна!", message_id)
        except Exception as e:
            await _reply_bot(chat_id, f"❌ Ошибка: {e}", message_id)
        return

    if text.lower().startswith("delete "):
        parts = text.split()[1:]
        ids = [int(p) for p in parts if p.isdigit()]
        if not ids:
            await _reply_bot(chat_id, "❌ Укажите ID: delete 42", message_id)
            return
        results = []
        for vid in ids:
            try:
                res = await delete_from_backend(vid)
                results.append(res)
            except Exception as e:
                results.append(f"❌ #{vid}: {e}")
        await _reply_bot(chat_id, "\n".join(results), message_id)
        return

    if text.lower() in ("help", "помощь", "/help", "/start"):
        await _reply_bot(
            chat_id,
            "Команды:\n"
            "delete 42 — удалить вакансию #42\n"
            "delete 42 55 78 — удалить несколько\n"
            "reauth XXXX — ввести WhatsApp код при переавторизации",
            message_id,
        )


async def bot_polling_loop():
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠ BOT_TOKEN или CHAT_ID не заданы — bot polling отключён")
        return
    offset = 0
    print("🤖 Bot polling запущен")
    while True:
        try:
            async with httpx.AsyncClient(timeout=30) as http:
                r = await http.get(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                    params={"offset": offset, "timeout": 20, "allowed_updates": ["message"]},
                )
            if r.status_code != 200:
                await asyncio.sleep(3)
                continue
            for update in r.json().get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message") or {}
                if not msg:
                    continue
                from_id = str(msg.get("from", {}).get("id", ""))
                if from_id != str(CHAT_ID):
                    continue
                text = (msg.get("text") or "").strip()
                if not text:
                    continue
                await _handle_bot_message(text, msg["chat"]["id"], msg["message_id"])
        except asyncio.CancelledError:
            return
        except Exception as e:
            print(f"✗ bot polling: {e}")
            await asyncio.sleep(5)


async def main():
    if SESSION_STRING:
        await client.start()
    else:
        await client.start(phone=PHONE)
    print("✓ Подключено")
    print(f"Слушаем: {', '.join(GROUPS)}")
    await _notify_token_expiry()
    asyncio.create_task(token_expiry_loop())
    asyncio.create_task(bot_polling_loop())
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
