"""الفحص الدلالي بنموذج لغوي — اختياري.

يعمل مع أي مزود يدعم صيغة OpenAI للمحادثة (/chat/completions).
الإعداد عبر متغيرات البيئة فقط، ولا يُكتب أي مفتاح في الكود:
    LLM_API_KEY    مفتاح المزود (إن غاب تعطّل هذا الفاحص وبقيت الفحوص الحتمية تعمل)
    LLM_BASE_URL   عنوان الواجهة، مثل https://api.openai.com/v1
    LLM_MODEL      اسم النموذج

قيود الموثوقية:
- لا يُقبل تنبيه إلا إذا كان النص المقتبس موجودًا حرفيًّا في الترجمة.
- لا يُقبل مقترح تصحيح إلا من القاموس (glossary_id)؛ وما سواه يُعلَّم «يحتاج مراجعة» بلا مقترح.
"""

from __future__ import annotations

import json
import os

import httpx

from amin.engine.model import Finding
from amin.glossary.loader import Knowledge

SYSTEM = """أنت مدقق شرعي للترجمات على منهج السلف الصالح. مهمتك كشف الخلل فقط، لا الترجمة ولا الفتوى.
افحص الترجمة مقابل الأصل العربي وأخرج JSON فقط بهذا الشكل:
{"findings":[{"type":5,"quote":"نص مقتبس حرفيًّا من الترجمة","issue_ar":"وصف الخلل بالعربية","glossary_id":"معرّف من القاموس أو null"}]}
الأنواع: 1 حمولة دينية دخيلة، 2 مصطلح مسيء، 3 اختزال مخل، 4 تأويل الصفات، 5 إضافة أو حذف يغير المعنى، 7 خطاب غير ملائم للجمهور.
قواعد صارمة:
- quote يجب أن يكون مقطعًا موجودًا حرفيًّا في الترجمة.
- لا تقترح ترجمة من عندك؛ اذكر glossary_id إن انطبق بند من القاموس، وإلا null.
- لا تكرر التنبيهات المذكورة في «سبق كشفه».
- إن لم تجد خللًا فأخرج {"findings":[]}.
"""


def available() -> bool:
    return bool(os.environ.get("LLM_API_KEY"))


def check_llm(k: Knowledge, arabic: str, target: str, lang: str, audience: str,
              already: list[Finding]) -> tuple[list[Finding], str | None]:
    if not available():
        return [], None
    base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    gloss = "\n".join(f"- {t.id}: {', '.join(t.ar[:3])} → {t.approved[lang]}" for t in k.terms if t.ar)
    seen = "\n".join(f"- «{f.found}»: {f.type_name}" for f in already if f.found)[:3000]
    user = (f"الجمهور المستهدف: {audience}\nلغة الترجمة: {lang}\n\nالقاموس:\n{gloss}\n\n"
            f"سبق كشفه:\n{seen or '(لا شيء)'}\n\nالأصل العربي:\n{arabic}\n\nالترجمة:\n{target}")
    try:
        r = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"},
            json={"model": model, "temperature": 0,
                  "response_format": {"type": "json_object"},
                  "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]},
            timeout=45,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        data = json.loads(content[content.find("{"): content.rfind("}") + 1])
    except Exception as e:  # نُبلغ الواجهة ولا نُسقط الفحص كله
        return [], f"تعذر الفحص الدلالي: {type(e).__name__}"

    out = []
    for item in data.get("findings", [])[:30]:
        quote = (item.get("quote") or "").strip()
        pos = target.find(quote) if quote else -1
        if pos < 0:
            continue  # اقتباس غير موجود حرفيًّا ← مرفوض
        ftype = int(item.get("type") or 5)
        if ftype not in (1, 2, 3, 4, 5, 7):
            continue
        term = k.term(item.get("glossary_id") or "") or k.attribute(item.get("glossary_id") or "")
        suggestion = term.approved[lang] if term else ""
        out.append(Finding(
            type=ftype, severity="medium", start=pos, end=pos + len(quote), found=quote,
            suggestion=suggestion, reason_ar=str(item.get("issue_ar") or "")[:500],
            source="القاموس" if term else "", ref_id=term.id if term else "",
            rule="llm", replace=bool(term) and ftype in (1, 2, 3, 4),
            needs_review=not term, origin="llm",
        ))
    return out, None
