"""النوع 4: كشف تأويل الصفات أو تعطيلها في الترجمة، على منهج السلف."""

from __future__ import annotations

from amin.engine.model import Finding
from amin.engine.normalize import contains_ar, normalize_ar
from amin.engine.segment import Span
from amin.glossary.loader import Knowledge


def check_attributes(k: Knowledge, pairs: list[tuple[Span, Span]], target: str, lang: str) -> list[Finding]:
    out: list[Finding] = []
    for si, (ar, tg) in enumerate(pairs):
        ar_norm = normalize_ar(ar.text)
        seg = target[tg.start:tg.end]
        for attr in k.attributes:
            if not contains_ar(ar_norm, attr.ar):
                continue
            for pat in attr.tawil.get(lang, []):
                for m in pat.finditer(seg):
                    s, e = tg.start + m.start(), tg.start + m.end()
                    ev = ", ".join(attr.evidence_ayat + attr.evidence_hadith)
                    out.append(Finding(
                        type=4, severity=attr.severity,
                        start=s, end=e, found=target[s:e],
                        suggestion=attr.approved[lang],
                        reason_ar=f"{attr.name_ar}: {attr.note_ar}",
                        source=f"ترجمة المعاني المعتمدة ({ev})" if ev else "",
                        ref_id=attr.id, rule=f"tawil:{attr.id}",
                        replace=True, sentence=si,
                        extra={"quotes": attr.quotes, "ayat": attr.evidence_ayat, "hadith": attr.evidence_hadith},
                    ))
    return out
