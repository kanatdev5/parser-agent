import hashlib
import json
import os
import re
import base64

from config import (
    SEEN_FILE, TG_LINK_RE, ALLOWED_CHARS_RE, GLITCH_CHECK_FIELDS,
    PHONE_RE, USERNAME_RE, WA_LINK_RE, SPAMMY_USERNAME_RE,
)


def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def make_hash(text: str) -> str:
    key = normalize_text(text)
    return hashlib.md5(key.encode()).hexdigest()


def strip_json_block(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return raw


def strip_tg_mentions(text: str) -> str:
    return TG_LINK_RE.sub(" ", text or "")


def as_bool(v, default=True) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    s = str(v).strip().lower()
    if s in ("false", "0", "no", "нет", ""):
        return False
    if s in ("true", "1", "yes", "да"):
        return True
    return default


def has_foreign_chars(text: str) -> bool:
    return bool(ALLOWED_CHARS_RE.search(text or ""))


def strip_foreign_chars(text: str) -> str:
    cleaned = ALLOWED_CHARS_RE.sub("", text or "")
    return re.sub(r"\s+", " ", cleaned).strip()


def has_glitch(vacancy: dict) -> bool:
    if not isinstance(vacancy, dict):
        return False
    for f in GLITCH_CHECK_FIELDS:
        if has_foreign_chars(str(vacancy.get(f, "") or "")):
            return True
    return False


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("996") and len(digits) == 12:
        return digits
    if digits.startswith("0") and len(digits) == 10:
        return "996" + digits[1:]
    if len(digits) == 9 and digits[0] in "23579":
        return "996" + digits
    return ""


def extract_contact(text: str) -> str:
    text = strip_tg_mentions(text)

    wa_link = WA_LINK_RE.search(text or "")
    if wa_link:
        normalized = normalize_phone(wa_link.group(1))
        if normalized:
            return f"https://wa.me/{normalized}"

    username = USERNAME_RE.search(text or "")
    if username and not SPAMMY_USERNAME_RE.search(username.group(0)):
        return f"https://t.me/{username.group(1)}"

    phone = PHONE_RE.search(text or "")
    if not phone:
        return ""

    normalized = normalize_phone(phone.group(0))
    if not normalized:
        return ""

    tail = normalize_text(text[max(0, phone.start() - 80):phone.end() + 80])
    if re.search(r"только звон|звоните|звонок|не писать|чалы", tail):
        return f"tel:+{normalized}"
    return f"https://wa.me/{normalized}"


def strip_list_markers(text: str) -> str:
    lines = (text or "").split("\n")
    cleaned = [re.sub(r"^[\-–—•*]\s*", "", line).strip() for line in lines]
    return "\n".join(l for l in cleaned if l)


def has_contact(text: str) -> bool:
    return bool(extract_contact(text))


def jwt_exp(token: str) -> int:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        return int(data.get("exp", 0))
    except Exception:
        return 0
