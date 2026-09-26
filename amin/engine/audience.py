"""النوع 7: ملاءمة الخطاب للجمهور الذي تحدده الجهة.

الأداة لا تستنتج شيئًا عن الأفراد؛ الجهة تختار جمهورها، ونقيّم الأسلوب على ضوئه.
شعار هذا الفاحص: ﴿ادْعُ إِلَىٰ سَبِيلِ رَبِّكَ بِالْحِكْمَةِ وَالْمَوْعِظَةِ الْحَسَنَةِ ۖ وَجَادِلْهُم بِالَّتِي هِيَ أَحْسَنُ﴾ [النحل: 125]
"""

from __future__ import annotations

import re

from amin.engine.model import Finding
from amin.engine.segment import split_target

AUDIENCES = {
    "general": {"name_ar": "عامة الناس", "max_len": 28},
    "children": {"name_ar": "الأطفال والناشئة", "max_len": 14},
    "new_muslims": {"name_ar": "المسلمون الجدد", "max_len": 20},
    "non_muslims": {"name_ar": "غير المسلمين", "max_len": 24},
    "academics": {"name_ar": "الفلاسفة والأكاديميون", "max_len": 40},
}

_HARSH = {
    "en": re.compile(r"\b(you will burn|burn forever|damned|doomed|accursed|you are (?:all )?(?:losers|misguided|ignorant)|stupid|foolish)\b", re.I),
    "fr": re.compile(r"\b(vous brûlerez|damnés?|maudits?|vous êtes (?:tous )?(?:égarés|ignorants)|stupides?|idiots?)\b", re.I),
}
_FEAR = {
    "en": re.compile(r"\b(hell|hellfire|torment|punishment|fire|wrath)\b", re.I),
    "fr": re.compile(r"\b(enfer|châtiment|tourment|feu|colère)\b", re.I),
}
_HOPE = {
    "en": re.compile(r"\b(mercy|merciful|paradise|jannah|forgive|forgiveness|love|reward|peace)\b", re.I),
    "fr": re.compile(r"\b(miséricorde|miséricordieux|paradis|pardon|pardonne|amour|récompense|paix)\b", re.I),
}
_ABSOLUTE = {
    "en": re.compile(r"\b(obviously|everyone knows|undeniably|without any doubt|clearly proves|it is self-evident)\b", re.I),
    "fr": re.compile(r"\b(évidemment|tout le monde sait|indéniablement|sans aucun doute|prouve clairement)\b", re.I),
}
_WORDS = re.compile(r"[A-Za-zÀ-ÿ'’-]+")


def check_audience(target: str, lang: str, audience: str) -> tuple[list[Finding], dict]:
    prof = AUDIENCES.get(audience, AUDIENCES["general"])
    sents = split_target(target)
    lens = [len(_WORDS.findall(s.text)) for s in sents] or [0]
    avg = sum(lens) / len(lens)
    out: list[Finding] = []

    for i, s in enumerate(sents):
        n = lens[i]
        if n > prof["max_len"]:
            out.append(Finding(
                type=7, severity="low", start=s.start, end=s.end, found=s.text,
                suggestion="",
                reason_ar=f"الجملة طويلة ({n} كلمة) على جمهور «{prof['name_ar']}»؛ يُستحسن تقسيمها إلى جمل أقصر.",
                rule="audience:long-sentence", sentence=i,
            ))

    if audience in ("non_muslims", "new_muslims", "children", "general"):
        for m in _HARSH[lang].finditer(target):
            out.append(Finding(
                type=7, severity="medium", start=m.start(), end=m.end(), found=m.group(0),
                suggestion="",
                reason_ar="عبارة جارحة أو منفّرة للمخاطَب؛ والله أمر بالحكمة والموعظة الحسنة والجدال بالتي هي أحسن [النحل: 125].",
                rule="audience:harsh", needs_review=True,
            ))

    fear, hope = len(_FEAR[lang].findall(target)), len(_HOPE[lang].findall(target))
    if audience in ("children", "new_muslims", "non_muslims") and fear >= 2 and fear > hope * 2:
        out.append(Finding(
            type=7, severity="low", start=-1, end=-1, found="",
            suggestion="",
            reason_ar=f"غلب على النص الترهيب ({fear} موضعًا) على الترغيب ({hope})؛ ويُستحسن لجمهور «{prof['name_ar']}» الموازنة بينهما وتقديم الرحمة.",
            rule="audience:fear-balance",
        ))

    if audience == "academics":
        for m in _ABSOLUTE[lang].finditer(target):
            out.append(Finding(
                type=7, severity="low", start=m.start(), end=m.end(), found=m.group(0),
                suggestion="",
                reason_ar="الجمهور الأكاديمي والفلسفي يُقنعه الدليل المرتّب لا عبارات القطع الإنشائية؛ يُستبدل بها عرض الحجة.",
                rule="audience:absolute",
            ))
        if target.count("!") >= 2:
            out.append(Finding(
                type=7, severity="low", start=-1, end=-1, found="",
                suggestion="",
                reason_ar="كثرة علامات التعجب تُضعف الطابع البرهاني للنص عند الجمهور الأكاديمي.",
                rule="audience:exclamations",
            ))

    report = {
        "audience": audience,
        "audience_name_ar": prof["name_ar"],
        "sentences": len(sents),
        "avg_sentence_words": round(avg, 1),
        "max_sentence_words": max(lens),
        "fear_mentions": fear,
        "hope_mentions": hope,
    }
    return out, report
