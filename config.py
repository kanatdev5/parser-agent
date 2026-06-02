import os
import re
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")
SESSION_STRING = os.getenv("SESSION_STRING", "")
GROUPS = ["@Jumush_BishkekKg", "@bishkek_jumush"]
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BACKEND_URL = os.getenv("BACKEND_URL", "").rstrip("/")
BACKEND_PHONE = os.getenv("BACKEND_PHONE", "")

DEFAULT_USER_ID = 1
SEEN_FILE = "seen_vacancies.json"

CATEGORIES = [
    "it", "trade", "sales", "construction", "transport", "food",
    "education", "beauty", "services", "manufacturing", "security",
    "medicine", "finance", "legal", "marketing", "admin",
    "agriculture", "hospitality", "domestic", "management",
    "customer_support", "warehouse", "cleaning", "other"
]

SCHEDULE_ENUM = ["Полный день", "Неполный день", "Сменный график", "Гибкий график"]

PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?996[\s\-()]*)?(?:0[\s\-()]*)?\d(?:[\s\-()]*\d){8}(?!\d)"
)
USERNAME_RE = re.compile(r"(?<![\w/])@([A-Za-z0-9_]{5,32})")
WA_LINK_RE = re.compile(r"(?:https?://)?(?:wa\.me|api\.whatsapp\.com/send\?phone=)/?(\+?\d[\d\s\-()]*)", re.I)
TG_LINK_RE = re.compile(r"tg://\S+", re.I)
SPAMMY_USERNAME_RE = re.compile(r"@(rasschitat_bot|anymelody_bot)\b", re.I)

ALLOWED_CHARS_RE = re.compile(
    "[^"
    "Ѐ-ӿ"
    "A-Za-z0-9"
    "\\s"
    "‐-―"
    "‘-‟"
    "…"
    "№"
    ".,:;!?'\"`@#%&*+/<>=~|()\\[\\]{}_\\\\-"
    "]"
)

REJECT_PATTERNS = [
    r"/start@",
    r"\b(?:симбанк|компаньон банк|компаньон|банк)\b.*\b(?:акция|бонус|кредит|регистрац)",
    r"\b(?:акция|бонус за регистрац|реферал|deeplink|simbank|kompanion)\b",
    r"\b(?:яндекс|yandex)[\s\-]*(?:go|еда|еды|еде|такси|taxi|про|pro|доставка)\b",
    r"\b(?:glovo|глово|wolt|волт|вольт)\b",
    r"reg\.eda\.yandex|eats\.yandex|user_invite_code|advertisement_campaign",
    r"интим",
    r"\bэскорт\b|escort",
    r"вебкам|webcam|вебкамщиц",
    r"индивидуалк|проститу",
    r"секс[\s\-]?(?:работ|услуг)",
    r"\bдосуг\b.{0,30}\b(?:девушк|кыз|оплат|сутк|ноч)\b",
    r"18\s*(?:ден|жаштан)\s*(?:ойдо|жогору).{0,40}\bкыз",
    r"\b(?:знакомств|18\+|watch here|horny)\b",
    r"жумуш\s*бар\s*бы|иш\s*бар\s*бы|жумуш бар бекен|иш бар бекен",
    r"\bиштейм\b|\bиштеем\b|иштейин|иштейли",
    r"\bиштейбиз\b|\bиштейбис\b",               # "мы работаем/готовы работать" — предлагают свой труд
    r"иш\s*болсо|жумуш\s*болсо",                # "если есть работа — пишите" — ищут работу сами
    r"жумуш айтып|иш айтып|жумуш тапса|иш тапса|жумуш таап",
    r"\b(?:ищу работу|ищу подработку|жумуш издейм|жумуш керек|мага жумуш|мне нужна работа)\b",
    r"\bиш керек\b",
    r"\b(?:иш|жумуш) изде",
    r"\d+\s*адам\s*кош",
    r"группага\s+(?:жазыш|кир|кош)",
    r"адам кошкул|адам кошунуз|кошуп койгул|подписывайтесь|вступайте в групп",
    r"кош келди|кош келиниз|группага кош|добро пожаловать в групп",
    r"\bлайк|колдоп кош|подпишитесь",
    r"\bпопутк|попутчик",
    r"беру посылки|туда и обратно|тууда обратно",
    r"мест[оа]?\s*\d.{0,25}(?:салон|посылк|обратно)",
    r"\b(?:недвижимость|ижара|аренда|квартирага подселение|подселение|сдается|сатылат|продается)\b",
    r"түнөп",
    r"\d+\s*комнат\w*\s*жашай|комнаттада жашай|чогуу жашай|бирге жашай|чогу жашай",
    r"бала керек.{0,30}жашай|жигит керек.{0,30}жашай",
    r"\b(?:онлайн|из дома|личные сообщения|лс)\b.*\b(?:подработка|жумуш|заработ)\b",
    r"готов\w*\s+текст",
    r"оператор\w*\s+переписк",
    r"переписк\w*\s+(?:с\s+)?клиент",
    r"(?:онлайн|удал[её]н|из дома|уйдо отуруп|уйдо олтуруп).{0,40}(?:отвеч|сообщени|переписк)",
    r"\b(?:россия|рф|ростов|сочи|анапа|гелджик|гелendжик|казахстан|алмата|кз)\b",
    r"\b(?:каспи|доверенность|вериф|верификац|открыть карту|загран)\b",
    r"\b(?:бригада|биргада)\s*керек\b",
    r"керек болсо",
    r"\b(?:tether|крипт|вейп|elfbar|сатылат|продаю)\b",
    r"\b(?:сантехник|электрик|ремонт|грузоперевоз)\b.{0,40}\b(?:услуг|жасайбыз|иштейбиз|24/7)\b",
    r"\b(?:авторынок|канал|подпис|кошул|вступай|реклама)\b.*(?:t\.me|whatsapp\.com/channel)",
]

JOB_SIGNAL_PATTERNS = [
    r"\b(?:требуется|требуются|ищем|нужен|нужна|нужны|набор|вакансия)\b",
    r"\b(?:керек|талап кылынат|жумушка чакырабыз|жумуш)\b",
    r"\b(?:продавец|кассир|официант|повар|посудомой|грузчик|водитель|курьер|охранник|уборщик|техничка|администратор|оператор|промоутер|рабочий|мастер|швея|бармен|шаурмист|пиццамейкер|сборщик|кладовщик)\b",
]

GLITCH_CHECK_FIELDS = [
    "position", "company", "description", "requirements",
    "conditions", "work_schedule", "experience_work", "work_address"
]

ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
