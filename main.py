import asyncio

from telethon import TelegramClient, events
from telethon.sessions import StringSession

from config import API_ID, API_HASH, PHONE, SESSION_STRING, GROUPS
from utils import load_seen, save_seen, make_hash, strip_tg_mentions, extract_contact, as_bool
from filters import is_job_offer, has_enough_data
from parser import parse_vacancy_safe, postprocess_vacancy, finalize
from backend import post_to_backend
from telegram_sender import send_to_telegram

if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient("session", API_ID, API_HASH)

seen_hashes: set = load_seen()


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

        parsed = postprocess_vacancy(clean, parsed, contact)
        final = finalize(parsed)

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


async def main():
    if SESSION_STRING:
        await client.start()
    else:
        await client.start(phone=PHONE)
    print("✓ Подключено")
    print(f"Слушаем: {', '.join(GROUPS)}")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
