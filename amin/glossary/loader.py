"""تحميل القاموس والمصادر الموثقة وتجهيز أنماطها."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from amin.engine.normalize import normalize_ar

ROOT = Path(__file__).resolve().parent.parent
LANGS = ("en", "fr")

# حدود الكلمة اللاتينية مع دعم الحروف المشكولة والفاصلة العليا
_WB_L = r"(?<![A-Za-zÀ-ÿĀ-ɏḀ-ỿ‘ʿ-])"  # الفاصلة العليا مسموحة قبل الكلمة لأجل الإدغام الفرنسي (l'aumône)
_WB_R = r"(?![A-Za-zÀ-ÿĀ-ɏḀ-ỿ-])"


def _latin(p: str) -> re.Pattern:
    return re.compile(_WB_L + "(?:" + p + ")" + _WB_R, re.IGNORECASE)


@dataclass
class Term:
    id: str
    ar: list[str]
    translit: list[re.Pattern]
    gloss: dict[str, list[re.Pattern]]
    forbidden: dict[str, list[re.Pattern]]
    forbidden_type: int
    approved: dict[str, str]
    note_ar: str
    source: str
    severity: str
    is_global: bool
    reviewed: bool
    raw: dict = field(repr=False)


@dataclass
class Attribute:
    id: str
    name_ar: str
    ar: list[str]
    tawil: dict[str, list[re.Pattern]]
    approved: dict[str, str]
    evidence_ayat: list[str]
    evidence_hadith: list[str]
    quotes: list[str]
    note_ar: str
    severity: str
    reviewed: bool
    raw: dict = field(repr=False)


@dataclass
class Ayah:
    ref: str
    ar: str
    ar_norm: str
    tr: dict[str, str]
    partial: bool


def _load_yaml(rel: str) -> dict:
    with open(ROOT / rel, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def load() -> "Knowledge":
    g = _load_yaml("glossary/terms.yaml")
    terms = []
    for t in g["terms"]:
        terms.append(Term(
            id=t["id"],
            ar=t.get("ar") or [],
            translit=[_latin(p) for p in t.get("translit") or []],
            gloss={l: [_latin(p) for p in (t.get("gloss") or {}).get(l, [])] for l in LANGS},
            forbidden={l: [_latin(p) for p in (t.get("forbidden") or {}).get(l, [])] for l in LANGS},
            forbidden_type=int(t.get("forbidden_type", 1)),
            approved=t["approved"],
            note_ar=t.get("note_ar", ""),
            source=t.get("source", ""),
            severity=t.get("severity", "medium"),
            is_global=bool(t.get("global", False)),
            reviewed=bool(t.get("reviewed", False)),
            raw=t,
        ))
    attrs = []
    for a in g["attributes"]:
        attrs.append(Attribute(
            id=a["id"],
            name_ar=a["name_ar"],
            ar=a["ar"],
            tawil={l: [re.compile(p, re.IGNORECASE) for p in a["tawil"].get(l, [])] for l in LANGS},
            approved=a["approved"],
            evidence_ayat=a.get("evidence_ayat", []),
            evidence_hadith=a.get("evidence_hadith", []),
            quotes=a.get("quotes", []),
            note_ar=a.get("note_ar", ""),
            severity=a.get("severity", "high"),
            reviewed=bool(a.get("reviewed", False)),
            raw=a,
        ))
    q = _load_yaml("sources/quotes.yaml")
    ay = _load_yaml("sources/ayat.yaml")
    ayat = [Ayah(ref=x["ref"], ar=x["ar"], ar_norm=normalize_ar(x["ar"]),
                 tr={"en": x["en"], "fr": x["fr"]}, partial=bool(x.get("partial")))
            for x in ay["ayat"]]
    return Knowledge(
        terms=terms,
        attributes=attrs,
        quotes={x["id"]: x for x in q.get("quotes", [])},
        hadith={x["id"]: x for x in q.get("hadith", [])},
        ayat=ayat,
        editions=ay.get("editions", {}),
    )


@dataclass
class Knowledge:
    terms: list[Term]
    attributes: list[Attribute]
    quotes: dict[str, dict]
    hadith: dict[str, dict]
    ayat: list[Ayah]
    editions: dict[str, str]

    def term(self, tid: str) -> Term | None:
        return next((t for t in self.terms if t.id == tid), None)

    def attribute(self, aid: str) -> Attribute | None:
        return next((a for a in self.attributes if a.id == aid), None)

    def ayah(self, ref: str) -> Ayah | None:
        return next((a for a in self.ayat if a.ref == ref), None)
