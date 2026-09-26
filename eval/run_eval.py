"""قياس أداء «أمين» على مجموعة الاختبار ذات الأخطاء المزروعة.

الاستعمال:
    python eval/run_eval.py              # الفحص الحتمي وحده
    python eval/run_eval.py --llm        # مع الفحص الدلالي (يتطلب LLM_API_KEY)
    python eval/run_eval.py --json out.json

المنهجية:
- كل عينة تحمل قائمة «expected» بالأخطاء المزروعة (بمعرّف القاعدة).
- تنبيه صحيح (TP): تنبيه قاعدته من المتوقع (يُستهلك كل متوقع مرة واحدة).
- إنذار كاذب (FP): تنبيه خارج المتوقع. تنبيهات الجمهور (النوع 7) تُعرض منفصلة لأنها توصيات أسلوبية لا أخطاء.
- خطأ فائت (FN): متوقع لم يُكشف.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from amin.engine.pipeline import run  # noqa: E402


def evaluate(use_llm: bool = False) -> dict:
    data = yaml.safe_load(open(ROOT / "samples" / "samples.yaml", encoding="utf-8"))
    rows, tp, fp, fn, style = [], 0, 0, 0, 0
    per_rule = Counter()
    for s in data["samples"]:
        r = run(s["arabic"], s["translation"], s["lang"], s["audience"], use_llm=use_llm)
        expected = Counter(e["rule"] for e in s["expected"])
        got = [f for f in r["findings"] if f["type"] != 7]
        style += sum(1 for f in r["findings"] if f["type"] == 7)
        remaining = expected.copy()
        s_tp, s_fp = 0, []
        for f in got:
            if remaining[f["rule"]] > 0:
                remaining[f["rule"]] -= 1
                s_tp += 1
                per_rule[f["rule"].split(":")[0]] += 1
            else:
                s_fp.append(f"{f['rule']} «{f['found'][:40]}»")
        s_fn = [rule for rule, n in remaining.items() for _ in range(n)]
        tp, fp, fn = tp + s_tp, fp + len(s_fp), fn + len(s_fn)
        rows.append({"sample": s["id"], "expected": sum(expected.values()), "tp": s_tp,
                     "fp": s_fp, "fn": s_fn})
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(precision, 3), "recall": round(recall, 3),
            "style_notes": style, "samples": rows, "llm": use_llm}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    res = evaluate(a.llm)
    print(f"\nأمين — نتائج التقييم ({'مع' if a.llm else 'دون'} النموذج اللغوي)")
    print("─" * 60)
    for r in res["samples"]:
        print(f"{r['sample']:10}  متوقع {r['expected']:2}  صحيح {r['tp']:2}  كاذب {len(r['fp']):2}  فائت {len(r['fn']):2}")
        for x in r["fp"]:
            print(f"    ✗ إنذار كاذب: {x}")
        for x in r["fn"]:
            print(f"    ○ فائت: {x}")
    print("─" * 60)
    print(f"الدقة (Precision): {res['precision']:.1%}   الاستدعاء (Recall): {res['recall']:.1%}")
    print(f"ملاحظات أسلوبية للجمهور (غير محتسبة): {res['style_notes']}")
    if a.json:
        Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
