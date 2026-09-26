// يشغّل محرك المتصفح على نصوص مُمرّرة (JSON من stdin) ويطبع التنبيهات — يستعمله test_js_parity.py
const fs = require("fs");
const path = require("path");
const E = require(path.join(__dirname, "..", "web", "engine.js"));
const K = E.compile(JSON.parse(fs.readFileSync(path.join(__dirname, "..", "web", "data", "knowledge.json"), "utf8")));
const cases = JSON.parse(fs.readFileSync(0, "utf8"));
const out = cases.map((c) => E.run(K, c.arabic, c.translation, c.lang, c.audience).findings
  .map((f) => [f.id, f.rule, f.start, f.end, f.suggestion, f.severity]));
process.stdout.write(JSON.stringify(out));
