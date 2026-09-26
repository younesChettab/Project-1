"""خط الفحص الكامل: يجمع الفاحصات ويزيل التكرار ويرتّب النتائج."""

from __future__ import annotations

import re

from amin.engine import llm
from amin.engine.attributes import check_attributes
from amin.engine.audience import check_audience
from amin.engine.model import SEVERITY_RANK, TYPES, Finding
from amin.engine.scripture import check_scripture
from amin.engine.segment import align
from amin.engine.terms import check_bare_translit, check_omissions, check_terms
from amin.glossary.loader import load

_FR_HINT = re.compile(r"\b(le|la|les|des|est|et|dans|qui|que|pour|une|du|au|aux|sont|leur|nous|vous)\b", re.I)
_EN_HINT = re.compile(r"\b(the|and|is|are|of|to|who|which|that|for|with|they|their|we|you)\b", re.I)


def detect_lang(text: str) -> str:
    return "fr" if len(_FR_HINT.findall(text)) > len(_EN_HINT.findall(text)) else "en"


def _overlaps(a: Finding, b: Finding) -> bool:
    return a.start >= 0 and b.start >= 0 and a.start < b.end and b.start < a.end


def _dedupe(findings: list[Finding]) -> list[Finding]:
    # الأولوية: الأخطر، ثم نوع الصفات والمسيء قبل غيرهما، ثم الأوسع نطاقًا (العبارة كاملة أولى من جزئها)
    prio = {4: 0, 2: 1, 6: 2, 1: 3, 5: 4, 3: 5, 7: 6}
    ordered = sorted(findings, key=lambda f: (SEVERITY_RANK[f.severity], prio.get(f.type, 9), -(f.end - f.start)))
    kept: list[Finding] = []
    for f in ordered:
        # تنبيهات الجملة كاملة (نفي، آية) لا تُلغي تنبيهات المصطلحات داخلها
        wide = f.rule.startswith(("omission", "ayah", "hadith:no-source", "audience:long"))
        if not wide and any(_overlaps(f, g) and not g.rule.startswith(("omission", "ayah", "hadith:no-source", "audience:long")) for g in kept):
            continue
        if any(f.rule == g.rule and f.start == g.start and f.end == g.end for g in kept):
            continue
        kept.append(f)
    return kept


def run(arabic: str, translation: str, lang: str | None = None, audience: str = "general",
        use_llm: bool = True) -> dict:
    k = load()
    lang = lang if lang in ("en", "fr") else detect_lang(translation)
    pairs, aligned = align(arabic, translation)

    findings: list[Finding] = []
    findings += check_attributes(k, pairs, translation, lang)
    findings += check_terms(k, pairs, translation, lang)
    findings += check_bare_translit(k, translation, lang)
    findings += check_scripture(k, pairs, translation, lang)
    findings += check_omissions(pairs, translation, lang, aligned)
    aud, aud_report = check_audience(translation, lang, audience)
    findings += aud

    llm_error = None
    llm_used = False
    if use_llm and llm.available():
        extra, llm_error = llm.check_llm(k, arabic, translation, lang, audience, findings)
        llm_used = llm_error is None
        findings += extra

    findings = _dedupe(findings)
    findings.sort(key=lambda f: (f.start if f.start >= 0 else 10**9, SEVERITY_RANK[f.severity]))
    for i, f in enumerate(findings, 1):
        f.id = f"f{i}"

    by_type = {t: 0 for t in TYPES}
    for f in findings:
        by_type[f.type] += 1

    return {
        "lang": lang,
        "aligned": aligned,
        "sentences": [{"ar": a.text, "tr": t.text, "start": t.start, "end": t.end} for a, t in pairs] if aligned else [],
        "findings": [f.to_dict() for f in findings],
        "stats": {
            "total": len(findings),
            "by_type": by_type,
            "by_severity": {s: sum(1 for f in findings if f.severity == s) for s in SEVERITY_RANK},
            "needs_review": sum(1 for f in findings if f.needs_review),
        },
        "types": TYPES,
        "audience": aud_report,
        "llm": {"available": llm.available(), "used": llm_used, "error": llm_error},
    }


def apply_corrections(translation: str, findings: list[dict], accepted: set[str]) -> str:
    """يطبق المقترحات المقبولة القابلة للاستبدال المباشر، من آخر النص إلى أوله."""
    chosen = [f for f in findings if f["id"] in accepted and f.get("replace") and f["start"] >= 0 and f["suggestion"]]
    chosen.sort(key=lambda f: f["start"], reverse=True)
    out, last = translation, len(translation) + 1
    for f in chosen:
        if f["end"] > last:
            continue  # تداخل ← نتجاوز
        out = out[:f["start"]] + f["suggestion"] + out[f["end"]:]
        last = f["start"]
    return out
