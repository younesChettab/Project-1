/* أمين — محرك الفحص في المتصفح.
 *
 * نقل أمين لمحرك Python (amin/engine/) ليعمل بلا خادم: الفحوص الحتمية نفسها بالقواعد نفسها،
 * على البيانات المصدّرة في web/data/knowledge.json (tools/export_data.py).
 * يُتحقق من تطابق المحركين في tests/test_js_parity.py.
 * الفحص الدلالي بالنموذج اللغوي غير متاح هنا؛ هو في نسخة الخادم فقط.
 */
(function (root) {
  "use strict";

  // ─── أدوات عامة ───
  const W = "[\\p{L}\\p{N}_]";
  // \b في JavaScript لاتيني فقط؛ نستبدل به حدًّا يعرف الحروف المشكولة كما في Python
  const UB = `(?:(?<=${W})(?!${W})|(?<!${W})(?=${W}))`;
  const convB = (p) => p.replace(/\\b/g, UB);
  const re = (p, flags) => new RegExp(convB(p), flags);
  const SEV_RANK = { high: 0, medium: 1, low: 2 };

  // ─── التطبيع ───
  const TASHKEEL = /[ؐ-ًؚ-ٰٟۖ-ۭـ]/g;
  const ALEF = /[إأآٱ]/g;
  const AR = "\\u0621-\\u064A";
  function normalizeAr(t) {
    return t.replace(TASHKEEL, "").replace(ALEF, "ا").replace(/ى/g, "ي").replace(/ة/g, "ه").replace(/ؤ/g, "و").replace(/ئ/g, "ي");
  }
  const escRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const arCache = new Map();
  function arPattern(form) {
    if (!arCache.has(form)) {
      const core = normalizeAr(form).split(/\s+/).map(escRe).join("\\s+");
      arCache.set(form, new RegExp(`(?:^|(?<=[^${AR}]))(?:[وفبلك]{0,2})(?:ال)?${core}(?:ه|ها|هم|هن|كم|كن|نا|ي|ين|ون|ات|ان|وا)?(?=$|[^${AR}])`));
    }
    return arCache.get(form);
  }
  const containsAr = (norm, forms) => forms.some((f) => arPattern(f).test(norm));

  // ─── تجهيز المعرفة ───
  const WB_L = "(?<![A-Za-zÀ-ÿĀ-ɏḀ-ỿ‘ʿ-])";
  const WB_R = "(?![A-Za-zÀ-ÿĀ-ɏḀ-ỿ-])";
  const latin = (p) => new RegExp(WB_L + "(?:" + convB(p) + ")" + WB_R, "giu");
  const LANGS = ["en", "fr"];

  function compile(data) {
    const isKfc = (s) => (s || "").includes("الهلالي") || (s || "").includes("حميد الله");
    const terms = data.terms.map((t) => ({
      id: t.id, ar: t.ar || [],
      translit: (t.translit || []).map(latin),
      gloss: Object.fromEntries(LANGS.map((l) => [l, ((t.gloss || {})[l] || []).map(latin)])),
      forbidden: Object.fromEntries(LANGS.map((l) => [l, ((t.forbidden || {})[l] || []).map(latin)])),
      forbidden_type: Number(t.forbidden_type || 1), approved: t.approved, note_ar: t.note_ar || "",
      source: t.source || "", severity: t.severity || "medium", is_global: !!t.global,
      reviewed: !!t.reviewed, kfc: isKfc(t.source), raw: t,
    }));
    const attributes = data.attributes.map((a) => ({
      id: a.id, name_ar: a.name_ar, ar: a.ar,
      tawil: Object.fromEntries(LANGS.map((l) => [l, (a.tawil[l] || []).map((p) => re(p, "giu"))])),
      approved: a.approved, evidence_ayat: a.evidence_ayat || [], evidence_hadith: a.evidence_hadith || [],
      quotes: a.quotes || [], note_ar: a.note_ar || "", severity: a.severity || "high", reviewed: !!a.reviewed,
    }));
    const ayat = data.ayat.map((x) => ({ ref: x.ref, ar: x.ar, ar_norm: normalizeAr(x.ar), tr: { en: x.en, fr: x.fr } }));
    return {
      data, terms, attributes, ayat, editions: data.editions, types: data.types, audiences: data.audiences,
      quotes: Object.fromEntries(data.quotes.map((q) => [q.id, q])),
      hadith: Object.fromEntries(data.hadith.map((h) => [h.id, h])),
      term: (id) => terms.find((t) => t.id === id), attribute: (id) => attributes.find((a) => a.id === id),
      ayah: (ref) => ayat.find((a) => a.ref === ref),
    };
  }

  function F(o) {
    return Object.assign({ source: "", ref_id: "", rule: "", replace: false, needs_review: false, origin: "rules", sentence: -1, id: "", extra: {} }, o);
  }

  // ─── التقسيم والمحاذاة ───
  const AR_END = /[.!؟?\n؛]+/g;
  const TG_END = /(?<!\b[A-Z])(?<!\bSt)[.!?\n;]+(?=\s|$)/g;
  function split(text, pattern, protect) {
    const masked = text.split("");
    for (const [op, cl] of protect) {
      let st = null;
      for (let i = 0; i < text.length; i++) {
        const ch = text[i];
        if (ch === op && st === null) st = i;
        else if (ch === cl && st !== null) {
          for (let j = st + 1; j < i; j++) if (".!?؟;؛\n".includes(masked[j])) masked[j] = " ";
          st = null;
        }
      }
    }
    const m = masked.join(""), spans = [];
    let pos = 0;
    const push = (chunk, base) => {
      if (!chunk.trim()) return;
      const lead = chunk.length - chunk.replace(/^\s+/, "").length, s = chunk.trim();
      spans.push({ text: s, start: base + lead, end: base + lead + s.length });
    };
    pattern.lastIndex = 0;
    for (const mm of m.matchAll(pattern)) { const end = mm.index + mm[0].length; push(text.slice(pos, end), pos); pos = end; }
    push(text.slice(pos), pos);
    return spans;
  }
  const splitArabic = (t) => split(t, AR_END, [["﴿", "﴾"], ["«", "»"]]);
  const splitTarget = (t) => split(t, TG_END, [["«", "»"], ["“", "”"], ['"', '"']]);
  const merge = (sp, i, j, text) => ({ text: text.slice(sp[i].start, sp[j - 1].end), start: sp[i].start, end: sp[j - 1].end });
  const sumLen = (xs) => xs.reduce((n, x) => n + x.text.length, 0);

  function dpAlign(a, t, arT, tgT) {
    const ratio = Math.max(1e-6, sumLen(t) / Math.max(1, sumLen(a)));
    const n = a.length, m = t.length;
    const cost = Array.from({ length: n + 1 }, () => Array(m + 1).fill(Infinity));
    const back = Array.from({ length: n + 1 }, () => Array(m + 1).fill(null));
    cost[0][0] = 0;
    const moves = [[1, 1, 0], [1, 2, 0.6], [2, 1, 0.6], [2, 2, 1.0]];
    for (let i = 0; i <= n; i++) for (let j = 0; j <= m; j++) {
      if (cost[i][j] === Infinity) continue;
      for (const [di, dj, pen] of moves) {
        const ni = i + di, nj = j + dj;
        if (ni > n || nj > m) continue;
        const la = sumLen(a.slice(i, ni)) * ratio, lt = sumLen(t.slice(j, nj));
        const c = cost[i][j] + Math.abs(Math.log((lt + 1) / (la + 1))) + pen;
        if (c < cost[ni][nj]) { cost[ni][nj] = c; back[ni][nj] = [i, j]; }
      }
    }
    if (cost[n][m] === Infinity) return null;
    const pairs = []; let i = n, j = m;
    while (i !== 0 || j !== 0) { const [pi, pj] = back[i][j]; pairs.push([merge(a, pi, i, arT), merge(t, pj, j, tgT)]); i = pi; j = pj; }
    return pairs.reverse();
  }

  function align(arabic, target) {
    const a = splitArabic(arabic), t = splitTarget(target);
    if (a.length && a.length === t.length) return [a.map((x, i) => [x, t[i]]), true];
    if (a.length && t.length && a.length <= 60 && t.length <= 60) { const p = dpAlign(a, t, arabic, target); if (p) return [p, true]; }
    return [[[{ text: arabic.trim(), start: 0, end: arabic.length }, { text: target, start: 0, end: target.length }]], false];
  }

  // ─── المصطلحات والقاعدة الذهبية ───
  function insideGloss(term, text, start) {
    const before = text.slice(Math.max(0, start - 40), start);
    const op = before.lastIndexOf("(");
    if (op < 0 || before.slice(op).includes(")")) return false;
    return term.translit.some((p) => { p.lastIndex = 0; return p.test(before.slice(0, op)); });
  }
  function pairedWithTranslit(term, text, start, end) {
    if (insideGloss(term, text, start)) return true;
    const after = text.slice(end, end + 30), op = after.indexOf("(");
    return op >= 0 && op <= 2 && term.translit.some((p) => { p.lastIndex = 0; return p.test(after.slice(op)); });
  }
  const LETTERS = /[^\p{L}\p{N}_À-ÿ]+/gu;
  const words = (s) => " " + s.toLowerCase().replace(LETTERS, " ").trim() + " ";
  function inApprovedQuote(K, text, start, end, lang) {
    const before = text.slice(Math.max(0, start - 60), start).toLowerCase().replace(LETTERS, " ").trim().split(/\s+/).filter(Boolean).slice(-3);
    if (before.length < 2) return false;
    const probe = " " + [...before, text.slice(start, end).toLowerCase()].join(" ") + " ";
    return K.ayat.some((ay) => words(ay.tr[lang]).includes(probe));
  }

  function checkTerms(K, pairs, target, lang) {
    const out = [];
    pairs.forEach(([ar, tg], si) => {
      const arN = normalizeAr(ar.text), seg = target.slice(tg.start, tg.end);
      for (const term of K.terms) {
        const inSrc = term.ar.length > 0 && containsAr(arN, term.ar);
        if (inSrc || term.is_global) {
          for (const pat of term.forbidden[lang]) {
            for (const m of seg.matchAll(pat)) {
              const s = tg.start + m.index, e = s + m[0].length;
              if (insideGloss(term, target, s) || inApprovedQuote(K, target, s, e, lang)) continue;
              out.push(F({ type: term.forbidden_type, severity: term.forbidden_type === 2 ? "high" : term.severity,
                start: s, end: e, found: target.slice(s, e), suggestion: term.approved[lang], reason_ar: term.note_ar,
                source: term.source, ref_id: term.id, rule: `forbidden:${term.id}`, replace: true, sentence: si }));
            }
          }
        }
        if (!inSrc) continue;
        for (const pat of term.gloss[lang]) {
          for (const m of seg.matchAll(pat)) {
            const s = tg.start + m.index, e = s + m[0].length;
            if (pairedWithTranslit(term, target, s, e)) continue;
            out.push(F({ type: 3, severity: term.severity !== "high" ? term.severity : "medium", start: s, end: e,
              found: target.slice(s, e), suggestion: term.approved[lang],
              reason_ar: "القاعدة الذهبية: يُقدَّم اللفظ الشرعي بالحروف اللاتينية ثم معناه بين قوسين. " + term.note_ar,
              source: term.source, ref_id: term.id, rule: `golden:${term.id}`, replace: true, sentence: si }));
          }
        }
      }
    });
    return out;
  }

  function checkBareTranslit(K, target, lang) {
    const out = [];
    for (const term of K.terms) {
      if (!term.approved[lang].includes("(")) continue;
      for (const pat of term.translit) {
        for (const m of target.matchAll(pat)) {
          const e = m.index + m[0].length;
          const after = target.slice(e, e + 16), before = target.slice(Math.max(0, m.index - 2), m.index);
          if (after.includes("(") || after.includes("[") || before.includes("(")) continue;
          out.push(F({ type: 3, severity: "low", start: m.index, end: e, found: m[0], suggestion: term.approved[lang],
            reason_ar: "اللفظ العربي ورد دون معناه بين قوسين؛ القارئ غير العربي قد لا يفهمه. " + term.note_ar,
            source: term.source, ref_id: term.id, rule: `bare:${term.id}`, replace: true }));
        }
      }
    }
    return out;
  }

  const NEG_AR = /(?:^|(?<=\s))[وف]?(?:لا|لم|لن|ليس|ليست|لستم|لسنا)(?=\s|$)/g;
  const NEG_T = {
    en: re("\\b(?:not|no|never|nor|none|neither|without|cannot|n['’]t|forbidden|prohibited|impermissible)\\b", "giu"),
    fr: re("(?:\\bne\\b|\\bn['’]|\\bsans\\b|\\binterdite?s?\\b)", "giu"),
  };
  const EXC_AR = /(?:^|(?<=\s))[وف]?(?:الا|سوي)(?=\s|$)/;
  const EXC_T = {
    en: re("\\b(?:except|but|only|save|unless|other than)\\b", "iu"),
    fr: re("\\b(?:sauf|excepté|hormis|seul|seulement|que|si ce n['’]est)\\b", "iu"),
  };
  const count = (s, r) => [...s.matchAll(r)].length;

  function checkOmissions(pairs, target, lang, aligned) {
    if (!aligned) return [];
    const out = [];
    pairs.forEach(([ar, tg], si) => {
      const body = normalizeAr(ar.text).replace(/﴿[^﴾]*﴾/g, " ");
      const seg = target.slice(tg.start, tg.end);
      const nAr = count(body, NEG_AR), nTg = count(seg, NEG_T[lang]);
      if (nAr > nTg) out.push(F({ type: 5, severity: "high", start: tg.start, end: tg.end, found: seg, suggestion: "",
        reason_ar: `في الأصل العربي ${nAr} من أدوات النفي أو النهي، وفي الترجمة ${nTg} فقط؛ سقوط النفي يقلب الحكم الشرعي.`,
        rule: "omission:negation", needs_review: true, sentence: si }));
      if (EXC_AR.test(body) && !EXC_T[lang].test(seg)) out.push(F({ type: 5, severity: "medium", start: tg.start, end: tg.end,
        found: seg, suggestion: "", reason_ar: "في الأصل استثناء أو حصر («إلا»)، ولا يظهر ما يقابله في الترجمة؛ قد يتسع الحكم أو يضيق.",
        rule: "omission:exception", needs_review: true, sentence: si }));
    });
    return out;
  }

  // ─── الصفات ───
  function checkAttributes(K, pairs, target, lang) {
    const out = [];
    pairs.forEach(([ar, tg], si) => {
      const arN = normalizeAr(ar.text), seg = target.slice(tg.start, tg.end);
      for (const a of K.attributes) {
        if (!containsAr(arN, a.ar)) continue;
        for (const pat of a.tawil[lang]) {
          for (const m of seg.matchAll(pat)) {
            const s = tg.start + m.index, e = s + m[0].length, ev = [...a.evidence_ayat, ...a.evidence_hadith].join(", ");
            out.push(F({ type: 4, severity: a.severity, start: s, end: e, found: target.slice(s, e), suggestion: a.approved[lang],
              reason_ar: `${a.name_ar}: ${a.note_ar}`, source: ev ? `ترجمة المعاني المعتمدة (${ev})` : "", ref_id: a.id,
              rule: `tawil:${a.id}`, replace: true, sentence: si,
              extra: { quotes: a.quotes, ayat: a.evidence_ayat, hadith: a.evidence_hadith } }));
          }
        }
      }
    });
    return out;
  }

  // ─── النصوص الشرعية ───
  const AYAH = /﴿([^﴾]+)﴾/g;
  const REF = /(?:\b\d{1,3}\s*[:：.]\s*\d{1,3}\b)|(?:\[\s*[A-Za-zÀ-ÿ'’\- ]+\s*:?\s*\d{1,3}\s*\])|(?:\b(?:surah|sourate|sura)\b)/i;
  const WORD = /[A-Za-zÀ-ÿ]+/g;
  const STOP = new Set(("the and of to a in is are was were be he his him they them their you your we our it its that this with for on as " +
    "by at from who whom which what or not nor but so then than those these there here have has had will shall may " +
    "le la les de des du un une et en est sont il ils elle elles vous nous leur leurs son sa ses que qui dans pour par sur au aux ce " +
    "cette ces ne pas se lui").split(" "));
  const HADITH_SRC_AR = /(رواه|اخرجه|متفق عليه|في الصحيحين|صحيح البخاري|صحيح مسلم)/;
  const HADITH_SRC_T = /(bukh[aā]r[iī]|muslim\b|ab[uū] d[aā]w[uū]d|tirmidh|nas[aā]['’]?[iī]|ibn m[aā]jah|ahmad|agreed upon|reported by|narrated by|rapporté|muttafaq|al-bukh)/i;
  const SALAWAT_AR = /(صلي الله عليه وسلم|ﷺ|عليه الصلاه والسلام)/;
  const SALAWAT_T = /(ﷺ|peace be upon him|pbuh|\(saw\)|s\.a\.w|salla|que la paix|paix et (le )?salut|sws|صلى)/i;
  const MESSENGER_T = re("\\b(muhammad|mohammed|messenger|prophet|proph[èe]te|messager)\\b", "iu");

  const contentWords = (s) => new Set((s.match(WORD) || []).map((w) => w.toLowerCase()).filter((w) => w.length > 2 && !STOP.has(w)));
  function similarity(a, b) {
    const A = contentWords(a), B = contentWords(b);
    if (!A.size || !B.size) return 0;
    let n = 0; A.forEach((w) => { if (B.has(w)) n++; });
    return n / Math.min(A.size, B.size);
  }
  const lettersAr = (s) => s.replace(/[^ء-ي ]/g, "").replace(/\s+/g, " ").trim();
  function matchAyah(K, qNorm) {
    const q = lettersAr(qNorm);
    if (q.length < 6) return null;
    return K.ayat.find((ay) => lettersAr(ay.ar_norm).includes(q)) || null;
  }

  function checkScripture(K, pairs, target, lang) {
    const out = [];
    pairs.forEach(([ar, tg], si) => {
      const seg = target.slice(tg.start, tg.end), arN = normalizeAr(ar.text);
      for (const m of arN.matchAll(AYAH)) {
        const ay = matchAyah(K, m[1]);
        if (ay) {
          const approved = ay.tr[lang], sim = similarity(approved, seg), hasRef = REF.test(seg);
          if (sim < 0.3) out.push(F({ type: 6, severity: "high", start: tg.start, end: tg.end, found: seg, suggestion: `${approved} [${ay.ref}]`,
            reason_ar: `الأصل يقتبس الآية (${ay.ref}) لكن الترجمة لا تقارب ترجمة المعاني المعتمدة (نسبة التقارب ${Math.round(sim * 100)}%). تُنقل الآية بترجمة معتمدة لا بصياغة حرة.`,
            source: K.editions[lang] || "", ref_id: ay.ref, rule: "ayah:free-translation", sentence: si, extra: { similarity: Math.round(sim * 100) / 100 } }));
          else if (!hasRef) out.push(F({ type: 6, severity: "low", start: tg.start, end: tg.end, found: seg, suggestion: `[${ay.ref}]`,
            reason_ar: `الآية (${ay.ref}) مترجمة دون ذكر موضعها؛ يُستحسن إثبات رقم السورة والآية ليتحقق القارئ.`,
            source: K.editions[lang] || "", ref_id: ay.ref, rule: "ayah:no-ref", sentence: si }));
        } else if (!REF.test(seg)) {
          out.push(F({ type: 6, severity: "medium", start: tg.start, end: tg.end, found: seg, suggestion: "",
            reason_ar: "في الأصل نص قرآني بين ﴿…﴾ لم نجده في مصادرنا الموثقة، والترجمة لا تذكر موضعه؛ يُراجع النص ويُعزى إلى سورته وآيته بترجمة معتمدة.",
            rule: "ayah:unknown", needs_review: true, sentence: si }));
        }
      }
      if (HADITH_SRC_AR.test(arN) && !HADITH_SRC_T.test(seg)) out.push(F({ type: 6, severity: "medium", start: tg.start, end: tg.end,
        found: seg, suggestion: "", reason_ar: "الأصل يذكر تخريج الحديث (من رواه)، والترجمة أسقطت العزو؛ العزو شرط الأمانة في نقل السنة.",
        rule: "hadith:no-source", sentence: si }));
      const mm = seg.match(MESSENGER_T);
      if (SALAWAT_AR.test(arN) && mm && !SALAWAT_T.test(seg)) {
        const s = tg.start + mm.index, e = s + mm[0].length;
        out.push(F({ type: 5, severity: "low", start: s, end: e, found: target.slice(s, e), suggestion: `${target.slice(s, e)} ﷺ`,
          reason_ar: "الأصل فيه الصلاة على النبي ﷺ وقد سقطت من الترجمة.", rule: "hadith:salawat", replace: true, sentence: si }));
      }
    });
    return out;
  }

  // ─── الجمهور ───
  const HARSH = {
    en: re("\\b(you will burn|burn forever|damned|doomed|accursed|you are (?:all )?(?:losers|misguided|ignorant)|stupid|foolish)\\b", "giu"),
    fr: re("\\b(vous brûlerez|damnés?|maudits?|vous êtes (?:tous )?(?:égarés|ignorants)|stupides?|idiots?)\\b", "giu"),
  };
  const FEAR = { en: re("\\b(hell|hellfire|torment|punishment|fire|wrath)\\b", "giu"), fr: re("\\b(enfer|châtiment|tourment|feu|colère)\\b", "giu") };
  const HOPE = {
    en: re("\\b(mercy|merciful|paradise|jannah|forgive|forgiveness|love|reward|peace)\\b", "giu"),
    fr: re("\\b(miséricorde|miséricordieux|paradis|pardon|pardonne|amour|récompense|paix)\\b", "giu"),
  };
  const ABSOLUTE = {
    en: re("\\b(obviously|everyone knows|undeniably|without any doubt|clearly proves|it is self-evident)\\b", "giu"),
    fr: re("\\b(évidemment|tout le monde sait|indéniablement|sans aucun doute|prouve clairement)\\b", "giu"),
  };
  const WORDS = /[A-Za-zÀ-ÿ'’-]+/g;

  function checkAudience(K, target, lang, audience) {
    const prof = K.audiences[audience] || K.audiences.general;
    const sents = splitTarget(target);
    const lens = sents.length ? sents.map((s) => (s.text.match(WORDS) || []).length) : [0];
    const avg = lens.reduce((a, b) => a + b, 0) / lens.length;
    const out = [];
    sents.forEach((s, i) => {
      if (lens[i] > prof.max_len) out.push(F({ type: 7, severity: "low", start: s.start, end: s.end, found: s.text, suggestion: "",
        reason_ar: `الجملة طويلة (${lens[i]} كلمة) على جمهور «${prof.name_ar}»؛ يُستحسن تقسيمها إلى جمل أقصر.`, rule: "audience:long-sentence", sentence: i }));
    });
    if (["non_muslims", "new_muslims", "children", "general"].includes(audience)) {
      for (const m of target.matchAll(HARSH[lang])) out.push(F({ type: 7, severity: "medium", start: m.index, end: m.index + m[0].length, found: m[0],
        suggestion: "", reason_ar: "عبارة جارحة أو منفّرة للمخاطَب؛ والله أمر بالحكمة والموعظة الحسنة والجدال بالتي هي أحسن [النحل: 125].",
        rule: "audience:harsh", needs_review: true }));
    }
    const fear = count(target, FEAR[lang]), hope = count(target, HOPE[lang]);
    if (["children", "new_muslims", "non_muslims"].includes(audience) && fear >= 2 && fear > hope * 2) out.push(F({ type: 7, severity: "low",
      start: -1, end: -1, found: "", suggestion: "",
      reason_ar: `غلب على النص الترهيب (${fear} موضعًا) على الترغيب (${hope})؛ ويُستحسن لجمهور «${prof.name_ar}» الموازنة بينهما وتقديم الرحمة.`,
      rule: "audience:fear-balance" }));
    if (audience === "academics") {
      for (const m of target.matchAll(ABSOLUTE[lang])) out.push(F({ type: 7, severity: "low", start: m.index, end: m.index + m[0].length,
        found: m[0], suggestion: "", reason_ar: "الجمهور الأكاديمي والفلسفي يُقنعه الدليل المرتّب لا عبارات القطع الإنشائية؛ يُستبدل بها عرض الحجة.",
        rule: "audience:absolute" }));
      if ((target.match(/!/g) || []).length >= 2) out.push(F({ type: 7, severity: "low", start: -1, end: -1, found: "", suggestion: "",
        reason_ar: "كثرة علامات التعجب تُضعف الطابع البرهاني للنص عند الجمهور الأكاديمي.", rule: "audience:exclamations" }));
    }
    return [out, { audience, audience_name_ar: prof.name_ar, sentences: sents.length, avg_sentence_words: Math.round(avg * 10) / 10,
      max_sentence_words: Math.max(...lens), fear_mentions: fear, hope_mentions: hope }];
  }

  // ─── خط الفحص ───
  const FR_HINT = re("\\b(le|la|les|des|est|et|dans|qui|que|pour|une|du|au|aux|sont|leur|nous|vous)\\b", "giu");
  const EN_HINT = re("\\b(the|and|is|are|of|to|who|which|that|for|with|they|their|we|you)\\b", "giu");
  const detectLang = (t) => (count(t, FR_HINT) > count(t, EN_HINT) ? "fr" : "en");
  const WIDE = /^(omission|ayah|hadith:no-source|audience:long)/;
  const overlaps = (a, b) => a.start >= 0 && b.start >= 0 && a.start < b.end && b.start < a.end;

  function dedupe(fs) {
    const prio = { 4: 0, 2: 1, 6: 2, 1: 3, 5: 4, 3: 5, 7: 6 };
    const ordered = fs.map((f, i) => [f, i]).sort((x, y) => {
      const a = x[0], b = y[0];
      return (SEV_RANK[a.severity] - SEV_RANK[b.severity]) || ((prio[a.type] ?? 9) - (prio[b.type] ?? 9)) ||
        ((b.end - b.start) - (a.end - a.start)) || (x[1] - y[1]);
    }).map((x) => x[0]);
    const kept = [];
    for (const f of ordered) {
      const wide = WIDE.test(f.rule);
      if (!wide && kept.some((g) => overlaps(f, g) && !WIDE.test(g.rule))) continue;
      if (kept.some((g) => f.rule === g.rule && f.start === g.start && f.end === g.end)) continue;
      kept.push(f);
    }
    return kept;
  }

  function run(K, arabic, translation, lang, audience) {
    audience = audience || "general";
    lang = lang === "en" || lang === "fr" ? lang : detectLang(translation);
    const [pairs, aligned] = align(arabic, translation);
    let fs = [];
    fs = fs.concat(checkAttributes(K, pairs, translation, lang));
    fs = fs.concat(checkTerms(K, pairs, translation, lang));
    fs = fs.concat(checkBareTranslit(K, translation, lang));
    fs = fs.concat(checkScripture(K, pairs, translation, lang));
    fs = fs.concat(checkOmissions(pairs, translation, lang, aligned));
    const [aud, audReport] = checkAudience(K, translation, lang, audience);
    fs = fs.concat(aud);
    return finalize(K, { lang, aligned, pairs, audReport }, fs);
  }

  // يزيل التكرار ويرتب ويرقّم ويحسب الإحصاءات — يُستعمل أيضًا لدمج تنبيهات الفحص الدلالي
  function finalize(K, ctx, fs) {
    fs = dedupe(fs).map((f, i) => [f, i]).sort((x, y) => {
      const a = x[0], b = y[0];
      return ((a.start >= 0 ? a.start : 1e9) - (b.start >= 0 ? b.start : 1e9)) || (SEV_RANK[a.severity] - SEV_RANK[b.severity]) || (x[1] - y[1]);
    }).map((x) => x[0]);
    fs.forEach((f, i) => { f.id = `f${i + 1}`; f.type_name = K.types[String(f.type)] || ""; });
    const byType = Object.fromEntries(Object.keys(K.types).map((t) => [t, 0]));
    fs.forEach((f) => { byType[String(f.type)]++; });
    return {
      lang: ctx.lang, aligned: ctx.aligned,
      sentences: ctx.aligned ? ctx.pairs.map(([a, t]) => ({ ar: a.text, tr: t.text, start: t.start, end: t.end })) : [],
      findings: fs,
      stats: { total: fs.length, by_type: byType,
        by_severity: Object.fromEntries(Object.keys(SEV_RANK).map((s) => [s, fs.filter((f) => f.severity === s).length])),
        needs_review: fs.filter((f) => f.needs_review).length },
      types: K.types, audience: ctx.audReport, llm: { available: false, used: false, error: null },
      _ctx: ctx,
    };
  }

  // ─── الفحص الدلالي (اختياري) — نفس قيود نسخة الخادم (amin/engine/llm.py) ───
  const LLM_SYSTEM = `أنت مدقق شرعي للترجمات على منهج السلف الصالح. مهمتك كشف الخلل فقط، لا الترجمة ولا الفتوى.
افحص الترجمة مقابل الأصل العربي وأخرج JSON فقط بهذا الشكل:
{"findings":[{"type":5,"quote":"نص مقتبس حرفيًّا من الترجمة","issue_ar":"وصف الخلل بالعربية","glossary_id":"معرّف من القاموس أو null"}]}
الأنواع: 1 حمولة دينية دخيلة، 2 مصطلح مسيء، 3 اختزال مخل، 4 تأويل الصفات، 5 إضافة أو حذف يغير المعنى، 7 خطاب غير ملائم للجمهور.
قواعد صارمة:
- quote يجب أن يكون مقطعًا موجودًا حرفيًّا في الترجمة.
- لا تقترح ترجمة من عندك؛ اذكر glossary_id إن انطبق بند من القاموس، وإلا null.
- لا تكرر التنبيهات المذكورة في «سبق كشفه».
- إن لم تجد خللًا فأخرج {"findings":[]}.`;

  function llmPrompt(K, arabic, target, result, audience) {
    const lang = result.lang;
    const gloss = K.terms.filter((t) => t.ar.length).map((t) => `- ${t.id}: ${t.ar.slice(0, 3).join(", ")} → ${t.approved[lang]}`).join("\n");
    const seen = result.findings.filter((f) => f.found).map((f) => `- «${f.found}»: ${f.type_name}`).join("\n").slice(0, 3000);
    return `${LLM_SYSTEM}\n\nالجمهور المستهدف: ${audience}\nلغة الترجمة: ${lang}\n\nالقاموس:\n${gloss}\n\nسبق كشفه:\n${seen || "(لا شيء)"}\n\nالأصل العربي:\n${arabic}\n\nالترجمة:\n${target}`;
  }

  function mergeLlm(K, result, target, data) {
    const lang = result.lang, extra = [];
    for (const item of ((data && data.findings) || []).slice(0, 30)) {
      const quote = String(item.quote || "").trim();
      const pos = quote ? target.indexOf(quote) : -1;
      if (pos < 0) continue; // اقتباس غير موجود حرفيًّا ← مرفوض
      const type = Number(item.type || 5);
      if (![1, 2, 3, 4, 5, 7].includes(type)) continue;
      const gid = String(item.glossary_id || "");
      const term = K.term(gid) || K.attribute(gid);
      extra.push(F({ type, severity: "medium", start: pos, end: pos + quote.length, found: quote,
        suggestion: term ? term.approved[lang] : "", reason_ar: String(item.issue_ar || "").slice(0, 500),
        source: term ? "القاموس" : "", ref_id: term ? term.id : "", rule: "llm",
        replace: !!term && [1, 2, 3, 4].includes(type), needs_review: !term, origin: "llm" }));
    }
    const base = result.findings.map((f) => Object.assign({}, f));
    const out = finalize(K, result._ctx, base.concat(extra));
    out.llm = { available: true, used: true, error: null };
    return out;
  }

  function explain(K, refId, lang) {
    lang = lang === "fr" ? "fr" : "en";
    const t = K.term(refId), a = K.attribute(refId), ay = K.ayah(refId);
    if (!(t || a || ay)) return null;
    const out = { id: refId, ayat: [], hadith: [], quotes: [], reviewed: null, kfc: false };
    if (t) Object.assign(out, { title: t.id, note_ar: t.note_ar, approved: t.approved[lang], source: t.source, reviewed: t.reviewed, kfc: t.kfc });
    if (a) {
      Object.assign(out, { title: a.name_ar, note_ar: a.note_ar, approved: a.approved[lang], reviewed: a.reviewed, kfc: a.evidence_ayat.length > 0 });
      out.ayat = a.evidence_ayat.map((r) => K.ayah(r)).filter(Boolean).map((x) => ({ ref: x.ref, ar: x.ar, tr: x.tr[lang], edition: K.editions[lang] }));
      out.hadith = a.evidence_hadith.map((h) => K.hadith[h]).filter(Boolean);
      out.quotes = a.quotes.map((q) => K.quotes[q]).filter(Boolean);
    }
    if (ay) {
      Object.assign(out, { title: `الآية ${ay.ref}`, note_ar: "ترجمة المعاني المعتمدة لهذه الآية.", approved: ay.tr[lang], kfc: true });
      out.ayat = [{ ref: ay.ref, ar: ay.ar, tr: ay.tr[lang], edition: K.editions[lang] }];
    }
    return out;
  }

  function human(p) {
    return p.replace(/\(\?:/g, "(").replace(/\[([^\]])[^\]]*\]/g, "$1").replace(/\((?:s|es|e|ies)\)\??|(?<=\w)\?/g, "")
      .replace(/\\s\+?/g, " ").replace(/\\b/g, "").replace(/\(([^()]*)\)/g, (_, g) => g.split("|")[0]).replace(/\|/g, " / ").trim();
  }

  function glossary(K, feedback) {
    const fb = feedback || {};
    return {
      terms: K.terms.map((t) => ({ id: t.id, ar: t.ar, approved: t.approved, note_ar: t.note_ar, source: t.source, severity: t.severity,
        reviewed: t.reviewed, kfc: t.kfc, forbidden: Object.fromEntries(LANGS.map((l) => [l, ((t.raw.forbidden || {})[l] || []).map(human)])),
        feedback: fb[t.id] || null })),
      attributes: K.attributes.map((a) => ({ id: a.id, name_ar: a.name_ar, ar: a.ar, approved: a.approved, note_ar: a.note_ar,
        ayat: a.evidence_ayat, hadith: a.evidence_hadith, reviewed: a.reviewed, kfc: true, feedback: fb[a.id] || null })),
    };
  }

  const api = { compile, run, explain, glossary, normalizeAr, align, llmPrompt, mergeLlm };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.AminEngine = api;
})(typeof self !== "undefined" ? self : this);
