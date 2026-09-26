"""الأنواع 1-3: المصطلحات الشرعية والقاعدة الذهبية.

القاعدة الذهبية: يُكتب المصطلح بلفظه العربي بالحروف اللاتينية أولًا ثم معناه بين قوسين.
"""

from __future__ import annotations

import re

from amin.engine.model import Finding
from amin.engine.normalize import contains_ar, normalize_ar
from amin.engine.segment import Span
from amin.glossary.loader import Knowledge, Term


def _paired_with_translit(term: Term, text: str, start: int, end: int) -> bool:
    """هل الكلمة المترجمة مقرونة باللفظ العربي؟ إما داخل قوسين بعده: Salah (Prayer)،
    أو يليها اللفظ العربي بين قوسين: prayer (Salah)."""
    if _inside_gloss(term, text, start):
        return True
    after = text[end:end + 30]
    op = after.find("(")
    return 0 <= op <= 2 and any(p.search(after[op:]) for p in term.translit)


def _inside_gloss(term: Term, text: str, start: int) -> bool:
    """هل الكلمة داخل قوسين يسبقهما اللفظ العربي المنقول؟"""
    before = text[max(0, start - 40):start]
    op = before.rfind("(")
    if op < 0 or ")" in before[op:]:
        return False
    return any(p.search(before[:op]) for p in term.translit)


_LETTERS = re.compile(r"[^\wÀ-ÿ]+")


def _words(s: str) -> str:
    return " " + _LETTERS.sub(" ", s.lower()).strip() + " "


def _in_approved_quote(k: Knowledge, text: str, start: int, end: int, lang: str) -> bool:
    """هل الكلمة جزء من اقتباس يطابق حرفيًّا ترجمة معاني معتمدة لآية؟ (الكلمة مع ثلاث كلمات قبلها)"""
    before = _LETTERS.sub(" ", text[max(0, start - 60):start].lower()).split()[-3:]
    if len(before) < 2:
        return False
    probe = " " + " ".join(before + [text[start:end].lower()]) + " "
    return any(probe in _words(ay.tr[lang]) for ay in k.ayat)


def check_terms(k: Knowledge, pairs: list[tuple[Span, Span]], target: str, lang: str) -> list[Finding]:
    out: list[Finding] = []
    for si, (ar, tg) in enumerate(pairs):
        ar_norm = normalize_ar(ar.text)
        seg = target[tg.start:tg.end]
        for term in k.terms:
            in_source = bool(term.ar) and contains_ar(ar_norm, term.ar)

            # 1) المقابلات المحظورة: تُفحص إن ورد المصطلح في الأصل، أو كان البند عامًّا
            if in_source or term.is_global:
                for pat in term.forbidden.get(lang, []):
                    for m in pat.finditer(seg):
                        s, e = tg.start + m.start(), tg.start + m.end()
                        if _inside_gloss(term, target, s):
                            continue  # مثل: Shuhada (Martyrs) — المعنى بين قوسين بعد اللفظ العربي مقبول
                        if _in_approved_quote(k, target, s, e, lang):
                            continue  # اقتباس مطابق لترجمة معاني المجمع — هي المرجع
                        out.append(Finding(
                            type=term.forbidden_type,
                            severity="high" if term.forbidden_type == 2 else term.severity,
                            start=s, end=e, found=target[s:e],
                            suggestion=term.approved[lang],
                            reason_ar=term.note_ar,
                            source=term.source, ref_id=term.id,
                            rule=f"forbidden:{term.id}", replace=True, sentence=si,
                        ))
            if not in_source:
                continue

            # 2) القاعدة الذهبية: الترجمة المجردة دون اللفظ العربي المنقول
            for pat in term.gloss.get(lang, []):
                for m in pat.finditer(seg):
                    s, e = tg.start + m.start(), tg.start + m.end()
                    if _paired_with_translit(term, target, s, e):
                        continue
                    out.append(Finding(
                        type=3, severity=term.severity if term.severity != "high" else "medium",
                        start=s, end=e, found=target[s:e],
                        suggestion=term.approved[lang],
                        reason_ar="القاعدة الذهبية: يُقدَّم اللفظ الشرعي بالحروف اللاتينية ثم معناه بين قوسين. " + term.note_ar,
                        source=term.source, ref_id=term.id,
                        rule=f"golden:{term.id}", replace=True, sentence=si,
                    ))
                    break  # تنبيه واحد لكل بند في الجملة يكفي
    return out


