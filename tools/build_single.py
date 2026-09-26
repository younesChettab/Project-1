"""يبني «أمين» صفحةً واحدة مكتفية بذاتها تعمل في المتصفح بلا خادم.

تُضمَّن فيها الأنماط والخطوط (data URI) والمحرك والبيانات. مناسبة للنشر على أي استضافة ثابتة
أو صفحة Artifact. الفحص الدلالي بالنموذج اللغوي غير متاح في هذه النسخة.

الاستعمال: python tools/build_single.py [--artifact]
  --artifact  يُخرج جسم الصفحة دون وسوم html/head/body، ويُخفي الطباعة والتنزيل (لا تعمل في إطار العرض).
"""

import argparse
import base64
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "dist" / "amin.html"))
    a = ap.parse_args()

    subprocess.run([sys.executable, str(ROOT / "tools" / "export_data.py")], check=True)
    html = (WEB / "index.html").read_text(encoding="utf-8")
    css = (WEB / "style.css").read_text(encoding="utf-8")
    css = re.sub(r'url\("fonts/([^"]+\.woff2)"\)',
                 lambda m: 'url("data:font/woff2;base64,' + base64.b64encode((WEB / "fonts" / m.group(1)).read_bytes()).decode() + '")',
                 css)
    if a.artifact:
        css += "\n#print { display: none !important; }\n"
    data = json.loads((WEB / "data" / "knowledge.json").read_text(encoding="utf-8"))
    engine = (WEB / "engine.js").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")
    data_js = "window.AMIN_DATA = " + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + ";"

    title = re.search(r"<title>.*?</title>", html, re.S).group(0)
    icon = re.search(r'<link rel="icon"[^>]*>', html).group(0)
    body = re.search(r"<body>(.*)</body>", html, re.S).group(1)
    body = re.sub(r'<script src="[^"]+"></script>\s*', "", body)
    scripts = f"<script>{data_js}</script>\n<script>{engine}</script>\n<script>{app}</script>\n"

    if a.artifact:
        page = f"{title}\n{icon}\n<style>{css}</style>\n<div dir=\"rtl\" lang=\"ar\">\n{body}\n</div>\n{scripts}"
    else:
        head = re.search(r"<head>(.*)</head>", html, re.S).group(1)
        head = re.sub(r'<link rel="stylesheet"[^>]*>', f"<style>{css}</style>", head)
        page = f'<!doctype html>\n<html lang="ar" dir="rtl">\n<head>{head}</head>\n<body>{body}{scripts}</body>\n</html>\n'
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"{out}: {out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
