"""النوع 6: النصوص الشرعية — الآيات والأحاديث.

- آية بين ﴿…﴾ في الأصل: إن عرفناها من المصادر الموثقة قارنّا ترجمتها بترجمة المعاني المعتمدة،
  وإلا طلبنا في الترجمة عزوًا (رقم السورة والآية).
- حديث في الأصل: إن ذُكر مخرّجه («رواه البخاري»، «متفق عليه») وجب أن يظهر العزو في الترجمة،
  وإن ذُكرت الصلاة على النبي ﷺ وجب ألا تسقط.
"""

from __future__ import annotations

import re

from amin.engine.model import Finding
from amin.engine.normalize import normalize_ar
from amin.engine.segment import Span
from amin.glossary.loader import Knowledge

_AYAH = re.compile(r"﴿([^﴾]+)﴾")
_REF = re.compile(r"(?:\b\d{1,3}\s*[:：.]\s*\d{1,3}\b)|(?:\[\s*[A-Za-zÀ-ÿ'’\- ]+\s*:?\s*\d{1,3}\s*\])|(?:\b(?:surah|sourate|sura)\b)", re.I)
_WORD = re.compile(r"[A-Za-zÀ-ÿ]+")
_STOP = set("""the and of to a in is are was were be he his him they them their you your we our it its that this with for on as
by at from who whom which what or not nor but so then than those these there here have has had will shall may
le la les de des du un une et en est sont il ils elle elles vous nous leur leurs son sa ses que qui dans pour par sur au aux ce
cette ces ne pas se lui""".split())

_HADITH_SRC_AR = re.compile(r"(رواه|اخرجه|متفق عليه|في الصحيحين|صحيح البخاري|صحيح مسلم)")
_HADITH_SRC_T = re.compile(r"(bukh[aā]r[iī]|muslim\b|ab[uū] d[aā]w[uū]d|tirmidh|nas[aā]['’]?[iī]|ibn m[aā]jah|ahmad|agreed upon|reported by|narrated by|rapporté|muttafaq|al-bukh)", re.I)
_SALAWAT_AR = re.compile(r"(صلي الله عليه وسلم|ﷺ|عليه الصلاه والسلام)")
_SALAWAT_T = re.compile(r"(ﷺ|peace be upon him|pbuh|\(saw\)|s\.a\.w|salla|que la paix|paix et (le )?salut|sws|صلى)", re.I)
_MESSENGER_T = re.compile(r"\b(muhammad|mohammed|messenger|prophet|proph[èe]te|messager)\b", re.I)


def _content_words(s: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(s) if len(w) > 2 and w.lower() not in _STOP}


def similarity(a: str, b: str) -> float:
    A, B = _content_words(a), _content_words(b)
    if not A or not B:
        return 0.0
    # المقام الأصغر: الأصل قد يقتبس جزءًا من الآية، والجملة قد تزيد عليها
    return len(A & B) / min(len(A), len(B))


def _match_ayah(k: Knowledge, quote_norm: str):
    q = re.sub(r"[^ء-ي ]", "", quote_norm).strip()
    q = re.sub(r"\s+", " ", q)
    if len(q) < 6:
        return None
    for ay in k.ayat:
        full = re.sub(r"\s+", " ", re.sub(r"[^ء-ي ]", "", ay.ar_norm)).strip()
        if q in full:
            return ay
    return None


def check_scripture(k: Knowledge, pairs: list[tuple[Span, Span]], target: str, lang: str) -> list[Finding]:
    out: list[Finding] = []
    for si, (ar, tg) in enumerate(pairs):
        seg = target[tg.start:tg.end]
        ar_norm = normalize_ar(ar.text)

        for m in _AYAH.finditer(ar_norm):
            ay = _match_ayah(k, m.group(1))
            if ay:
                approved = ay.tr[lang]
                sim = similarity(approved, seg)
                has_ref = bool(_REF.search(seg))
                if sim < 0.3:
                    out.append(Finding(
                        type=6, severity="high", start=tg.start, end=tg.end, found=seg,
                        suggestion=f"{approved} [{ay.ref}]",
                        reason_ar=f"الأصل يقتبس الآية ({ay.ref}) لكن الترجمة لا تقارب ترجمة المعاني المعتمدة (نسبة التقارب {sim:.0%}). تُنقل الآية بترجمة معتمدة لا بصياغة حرة.",
                        source=k.editions.get(lang, ""), ref_id=ay.ref, rule="ayah:free-translation",
                        replace=False, sentence=si, extra={"similarity": round(sim, 2)},
                    ))
                elif not has_ref:
                    out.append(Finding(
                        type=6, severity="low", start=tg.start, end=tg.end, found=seg,
                        suggestion=f"[{ay.ref}]",
                        reason_ar=f"الآية ({ay.ref}) مترجمة دون ذكر موضعها؛ يُستحسن إثبات رقم السورة والآية ليتحقق القارئ.",
                        source=k.editions.get(lang, ""), ref_id=ay.ref, rule="ayah:no-ref",
                        sentence=si,
                    ))
            elif not _REF.search(seg):
                out.append(Finding(
                    type=6, severity="medium", start=tg.start, end=tg.end, found=seg,
                    suggestion="",
                    reason_ar="في الأصل نص قرآني بين ﴿…﴾ لم نجده في مصادرنا الموثقة، والترجمة لا تذكر موضعه؛ يُراجع النص ويُعزى إلى سورته وآيته بترجمة معتمدة.",
                    rule="ayah:unknown", needs_review=True, sentence=si,
                ))

        if _HADITH_SRC_AR.search(ar_norm) and not _HADITH_SRC_T.search(seg):
            out.append(Finding(
                type=6, severity="medium", start=tg.start, end=tg.end, found=seg,
                suggestion="",
                reason_ar="الأصل يذكر تخريج الحديث (من رواه)، والترجمة أسقطت العزو؛ العزو شرط الأمانة في نقل السنة.",
                rule="hadith:no-source", needs_review=False, sentence=si,
            ))
        if _SALAWAT_AR.search(ar_norm) and _MESSENGER_T.search(seg) and not _SALAWAT_T.search(seg):
            mm = _MESSENGER_T.search(seg)
            s, e = tg.start + mm.start(), tg.start + mm.end()
            out.append(Finding(
                type=5, severity="low", start=s, end=e, found=target[s:e],
                suggestion=f"{target[s:e]} ﷺ",
                reason_ar="الأصل فيه الصلاة على النبي ﷺ وقد سقطت من الترجمة.",
                rule="hadith:salawat", replace=True, sentence=si,
            ))
    return out
