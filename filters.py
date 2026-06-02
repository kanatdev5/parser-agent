import re

from config import REJECT_PATTERNS, JOB_SIGNAL_PATTERNS
from utils import normalize_text, has_contact


def is_obvious_reject(text: str) -> bool:
    compact = normalize_text(text)
    if len(compact) < 15:
        return True
    return any(re.search(pattern, compact, re.I) for pattern in REJECT_PATTERNS)


def has_job_signal(text: str) -> bool:
    compact = normalize_text(text)
    return any(re.search(pattern, compact, re.I) for pattern in JOB_SIGNAL_PATTERNS)


def is_job_offer(text: str) -> bool:
    if is_obvious_reject(text):
        return False
    if not has_contact(text):
        return False
    if not has_job_signal(text):
        return False
    return True


def has_enough_data(text: str) -> bool:
    return has_contact(text) and has_job_signal(text) and not is_obvious_reject(text)
