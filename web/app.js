/* أمين — منطق الواجهة. لا مكتبات خارجية. */
(() => {
  "use strict";

  const $ = (s, el = document) => el.querySelector(s);
  const TYPE_COLOR = (t) => `var(--t${t})`;
  const SEV_AR = { high: "خطير", medium: "متوسط", low: "تحسين" };
  const WIDE = /^(omission|ayah|hadith:no-source|audience:long)/;
  const AR_DIGITS = (n) => String(n).replace(/\d/g, (d) => "٠١٢٣٤٥٦٧٨٩"[d]).replace(".", "٫");

  const state = {
    meta: null, samples: [], result: null, translation: "", arabic: "",
    decisions: {},           // id → "accepted" | "rejected"
    filter: null,            // نوع مصفّى أو null
    open: new Set(),         // بطاقات «البيان» المفتوحة
  };

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const isWide = (f) => f.start < 0 || WIDE.test(f.rule);

  async function api(path, opts) {
    const r = await fetch(path, opts);
    if (!r.ok) {
      let msg = `خطأ ${r.status}`;
      try { msg = (await r.json()).detail || msg; } catch (_) { /* نص غير JSON */ }
      throw new Error(typeof msg === "string" ? msg : "تعذر الطلب");
    }
    return r.json();
  }

  function setStep(n) {
    document.querySelectorAll(".step").forEach((s) => s.classList.toggle("is-on", Number(s.dataset.step) <= n));
  }

  // ───────── الإعداد ─────────
  async function init() {
    try {
      const [meta, samples] = await Promise.all([api("/api/meta"), api("/api/samples")]);
      state.meta = meta; state.samples = samples;
    } catch (e) {
      showErr("تعذر الاتصال بالخادم: " + e.message); return;
    }
    $("#audiences").innerHTML = Object.entries(state.meta.audiences).map(([k, v], i) =>
      `<label class="tile"><input type="radio" name="aud" value="${k}" ${i === 0 ? "checked" : ""}><span>${esc(v)}</span></label>`).join("");
    $("#samples").innerHTML = state.samples.map((s) =>
      `<button type="button" class="chip" data-id="${s.id}">${esc(s.title_ar)}</button>`).join("");
    $("#llm-toggle").hidden = !state.meta.llm;
    $("#samples").addEventListener("click", (e) => {
      const b = e.target.closest(".chip"); if (!b) return;
      const s = state.samples.find((x) => x.id === b.dataset.id);
      $("#arabic").value = s.arabic.trim(); $("#translation").value = s.translation.trim();
      const lr = document.querySelector(`input[name=lang][value="${s.lang}"]`); if (lr) lr.checked = true;
      const ar = document.querySelector(`input[name=aud][value="${s.audience}"]`); if (ar) ar.checked = true;
    });
    $("#run").addEventListener("click", runCheck);
    $("#accept-all").addEventListener("click", () => {
      state.result.findings.forEach((f) => { if (f.replace && f.suggestion && !f.needs_review) state.decisions[f.id] = "accepted"; });
      renderAll();
    });
    $("#reset-all").addEventListener("click", () => { state.decisions = {}; renderAll(); });
    $("#copy").addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(corrected().text); flash($("#copy"), "نُسخ ✓"); } catch (_) { flash($("#copy"), "تعذر النسخ"); }
    });
    $("#export-json").addEventListener("click", exportJSON);
    $("#export-html").addEventListener("click", exportHTML);
    $("#print").addEventListener("click", () => window.print());
  }

  function flash(btn, txt) { const o = btn.textContent; btn.textContent = txt; setTimeout(() => (btn.textContent = o), 1400); }
  function showErr(m) { const e = $("#err"); e.textContent = m; e.hidden = !m; }

  // ───────── الفحص ─────────
  async function runCheck() {
    showErr("");
    const arabic = $("#arabic").value, translation = $("#translation").value;
    if (!arabic.trim() || !translation.trim()) { showErr("أدخل الأصل العربي والترجمة معًا."); return; }
    const btn = $("#run"); btn.disabled = true; btn.textContent = "جارٍ الفحص…";
    try {
      const res = await api("/api/check", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          arabic, translation,
          lang: document.querySelector("input[name=lang]:checked").value || null,
          audience: document.querySelector("input[name=aud]:checked").value,
          use_llm: $("#use-llm").checked,
        }),
      });
      Object.assign(state, { result: res, translation, arabic, decisions: {}, filter: null, open: new Set() });
      $("#report").hidden = false; $("#corrected-sec").hidden = false;
      renderAll(); setStep(2);
      $("#report").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      showErr("تعذر الفحص: " + e.message);
    } finally {
      btn.disabled = false; btn.textContent = "افحص الترجمة";
    }
  }

  // ───────── العرض ─────────
  function renderAll() { renderSummary(); renderMarked(); renderCards(); renderAudience(); renderCorrected(); }

  function renderSummary() {
    const r = state.result, st = r.stats;
    $("#total").textContent = AR_DIGITS(st.total);
    const lang = r.lang === "fr" ? "الفرنسية" : "الإنجليزية";
    const llm = r.llm.used ? "مع الفحص الدلالي" : (r.llm.error ? `دون الفحص الدلالي (${esc(r.llm.error)})` : "بالفحص الحتمي");
    $("#summary-line").innerHTML =
      `ترجمة <b>${lang}</b> · خطير <b>${AR_DIGITS(st.by_severity.high)}</b> · متوسط <b>${AR_DIGITS(st.by_severity.medium)}</b> · تحسين <b>${AR_DIGITS(st.by_severity.low)}</b>` +
      ` · يحتاج مراجعة بشرية <b>${AR_DIGITS(st.needs_review)}</b> · ${llm}` +
      (r.aligned ? "" : ` · <span class="pending">تعذرت المحاذاة جملةً بجملة، ففُحص النص كاملًا</span>`);
    $("#type-tiles").innerHTML = Object.entries(r.types).map(([t, name]) => {
      const n = st.by_type[t] || 0;
      return `<button type="button" class="ttile ${n ? "" : "zero"}" style="--c:${TYPE_COLOR(t)}" data-t="${t}" aria-pressed="${state.filter === Number(t)}">
        <span class="dia"></span>${esc(name)} <b>${AR_DIGITS(n)}</b></button>`;
    }).join("");
    $("#type-tiles").onclick = (e) => {
      const b = e.target.closest(".ttile"); if (!b) return;
      const t = Number(b.dataset.t); state.filter = state.filter === t ? null : t; renderAll();
    };
  }

  function visible(f) { return state.filter === null || f.type === state.filter; }

  function renderMarked() {
    const text = state.translation, fs = state.result.findings;
    const inline = fs.filter((f) => !isWide(f)).sort((a, b) => a.start - b.start);
    const wides = fs.filter((f) => isWide(f) && f.start >= 0);
    // نقاط إدراج شارات التنبيهات الواسعة عند نهاية جملها
    const tail = {};
    wides.forEach((f) => { (tail[f.end] ||= []).push(f); });
    let html = "", pos = 0;
    const flushTo = (end) => {
      while (pos < end) {
        const next = Object.keys(tail).map(Number).filter((k) => k > pos && k <= end).sort((a, b) => a - b)[0];
        const stop = next ?? end;
        html += esc(text.slice(pos, stop)); pos = stop;
        if (next !== undefined) { tail[next].forEach((w) => (html += badge(w))); delete tail[next]; }
      }
    };
    for (const f of inline) {
      if (f.start < pos) continue;
      flushTo(f.start);
      const d = state.decisions[f.id];
      html += `<mark class="${d ? "is-" + d : ""} ${visible(f) ? "" : "is-dim"}" style="--c:${TYPE_COLOR(f.type)}" data-id="${f.id}" title="${esc(f.type_name)}">${esc(text.slice(f.start, f.end))}</mark>${badge(f)}`;
      pos = f.end;
    }
    flushTo(text.length);
    Object.values(tail).flat().forEach((w) => (html += badge(w)));
    $("#marked").innerHTML = html;
    $("#marked").onclick = (e) => {
      const m = e.target.closest("[data-id]"); if (!m) return;
      const card = document.getElementById("card-" + m.dataset.id);
      if (card) { card.scrollIntoView({ behavior: "smooth", block: "center" }); card.classList.add("is-focus"); setTimeout(() => card.classList.remove("is-focus"), 1600); }
    };
  }

  function badge(f) {
    return `<span class="badge" style="--c:${TYPE_COLOR(f.type)}" data-id="${f.id}" title="${esc(f.type_name)}">${AR_DIGITS(f.id.slice(1))}</span>`;
  }

  function renderCards() {
    const fs = state.result.findings.filter(visible);
    if (!state.result.findings.length) {
      $("#cards").innerHTML = `<div class="empty">لم يُعثر على مواضع تخالف القاموس والمصادر المعتمدة. يبقى نظر المراجع الشرعي هو الحَكَم.</div>`;
      return;
    }
    $("#cards").innerHTML = fs.map(cardHTML).join("");
    $("#cards").onclick = onCardClick;
    state.open.forEach((id) => loadBayan(id));
  }

  function cardHTML(f) {
    const d = state.decisions[f.id];
    const canApply = f.replace && f.suggestion;
    const found = f.found.length > 160 ? f.found.slice(0, 160) + "…" : f.found;
    const flags = [
      f.needs_review ? `<span class="flag">يحتاج مراجعة بشرية</span>` : "",
      f.origin === "llm" ? `<span class="flag ai">من الفحص الدلالي</span>` : "",
    ].join("");
    return `
    <article class="card ${d ? "is-" + d : ""}" id="card-${f.id}" style="--c:${TYPE_COLOR(f.type)}">
      <div class="card-top">
        <span class="num">${AR_DIGITS(f.id.slice(1))}</span>
        <span class="tname">${esc(f.type_name)}</span>
        <span class="sev sev-${f.severity}">${SEV_AR[f.severity]}</span>
      </div>
      <div class="card-body">
        <dl class="pair">
          ${found ? (isWide(f) ? `<dt>الجملة</dt><dd class="ctx">${esc(found)}</dd>` : `<dt>الوارد</dt><dd class="was">${esc(found)}</dd>`) : ""}
          <dt>المقترح</dt>
          ${f.suggestion ? `<dd class="now">${esc(f.suggestion)}</dd>` : `<dd class="now none">لا مقترح آلي — يُحال إلى المراجع</dd>`}
        </dl>
        <p class="reason">${esc(f.reason_ar)}</p>
        ${f.source ? `<p class="src">المرجع: ${esc(f.source)}</p>` : ""}
        ${flags ? `<div class="flags">${flags}</div>` : ""}
      </div>
      <div class="card-actions">
        ${canApply ? `<button type="button" class="act ok" data-act="accepted" data-id="${f.id}" aria-pressed="${d === "accepted"}">✓ قبول</button>` : ""}
        <button type="button" class="act no" data-act="rejected" data-id="${f.id}" aria-pressed="${d === "rejected"}">✗ ${canApply ? "رفض" : "تجاهل"}</button>
        ${f.ref_id ? `<button type="button" class="act bayan" data-bayan="${f.id}" aria-expanded="${state.open.has(f.id)}" aria-controls="bayan-${f.id}">البيان</button>` : ""}
      </div>
      <div class="bayan-slot" id="bayan-${f.id}"></div>
    </article>`;
  }

  function onCardClick(e) {
    const a = e.target.closest("[data-act]");
    if (a) {
      const id = a.dataset.id, v = a.dataset.act;
      state.decisions[id] = state.decisions[id] === v ? undefined : v;
      if (!state.decisions[id]) delete state.decisions[id];
      renderMarked(); renderCorrected();
      const card = document.getElementById("card-" + id);
      card.outerHTML = cardHTML(state.result.findings.find((f) => f.id === id));
      if (state.open.has(id)) loadBayan(id);
      if (Object.keys(state.decisions).length) setStep(3);
      return;
    }
    const b = e.target.closest("[data-bayan]");
    if (b) {
      const id = b.dataset.bayan;
      if (state.open.has(id)) { state.open.delete(id); $("#bayan-" + id).innerHTML = ""; b.setAttribute("aria-expanded", "false"); }
      else { state.open.add(id); b.setAttribute("aria-expanded", "true"); loadBayan(id); }
    }
  }

  const bayanCache = {};
  async function loadBayan(id) {
    const f = state.result.findings.find((x) => x.id === id);
    const slot = $("#bayan-" + id); if (!f || !slot) return;
    const key = f.ref_id + ":" + state.result.lang;
    slot.innerHTML = `<div class="bayan-panel">جارٍ جلب البيان…</div>`;
    try {
      const b = bayanCache[key] ||= await api(`/api/explain/${encodeURIComponent(f.ref_id)}?lang=${state.result.lang}`);
      slot.innerHTML = bayanHTML(b);
    } catch (e) {
      slot.innerHTML = `<div class="bayan-panel">لا بيان متاح لهذا البند بعد.</div>`;
    }
  }

  function bayanHTML(b) {
    const parts = [];
    parts.push(`<section><h4>${esc(b.title || "البيان")}</h4><p>${esc(b.note_ar || "")}</p>
      ${b.approved ? `<p class="bayan-tr">${esc(b.approved)}</p>` : ""}
      ${b.source ? `<p class="bayan-cite">المرجع: ${esc(b.source)}</p>` : ""}
      ${b.kfc ? `<p class="approved-kfc">◆ المقابل معتمد وفق ترجمة معاني القرآن الصادرة عن مجمع الملك فهد.</p>`
        : (b.reviewed === false ? `<p class="pending">◆ هذا البند بانتظار اعتماد المراجع الشرعي.</p>` : "")}</section>`);
    if (b.ayat?.length) parts.push(`<section><h4>من ترجمة المعاني المعتمدة</h4>${b.ayat.map((a) =>
      `<p class="bayan-ayah">﴿${esc(a.ar)}﴾ <small>[${esc(a.ref)}]</small></p><p class="bayan-tr">${esc(a.tr)}</p><p class="bayan-cite">${esc(a.edition || "")}</p>`).join("")}</section>`);
    if (b.hadith?.length) parts.push(`<section><h4>من السنة</h4>${b.hadith.map((h) =>
      `<p class="bayan-ayah">«${esc(h.ar)}»</p><p class="bayan-cite">${esc(h.collection)} (${esc(h.number)}) — ${esc(h.grade)} · <a href="${esc(h.link)}" target="_blank" rel="noopener">المصدر</a></p>`).join("")}</section>`);
    if (b.quotes?.length) parts.push(`<section><h4>من كلام أهل العلم</h4>${b.quotes.map((q) =>
      `<p class="bayan-quote">${esc(q.text)}</p><p class="bayan-cite">${esc(q.author)}، «${esc(q.book)}» ${esc(q.locator)} · <a href="${esc(q.link)}" target="_blank" rel="noopener">النص في مصدره</a></p>`).join("")}</section>`);
    if (!b.quotes?.length && !b.ayat?.length && !b.hadith?.length) parts.push(`<section><p class="bayan-cite">لا نقل موثق بعد لهذا البند.</p></section>`);
    return `<div class="bayan-panel">${parts.join("")}</div>`;
  }

  function renderAudience() {
    const a = state.result.audience;
    $("#audience-report").innerHTML = [
      [a.audience_name_ar, "الجمهور المختار"],
      [AR_DIGITS(a.avg_sentence_words), "متوسط كلمات الجملة"],
      [AR_DIGITS(a.max_sentence_words), "أطول جملة (كلمة)"],
      [`${AR_DIGITS(a.hope_mentions)} / ${AR_DIGITS(a.fear_mentions)}`, "ترغيب / ترهيب"],
    ].map(([v, l]) => `<div class="metric"><b>${esc(v)}</b><span>${l}</span></div>`).join("");
  }

  // يطبق المقترحات المقبولة من آخر النص إلى أوله (نفس منطق الخادم)
  function corrected() {
    const t = state.translation;
    const chosen = state.result.findings
      .filter((f) => state.decisions[f.id] === "accepted" && f.replace && f.start >= 0 && f.suggestion)
      .sort((a, b) => b.start - a.start);
    let out = t, last = t.length + 1; const spans = [];
    for (const f of chosen) {
      if (f.end > last) continue;
      out = out.slice(0, f.start) + f.suggestion + out.slice(f.end);
      spans.forEach((s) => { s.start += f.suggestion.length - (f.end - f.start); });
      spans.push({ start: f.start, end: f.start + f.suggestion.length });
      last = f.start;
    }
    return { text: out, spans: spans.sort((a, b) => a.start - b.start) };
  }

  function renderCorrected() {
    const { text, spans } = corrected();
    let html = "", pos = 0;
    spans.forEach((s) => { html += esc(text.slice(pos, s.start)) + `<ins>${esc(text.slice(s.start, s.end))}</ins>`; pos = s.end; });
    html += esc(text.slice(pos));
    $("#corrected").innerHTML = html;
  }

  // ───────── التصدير ─────────
  function download(name, content, type) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([content], { type }));
    a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  function reportData() {
    return {
      tool: "Amin — أمين", generated: new Date().toISOString(),
      lang: state.result.lang, audience: state.result.audience,
      arabic: state.arabic, translation: state.translation, corrected: corrected().text,
      stats: state.result.stats,
      findings: state.result.findings.map((f) => ({ ...f, decision: state.decisions[f.id] || "pending" })),
    };
  }

  function exportJSON() { download("amin-report.json", JSON.stringify(reportData(), null, 2), "application/json"); }

  function exportHTML() {
    const d = reportData();
    const rows = d.findings.map((f) => `<tr><td>${esc(f.id)}</td><td>${esc(f.type_name)}</td><td>${SEV_AR[f.severity]}</td>
      <td dir="ltr">${esc(f.found.slice(0, 200))}</td><td dir="ltr">${esc(f.suggestion)}</td><td>${esc(f.reason_ar)}</td><td>${esc(f.source)}</td>
      <td>${{ accepted: "مقبول", rejected: "مرفوض", pending: "معلّق" }[f.decision]}</td></tr>`).join("");
    const html = `<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>تقرير أمين</title>
      <style>body{font-family:Tahoma,sans-serif;margin:24px;color:#18223a}h1{color:#1b2a55}table{border-collapse:collapse;width:100%;font-size:13px}
      td,th{border:1px solid #ccd;padding:6px;vertical-align:top}th{background:#1b2a55;color:#fff}pre{white-space:pre-wrap;background:#f4f7f8;padding:12px;border:1px solid #ccd}</style></head>
      <body><h1>تقرير «أمين» لمراجعة الترجمة</h1><p>تاريخ التقرير: ${esc(d.generated)} · اللغة: ${esc(d.lang)} · الجمهور: ${esc(d.audience.audience_name_ar)} · عدد المواضع: ${d.stats.total}</p>
      <h2>الأصل العربي</h2><pre>${esc(d.arabic)}</pre><h2>الترجمة</h2><pre dir="ltr">${esc(d.translation)}</pre>
      <h2>المواضع</h2><table><tr><th>#</th><th>النوع</th><th>الخطورة</th><th>الوارد</th><th>المقترح</th><th>السبب</th><th>المرجع</th><th>القرار</th></tr>${rows}</table>
      <h2>النسخة المصححة</h2><pre dir="ltr">${esc(d.corrected)}</pre>
      <p style="color:#5b6680;font-size:12px">«أمين» أداة مساعدة للمراجع الشرعي: تكتشف ولا تؤلّف، ولا تُفتي.</p></body></html>`;
    download("amin-report.html", html, "text/html");
  }

  init();
})();
