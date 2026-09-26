"""نموذج التنبيه الموحّد الذي تُرجعه كل الفاحصات."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

TYPES = {
    1: "حمولة دينية دخيلة",
    2: "مصطلح مسيء أو مشوِّه",
    3: "اختزال مخلّ (القاعدة الذهبية)",
    4: "مخالفة منهج السلف في الصفات",
    5: "إضافة أو حذف يغيّر المعنى",
    6: "نص شرعي غير موثق",
    7: "ملاءمة الخطاب للجمهور",
}

SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


@dataclass
class Finding:
    type: int
    severity: str
    start: int            # موضع البداية في نص الترجمة (-1 إن كان التنبيه على مستوى الجملة أو النص)
    end: int
    found: str            # النص الوارد في الترجمة
    suggestion: str       # الصيغة المقترحة (من القاموس أو الترجمة المعتمدة)، أو "" إن لم يوجد مقترح موثق
    reason_ar: str
    source: str = ""
    ref_id: str = ""      # معرّف بند القاموس أو الصفة أو الآية
    rule: str = ""        # معرّف القاعدة التي أطلقت التنبيه
    replace: bool = False  # هل يصلح المقترح بديلًا مباشرًا للنص الوارد
    needs_review: bool = False
    origin: str = "rules"  # rules | llm
    sentence: int = -1
    id: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def type_name(self) -> str:
        return TYPES.get(self.type, "")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type_name"] = self.type_name
        return d
