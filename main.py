import asyncio
import os
import json
import hashlib
import re
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from openai import OpenAI
import httpx

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")
SESSION_STRING = os.getenv("SESSION_STRING", "")
GROUPS = ["@Jumush_BishkekKg", "@bishkek_jumush"]
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DEFAULT_USER_ID = 1

ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
else:
    client = TelegramClient("session", API_ID, API_HASH)

SEEN_FILE = "seen_vacancies.json"

CATEGORIES = [
    "it", "trade", "sales", "construction", "transport", "food",
    "education", "beauty", "services", "manufacturing", "security",
    "medicine", "finance", "legal", "marketing", "admin",
    "agriculture", "hospitality", "domestic", "management",
    "customer_support", "warehouse", "cleaning", "other"
]

def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def make_hash(contact: str, position: str) -> str:
    key = f"{contact}_{position}".lower().strip()
    return hashlib.md5(key.encode()).hexdigest()

seen_hashes: set = load_seen()

def strip_json_block(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return raw

# РАБОЧИЙ 2а — это вообще легальная постоянная вакансия?
def is_job_offer(text: str) -> bool:
    response = ai.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": f"""Это объявление от РАБОТОДАТЕЛЯ который ищет СОТРУДНИКА на ПОСТОЯННУЮ работу в Кыргызстане?

Отвечай НЕТ если хоть одно верно:
- Человек ПРЕДЛАГАЕТ СВОИ услуги (сантехник любой сложности, электрик на дом, мастер маникюра, грузоперевозки, репетитор, ищу заказы) — это поиск клиентов, НЕ вакансия
- Человек сам ищет работу
- Это разовая/временная подработка или шабашка (выкопать яму, помочь переехать, разгрузить один раз)
- Реклама группы, канала, биржи труда
- Реклама агрегаторов: Яндекс Go, Glovo, Uber
- Сетевой маркетинг, "лёгкий заработок", "работа из дома 200с", "активным 1500с в день"
- Подозрительно на мошенничество
- Работа за рубежом (Россия, Казахстан, другая страна)
- Нелегальное: казино, ставки, наркотики, эскорт, интим
- Непонятно кто конкретно требуется

Отвечай ДА только если КОМПАНИЯ или ЧЕЛОВЕК НАНИМАЕТ кого-то к себе.
Отвечай только ДА или НЕТ.
Текст: {text}"""
        }]
    )
    return "ДА" in response.choices[0].message.content.strip().upper()

# РАБОЧИЙ 2б — достаточно данных и понятна должность?
def has_enough_data(text: str) -> bool:
    response = ai.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": f"""В объявлении понятно ВСЁ из списка?

1. Понятная конкретная должность — ясно кого НАНИМАЮТ (не просто "нужен человек", "жумушчу керек")
2. Понятно чем сотрудник будет заниматься
3. Есть контакт — номер телефона или @username (в любом месте текста)
4. Это постоянная работа по найму, а не разовая подработка и не предложение своих услуг

Отвечай только ДА или НЕТ.
Текст: {text}"""
        }]
    )
    return "ДА" in response.choices[0].message.content.strip().upper()

# РАБОЧИЙ 3 — парсинг полей
def parse_vacancy(text: str) -> dict:
    clean_text = text.replace('"', "'").replace('\\', '')

    response = ai.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": f"""Извлеки вакансию из объявления и верни JSON-объект.
Только JSON, без лишнего текста, без markdown.

КРИТИЧЕСКИ ВАЖНО: НИЧЕГО не выдумывай. Бери ТОЛЬКО то что прямо написано.
НО и НЕ ТЕРЯЙ то что написано — если требование есть в тексте, обязательно извлеки его.

{{
  "position": "понятное название должности",
  "category": "одна из категорий списка",
  "company": "название компании из вакансии или Частный работодатель",
  "work_schedule": "график или пусто",
  "requirements": "требования к кандидату которые ЕСТЬ в тексте или пусто",
  "conditions": "условия которые ЕСТЬ в тексте или пусто",
  "description": "краткая суть вакансии или пусто",
  "experience_work": "опыт коротко или пусто",
  "remote_work": false,
  "city": "город",
  "work_address": "адрес или пусто",
  "region": "регион или пусто",
  "payment_period": "В час / В день / В неделю / В месяц или пусто",
  "salary_net": 0,
  "company_description": "ссылка-контакт"
}}

Категории: it, trade, sales, construction, transport, food, education, beauty, services, manufacturing, security, medicine, finance, legal, marketing, admin, agriculture, hospitality, domestic, management, customer_support, warehouse, cleaning, other
Не подходит — other.

ПРАВИЛА:

position: понятно и не длинно, объединяй род, исправляй КАПС, с большой буквы

company: название из текста без кавычек. Если нет — "Частный работодатель"

work_schedule: график, две смены как "с 08:00 до 23:00". Нет — ""

requirements: требования к кандидату которые ЯВНО написаны. Блок может называться "Требования", "Кого мы ищем", "Кого ищем", "От вас". Каждое с новой строки через дефис. Если в тексте ТРЕБОВАНИЙ НЕТ — "". НЕ ВЫДУМЫВАЙ, но и НЕ ТЕРЯЙ существующие. Пример: "опыт работы торговым агентом от 3 лет"

conditions: что работодатель предлагает (зарплата, питание, развоз, компенсация, оформление). Блок "Условия", "Что предлагаем", "Мы предлагаем". Каждое с новой строки через дефис. Нет — ""

description: краткая суть. Без эмодзи, без телефонов, без префикса "Работодатель:". Нет — ""

experience_work: если в тексте есть опыт — извлеки коротко ("от 3 лет", "от 1 года"). Нет — ""

remote_work: false. true только если местная работа явно онлайн без мошенничества
city: по умолчанию "Бишкек", меняй только если указан другой
work_address: адрес если есть, иначе ""
region: по умолчанию "", только если явно указан
payment_period: "В час"/"В день"/"В неделю"/"В месяц". Зарплата не указана — ""
salary_net: только число. "от 35000 до 120000" → 35000 (в description уточни "от 35000 до 120000"). Нет — 0

company_description: найди номер или @username в ЛЮБОМ месте текста, сделай ССЫЛКУ без эмодзи. Номер может быть в форматах: 0707798195, +996559110622, 0707 79 81 95.
Приведи к виду 996XXXXXXXXX (ровно 12 цифр: 996 + 9 цифр):
- если начинается с 0 и 10 цифр → убери 0, добавь 996
- если начинается с 996 → оставь как есть
- если начинается с +996 → убери +
Затем:
- WhatsApp/Ватсап/вотсап → https://wa.me/996XXXXXXXXX
- Telegram/@username → https://t.me/username
- "звоните"/"только звонить" → tel:+996XXXXXXXXX
- Соцсеть не указана → https://wa.me/996XXXXXXXXX
Примеры: 0707798195 → https://wa.me/996707798195 ; +996559110622 → https://wa.me/996559110622

Объявление: {clean_text}"""
        }]
    )

    raw = strip_json_block(response.choices[0].message.content)
    if not raw:
        raise ValueError("GPT вернул пустой ответ")
    return json.loads(raw)

# РАБОЧИЙ 4 — валидатор
def validate_and_fix(original: str, parsed: dict) -> dict:
    response = ai.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": f"""Ты строгий редактор. От точности зависит репутация компании.
Сверь JSON с оригиналом. Удали выдуманное, верни потерянное.
Верни ТОЛЬКО исправленный JSON, без лишнего текста.

Главные правила:
- Если факта НЕТ в оригинале — поле пустое ""
- Если факт ЕСТЬ в оригинале но потерян в JSON — добавь его
- requirements: всё что в тексте является требованием к кандидату (включая блоки "Кого ищем", "От вас")
- conditions: всё что работодатель предлагает
- experience_work: если опыт упомянут — извлеки коротко
- salary_net: только число, диапазон → нижняя граница
- company: название из текста или "Частный работодатель", не число
- company_description: ОБЯЗАТЕЛЬНО ссылка из номера в тексте, без эмодзи. Формат 996 + 9 цифр. Если в тексте есть номер — поле НЕ пустое
- description: без префикса "Работодатель:", без эмодзи, без телефонов
- Нигде нет эмодзи и телефонов в текстовых полях

Оригинал:
{original}

JSON:
{json.dumps(parsed, ensure_ascii=False)}"""
        }]
    )

    raw = strip_json_block(response.choices[0].message.content)
    try:
        fixed = json.loads(raw)
        if fixed != parsed:
            print("🔧 Валидатор исправил поля")
        else:
            print("✓ Валидатор: всё верно")
        return fixed
    except json.JSONDecodeError:
        print("⚠ Валидатор вернул невалидный JSON — используем оригинал")
        return parsed

# ЖЁСТКАЯ ЗАЩИТА — без GPT, чистый код
def guard_against_hallucination(original: str, vacancy: dict) -> dict:
    """Если в оригинале нет блока требований/условий — обнуляем поле принудительно"""
    text_lower = original.lower()

    req_markers = [
        "требовани", "талап", "кандидат", "от вас", "нужно уметь",
        "обязанност", "кого мы ищем", "кого ищем", "ищем человек", "опыт"
    ]
    has_req_block = any(m in text_lower for m in req_markers)

    cond_markers = [
        "услови", "предлага", "шарт", "оформлени", "питани", "развоз",
        "график", "зарплат", "оплат", "з/п", "айлык", "компенсац", "бонус"
    ]
    has_cond_block = any(m in text_lower for m in cond_markers)

    if not has_req_block:
        vacancy["requirements"] = ""
    if not has_cond_block:
        vacancy["conditions"] = ""

    return vacancy

# Достраиваем служебные поля в финальный формат
def finalize(vacancy: dict) -> dict:
    category = vacancy.get("category", "other")
    if category not in CATEGORIES:
        category = "other"

    salary = vacancy.get("salary_net", 0)
    try:
        salary = int(salary)
    except (ValueError, TypeError):
        salary = 0

    period = vacancy.get("payment_period", "") or ""
    if salary == 0 and not period:
        period = ""

    return {
        "user_id": DEFAULT_USER_ID,
        "position": vacancy.get("position", "") or "",
        "category": category,
        "work_schedule": vacancy.get("work_schedule", "") or "",
        "requirements": vacancy.get("requirements", "") or "",
        "conditions": vacancy.get("conditions", "") or "",
        "description": vacancy.get("description", "") or "",
        "experience_work": vacancy.get("experience_work", "") or "",
        "remote_work": bool(vacancy.get("remote_work", False)),
        "city": vacancy.get("city", "") or "Бишкек",
        "work_address": vacancy.get("work_address", "") or "",
        "region": vacancy.get("region", "") or "",
        "payment_period": period,
        "salary_net": salary,
        "company": vacancy.get("company", "") or "Частный работодатель",
        "company_description": vacancy.get("company_description", "") or "",
    }

# РАБОЧИЙ 5 — отправка в Telegram
async def send_to_telegram(original: str, vacancy: dict):
    pretty_json = json.dumps(vacancy, ensure_ascii=False, indent=2)

    message = f"""✅ Найдена вакансия!

{pretty_json}

Оригинал:
{original[:500]}"""

    async with httpx.AsyncClient() as http:
        await http.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": message}
        )

# РАБОЧИЙ 1 — слушатель
@client.on(events.NewMessage(chats=GROUPS))
async def handle_new_message(event):
    text = event.message.text
    if not text:
        return

    print(f"\n📨 Сообщение: {text[:50]}...")

    if not is_job_offer(text):
        print("🗑 Не вакансия / услуги / разовая — пропускаем")
        return

    if not has_enough_data(text):
        print("⚠ Непонятная должность или мало данных — пропускаем")
        return

    print("✓ Вакансия — парсим...")

    try:
        parsed = parse_vacancy(text)
        parsed = validate_and_fix(text, parsed)
        parsed = guard_against_hallucination(text, parsed)
        final = finalize(parsed)

        # Без контакта вакансия не имеет смысла — пропускаем
        if not final["company_description"]:
            print("⚠ Нет контакта — пропускаем вакансию")
            return

        contact = final["company_description"]
        position = final["position"] or "no_position"
        vacancy_hash = make_hash(contact, position)

        if vacancy_hash in seen_hashes:
            print(f"🔁 Дубль — {position}")
            return

        seen_hashes.add(vacancy_hash)
        save_seen(seen_hashes)

        print(f"📋 {final['position']} [{final['category']}]")
        await send_to_telegram(text, final)
        print("📤 Отправлено!")

    except Exception as e:
        print(f"✗ Ошибка: {e}")

async def main():
    if SESSION_STRING:
        print("Подключаемся через SESSION_STRING...")
        await client.start()
    else:
        print(f"Подключаемся с номером: {PHONE}")
        await client.start(phone=PHONE)
    print("✓ Успешно подключены!")
    print(f"Слушаем группы: {', '.join(GROUPS)}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())