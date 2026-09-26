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


def _merge(spans: list[Span], i: int, j: int, text: str) -> Span:
    return Span(text[spans[i].start:spans[j - 1].end], spans[i].start, spans[j - 1].end)


def _dp_align(a: list[Span], t: list[Span], ar_text: str, tg_text: str) -> list[tuple[Span, Span]] | None:
    """محاذاة بالبرمجة الديناميكية على طول الجمل (على طريقة Gale-Church مبسطة).

    تسمح بالمطابقات 1-1 و1-2 و2-1 و2-2، بكلفة هي انحراف نسبة الطول عن النسبة العامة للنصين.
    """
    import math

    ratio = max(1e-6, sum(len(x.text) for x in t) / max(1, sum(len(x.text) for x in a)))
    n, m = len(a), len(t)
    INF = float("inf")
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple[int, int] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0
    moves = ((1, 1, 0.0), (1, 2, 0.6), (2, 1, 0.6), (2, 2, 1.0))
    for i in range(n + 1):
        for j in range(m + 1):
            if cost[i][j] == INF:
                continue
            for di, dj, pen in moves:
                ni, nj = i + di, j + dj
                if ni > n or nj > m:
                    continue
                la = sum(len(x.text) for x in a[i:ni]) * ratio
                lt = sum(len(x.text) for x in t[j:nj])
                c = cost[i][j] + abs(math.log((lt + 1) / (la + 1))) + pen
                if c < cost[ni][nj]:
                    cost[ni][nj], back[ni][nj] = c, (i, j)
    if cost[n][m] == INF:
        return None
    pairs, i, j = [], n, m
    while (i, j) != (0, 0):
        pi, pj = back[i][j]
        pairs.append((_merge(a, pi, i, ar_text), _merge(t, pj, j, tg_text)))
        i, j = pi, pj
    return pairs[::-1]


def align(arabic: str, target: str) -> tuple[list[tuple[Span, Span]], bool]:
    """يرجع أزواج (جملة عربية، جملة مترجمة) ومؤشرًا على نجاح المحاذاة بالجمل.

    - إن تساوى عدد الجمل قوبلت بالترتيب.
    - وإلا جُرّبت المحاذاة الديناميكية على الطول (حتى 60 جملة).
    - وإن تعذر ذلك عومل النصان وحدةً واحدة.
    """
    a, t = split_arabic(arabic), split_target(target)
    if a and len(a) == len(t):
        return list(zip(a, t)), True
    if a and t and len(a) <= 60 and len(t) <= 60:
        pairs = _dp_align(a, t, arabic, target)
        if pairs:
            return pairs, True
    return [(Span(arabic.strip(), 0, len(arabic)), Span(target, 0, len(target)))], False