def check_bare_translit(k: Knowledge, target: str, lang: str) -> list[Finding]:
    """لفظ عربي منقول بلا معنى بين قوسين بعده — النصف الثاني من القاعدة الذهبية."""
    out = []
    for term in k.terms:
        if term.id == "allah":
            continue  # لفظ الجلالة لا يحتاج شرحًا
        for pat in term.translit:
            for m in pat.finditer(target):
                after = target[m.end():m.end() + 16]
                before = target[max(0, m.start() - 2):m.start()]
                if "(" in after or "[" in after or "(" in before:
                    continue
                out.append(Finding(
                    type=3, severity="low",
                    start=m.start(), end=m.end(), found=m.group(0),
                    suggestion=term.approved[lang],
                    reason_ar="اللفظ العربي ورد دون معناه بين قوسين؛ القارئ غير العربي قد لا يفهمه. " + term.note_ar,
                    source=term.source, ref_id=term.id,
                    rule=f"bare:{term.id}", replace=True,
                ))
    return out


# أدوات النفي والنهي في العربية (مع السوابق و/ف)، ومقابلاتها في الترجمة.
# نقارن العدد: إن قلّت أدوات النفي في الترجمة عن الأصل فقد سقط نفي.
_NEG_AR = re.compile(r"(?:^|(?<=\s))[وف]?(?:لا|لم|لن|ليس|ليست|لستم|لسنا)(?=\s|$)")
_NEG_T = {
    "en": re.compile(r"\b(?:not|no|never|nor|none|neither|without|cannot|n['’]t|forbidden|prohibited|impermissible)\b", re.I),
    "fr": re.compile(r"\b(?:pas|jamais|ni|aucun|aucune|nul|nulle|sans|interdit|interdite|point|guère)\b", re.I),
}
_EXC_AR = re.compile(r"(?:^|(?<=\s))[وف]?(?:الا|سوي)(?=\s|$)")
_EXC_T = {
    "en": re.compile(r"\b(?:except|but|only|save|unless|other than)\b", re.I),
    "fr": re.compile(r"\b(?:sauf|excepté|hormis|seul|seulement|que|si ce n['’]est)\b", re.I),
}


def check_omissions(pairs: list[tuple[Span, Span]], target: str, lang: str, aligned: bool) -> list[Finding]:
    """النوع 5: احتمال سقوط النفي أو الاستثناء (يحتاج محاذاة بالجمل)."""
    if not aligned:
        return []
    out = []
    for si, (ar, tg) in enumerate(pairs):
        ar_norm = normalize_ar(ar.text)
        # نتجاوز ما بين الأقواس القرآنية لأن الآيات تُفحص في فاحص النصوص الشرعية
        ar_body = re.sub(r"﴿[^﴾]*﴾", " ", ar_norm)
        seg = target[tg.start:tg.end]
        n_ar, n_tg = len(_NEG_AR.findall(ar_body)), len(_NEG_T[lang].findall(seg))
        if n_ar > n_tg:
            out.append(Finding(
                type=5, severity="high", start=tg.start, end=tg.end, found=seg,
                suggestion="",
                reason_ar=f"في الأصل العربي {n_ar} من أدوات النفي أو النهي، وفي الترجمة {n_tg} فقط؛ سقوط النفي يقلب الحكم الشرعي.",
                rule="omission:negation", needs_review=True, sentence=si,
            ))
        if _EXC_AR.search(ar_body) and not _EXC_T[lang].search(seg):
            out.append(Finding(
                type=5, severity="medium", start=tg.start, end=tg.end, found=seg,
                suggestion="",
                reason_ar="في الأصل استثناء أو حصر («إلا»)، ولا يظهر ما يقابله في الترجمة؛ قد يتسع الحكم أو يضيق.",
                rule="omission:exception", needs_review=True, sentence=si,
            ))
    return out
