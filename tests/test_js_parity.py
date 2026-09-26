"""يتحقق من أن محرك المتصفح (web/engine.js) يعطي النتائج نفسها التي يعطيها محرك Python."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from amin.engine.pipeline import run

ROOT = Path(__file__).resolve().parent.parent

EXTRA = [
    {"arabic": "الشهداء أحياء. ولا يجوز الاعتداء على من لم يقاتل. والله أعلم.",
     "translation": "The martyrs are alive. It is permitted to attack. That applies to those who did not fight. God knows best.",
     "lang": "en", "audience": "general"},
    {"arabic": "قال تعالى: ﴿قُلْ يَا أَيُّهَا الْكَافِرُونَ﴾.", "translation": 'Allah a dit : « Dis : "Ô vous les infidèles ! » [109:1].',
     "lang": "fr", "audience": "general"},
    {"arabic": "خلق الله آدم.", "translation": "Obviously God created Adam! Everyone knows it! You will burn in hell and hellfire.",
     "lang": None, "audience": "academics"},
]


@pytest.mark.skipif(not shutil.which("node"), reason="node غير مثبت")
def test_engines_agree():
    subprocess.run([sys.executable, str(ROOT / "tools" / "export_data.py")], check=True, capture_output=True)
    samples = yaml.safe_load(open(ROOT / "samples" / "samples.yaml", encoding="utf-8"))["samples"]
    cases = [{k: s[k] for k in ("arabic", "translation", "lang", "audience")} for s in samples] + EXTRA
    js = json.loads(subprocess.run(["node", str(ROOT / "tests" / "parity_run.js")], input=json.dumps(cases),
                                   capture_output=True, text=True, check=True).stdout)
    for c, got in zip(cases, js):
        py = [[f["id"], f["rule"], f["start"], f["end"], f["suggestion"], f["severity"]]
              for f in run(c["arabic"], c["translation"], c["lang"], c["audience"], use_llm=False)["findings"]]
        assert got == py, c["translation"][:60]
