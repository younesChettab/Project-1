"""تطبيع النص العربي قبل المطابقة."""

import re

_TASHKEEL = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_ALEF = re.compile(r"[إأآٱ]")

AR_LETTER = r"ء-ي"
# حروف السوابق الشائعة: و ف ب ل ك، ثم «ال» اختياريًّا
_PREFIX = r"(?:[وفبلك]{0,2})(?:ال)?"
_SUFFIX = r"(?:ه|ها|هم|هن|كم|كن|نا|ي|ين|ون|ات|ان|وا)?"


def normalize_ar(text: str) -> str:
    text = _TASHKEEL.sub("", text)
    text = _ALEF.sub("ا", text)
    text = text.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    return text


def ar_pattern(form: str) -> re.Pattern:
    """نمط يطابق الصيغة كلمةً مستقلة مع السوابق واللواحق الشائعة."""
    form = normalize_ar(form)
    words = [re.escape(w) for w in form.split()]
    core = r"\s+".join(words)
    return re.compile(
        rf"(?:^|(?<=[^{AR_LETTER}])){_PREFIX}{core}{_SUFFIX}(?=$|[^{AR_LETTER}])"
    )


def contains_ar(text_norm: str, forms: list[str]) -> bool:
    return any(ar_pattern(f).search(text_norm) for f in forms)
