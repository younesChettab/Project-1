"""واجهة «أمين» البرمجية — FastAPI.

التشغيل:  uvicorn amin.api:app --reload
"""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from amin import __version__
from amin.engine import llm
from amin.engine.audience import AUDIENCES
from amin.engine.model import TYPES
from amin.engine.pipeline import apply_corrections, run
from amin.glossary.loader import load

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
MAX_CHARS = 12000

app = FastAPI(title="Amin — أمين", version=__version__)


class CheckIn(BaseModel):
    arabic: str = Field(..., max_length=MAX_CHARS)
    translation: str = Field(..., max_length=MAX_CHARS)
    lang: str | None = None
    audience: str = "general"
    use_llm: bool = True


class ApplyIn(BaseModel):
    translation: str = Field(..., max_length=MAX_CHARS)
    findings: list[dict]
    accepted: list[str]


@app.get("/api/health")
def health():
    k = load()
    return {"ok": True, "version": __version__, "terms": len(k.terms), "attributes": len(k.attributes),
            "ayat": len(k.ayat), "quotes": len(k.quotes), "llm": llm.available()}


@app.get("/api/meta")
def meta():
    return {"types": TYPES,
            "audiences": {k: v["name_ar"] for k, v in AUDIENCES.items()},
            "llm": llm.available()}


@app.post("/api/check")
def check(body: CheckIn):
    if not body.arabic.strip() or not body.translation.strip():
        raise HTTPException(400, "الأصل العربي والترجمة مطلوبان")
    return run(body.arabic, body.translation, body.lang, body.audience, body.use_llm)


@app.post("/api/apply")
def apply(body: ApplyIn):
    return {"corrected": apply_corrections(body.translation, body.findings, set(body.accepted))}


@app.get("/api/glossary")
def glossary():
    k = load()
    return {
        "terms": [{"id": t.id, "ar": t.ar, "approved": t.approved, "note_ar": t.note_ar, "source": t.source,
                   "severity": t.severity, "reviewed": t.reviewed} for t in k.terms],
        "attributes": [{"id": a.id, "name_ar": a.name_ar, "ar": a.ar, "approved": a.approved,
                        "note_ar": a.note_ar, "ayat": a.evidence_ayat, "reviewed": a.reviewed}
                       for a in k.attributes],
    }


@app.get("/api/explain/{ref_id}")
def explain(ref_id: str, lang: str = "en"):
    """«البيان»: تعريف المصطلح ومقابله المعتمد والأدلة والنقول الموثقة — لا توليد فيه."""
    k = load()
    lang = lang if lang in ("en", "fr") else "en"
    t, a = k.term(ref_id), k.attribute(ref_id)
    ay = k.ayah(ref_id)
    if not (t or a or ay):
        raise HTTPException(404, "لا بيان لهذا البند")
    out = {"id": ref_id, "ayat": [], "hadith": [], "quotes": [], "reviewed": None}
    if t:
        out.update(title=t.id, note_ar=t.note_ar, approved=t.approved[lang], source=t.source,
                   reviewed=t.reviewed)
    if a:
        out.update(title=a.name_ar, note_ar=a.note_ar, approved=a.approved[lang], reviewed=a.reviewed)
        out["ayat"] = [{"ref": r, "ar": k.ayah(r).ar, "tr": k.ayah(r).tr[lang], "edition": k.editions.get(lang)}
                       for r in a.evidence_ayat if k.ayah(r)]
        out["hadith"] = [k.hadith[h] for h in a.evidence_hadith if h in k.hadith]
        out["quotes"] = [k.quotes[q] for q in a.quotes if q in k.quotes]
    if ay:
        out.update(title=f"الآية {ay.ref}", note_ar="ترجمة المعاني المعتمدة لهذه الآية.",
                   approved=ay.tr[lang])
        out["ayat"] = [{"ref": ay.ref, "ar": ay.ar, "tr": ay.tr[lang], "edition": k.editions.get(lang)}]
    return out


@app.get("/api/samples")
def samples():
    data = yaml.safe_load(open(ROOT / "samples" / "samples.yaml", encoding="utf-8"))
    return [{k: s[k] for k in ("id", "title_ar", "lang", "audience", "arabic", "translation")}
            for s in data["samples"]]


app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")
