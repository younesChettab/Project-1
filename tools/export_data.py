"""تصدير القاموس والمصادر والعينات إلى JSON لمحرك المتصفح (web/engine.js).

الاستعمال: python tools/export_data.py
"""

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from amin.engine.audience import AUDIENCES  # noqa: E402
from amin.engine.model import TYPES  # noqa: E402


def main() -> None:
    y = lambda p: yaml.safe_load(open(ROOT / p, encoding="utf-8"))  # noqa: E731
    g, q, ay, sm = y("amin/glossary/terms.yaml"), y("amin/sources/quotes.yaml"), y("amin/sources/ayat.yaml"), y("samples/samples.yaml")
    data = {
        "terms": g["terms"],
        "attributes": g["attributes"],
        "quotes": q.get("quotes", []),
        "hadith": q.get("hadith", []),
        "ayat": ay["ayat"],
        "editions": ay.get("editions", {}),
        "types": {str(k): v for k, v in TYPES.items()},
        "audiences": {k: v for k, v in AUDIENCES.items()},
        "samples": [{k: s[k] for k in ("id", "title_ar", "lang", "audience", "arabic", "translation")} for s in sm["samples"]],
    }
    out = ROOT / "web" / "data" / "knowledge.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: {out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
