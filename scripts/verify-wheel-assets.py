from __future__ import annotations

import glob
import zipfile

wheels = glob.glob("dist/*.whl")
if not wheels:
    raise SystemExit("no wheel found in dist/")

wheel = wheels[0]
with zipfile.ZipFile(wheel) as zf:
    names = set(zf.namelist())
    has_index = "app/static/index.html" in names
    has_js = any(name.startswith("app/static/assets/") and name.endswith(".js") for name in names)
    has_css = any(name.startswith("app/static/assets/") and name.endswith(".css") for name in names)

if not (has_index and has_js and has_css):
    raise SystemExit(f"frontend assets missing in wheel: index={has_index} js={has_js} css={has_css}")

print(f"frontend assets verified in wheel: {wheel}")
