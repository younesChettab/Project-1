"""تقسيم النصين إلى جمل ومحاذاتها.

المحاذاة بسيطة عمدًا: إن تساوى عدد الجمل في الأصل والترجمة قوبلت الجمل بالترتيب،
وإلا عومل النصان وحدةً واحدة. وهذا يكفي لنصوص الدعوة القصيرة ويبقي الأداة خفيفة
على الاستضافة المجانية؛ ويمكن لاحقًا استبداله بمحاذاة بالتضمينات.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# لا نقسم داخل الأقواس القرآنية ﴿…﴾ ولا علامات التنصيص «…»
_AR_END = re.compile(r"[.!؟?\n؛]+")
_TG_END = re.compile(r"(?<!\b[A-Z])(?<!\bSt)[.!?\n;]+(?=\s|$)")


@dataclass
class Span:
    text: str
    start: int
    end: int


def _split(text: str, pattern: re.Pattern, protect: tuple[tuple[str, str], ...]) -> list[Span]:
    # نحجب ما بين الأقواس المحمية حتى لا يُقسم داخله
    masked = list(text)
    for op, cl in protect:
        depth_start = None
        for i, ch in enumerate(text):
            if ch == op and depth_start is None:
                depth_start = i
            elif ch == cl and depth_start is not None:
                for j in range(depth_start + 1, i):
                    if masked[j] in ".!?؟;؛\n":
                        masked[j] = " "
                depth_start = None
    m_text = "".join(masked)
    spans, pos = [], 0
    for m in pattern.finditer(m_text):
        end = m.end()
        chunk = text[pos:end]
        if chunk.strip():
            lead = len(chunk) - len(chunk.lstrip())
            spans.append(Span(chunk.strip(), pos + lead, pos + lead + len(chunk.strip())))
        pos = end
    tail = text[pos:]
    if tail.strip():
        lead = len(tail) - len(tail.lstrip())
        spans.append(Span(tail.strip(), pos + lead, pos + lead + len(tail.strip())))
    return spans


def split_arabic(text: str) -> list[Span]:
    return _split(text, _AR_END, (("﴿", "﴾"), ("«", "»")))


def split_target(text: str) -> list[Span]:
    return _split(text, _TG_END, (("«", "»"), ("“", "”"), ('"', '"')))


def align(arabic: str, target: str) -> tuple[list[tuple[Span, Span]], bool]:
    """يرجع أزواج (جملة عربية، جملة مترجمة) ومؤشرًا على نجاح المحاذاة بالجمل."""
    a, t = split_arabic(arabic), split_target(target)
    if a and len(a) == len(t):
        return list(zip(a, t)), True
    return [(Span(arabic.strip(), 0, len(arabic)), Span(target, 0, len(target)))], False
