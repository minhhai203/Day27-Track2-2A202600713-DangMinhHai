#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -f phases/private.key ]; then
  echo "Missing phases/private.key"
  echo "Copy/download the released private key into phases/private.key, then rerun:"
  echo "  bash solution/run_private.sh"
  exit 1
fi

if [ ! -x .venv/bin/python3 ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

.venv/bin/python3 harness/selfcheck.py
.venv/bin/python3 harness/run.py --phase private --defense solution/defense.py --out solution/private_report.json

mkdir -p screenshot
python3 - <<'PY'
import json
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception as exc:
    print(f"Skip screenshot render: PIL unavailable ({exc})")
    raise SystemExit(0)

root = Path.cwd()
json_path = root / "solution" / "private_report.json"
out_path = root / "screenshot" / "private_report_json.png"
raw = json.loads(json_path.read_text())
lines = json.dumps(raw, indent=2).splitlines()

font_paths = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/SFNSMono.ttf",
    "/Library/Fonts/Menlo.ttf",
]
for path in font_paths:
    try:
        font = ImageFont.truetype(path, 18)
        small = ImageFont.truetype(path, 15)
        break
    except Exception:
        continue
else:
    font = small = ImageFont.load_default()

width = 1180
line_h = 28
header_h = 70
height = header_h + len(lines) * line_h + 44
img = Image.new("RGB", (width, height), "#252a33")
draw = ImageDraw.Draw(img)

img.paste("#20252e", (0, 0, width, 40))
img.paste("#2b313c", (0, 40, width, 70))
draw.polygon([(0, 0), (250, 0), (274, 40), (0, 40)], fill="#2c333f")
draw.text((20, 11), "{} private_report.json  U  x", font=small, fill="#9ee493")
draw.text(
    (22, 48),
    "Day27-Track2-2A202600713-DangMinhHai  >  solution  >  {} private_report.json  > ...",
    font=small,
    fill="#9ca8ba",
)
img.paste("#282e39", (0, 70, width, height))
img.paste("#303746", (0, 70, width, 70 + line_h))

colors = {
    "brace": "#d8a657",
    "key": "#e6a6ff",
    "string": "#9ee493",
    "num": "#ffb86c",
    "plain": "#d7dde8",
    "line": "#8b98aa",
}


def draw_json_line(x, y, line):
    stripped = line.lstrip(" ")
    indent = len(line) - len(stripped)
    cx = x + indent * 10
    if stripped in ("{", "}", "},"):
        draw.text((cx, y), stripped, font=font, fill=colors["brace"])
        return
    if ":" in stripped:
        key_part, value_part = stripped.split(":", 1)
        draw.text((cx, y), key_part + ":", font=font, fill=colors["key"])
        key_w = draw.textlength(key_part + ":", font=font)
        value_color = colors["string"] if '"' in value_part else colors["num"]
        if value_part.strip().startswith("{"):
            value_color = colors["brace"]
        draw.text((cx + key_w + 8, y), value_part, font=font, fill=value_color)
        return
    color = colors["brace"] if stripped.startswith(("}", "{")) else colors["plain"]
    draw.text((cx, y), stripped, font=font, fill=color)


for index, line in enumerate(lines, start=1):
    y = header_h + (index - 1) * line_h + 4
    draw.text((42, y), str(index), font=small, fill=colors["line"], anchor="ra")
    draw_json_line(78, y, line)

img.save(out_path)
print(out_path)
PY

echo "Ready:"
echo "  solution/private_report.json"
echo "  screenshot/private_report_json.png"
