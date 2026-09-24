"""Build the affordability explorer from its template and data.

  python paper1_affordability/scripts/build_explorer.py [--site-url URL]
  -> docs/explorer/explorer.html   standalone page (open in a browser; GitHub Pages index)
     docs/explorer/preview.png     1200 x 630 link-preview image for social media

Run scripts/export_explorer_data.py and scripts/anim_affordability.py first.
"""
import _paper  # noqa: F401  (shared pipeline + paper-1 outputs)
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "paper1_affordability/docs/explorer"
ap = argparse.ArgumentParser()
ap.add_argument("--site-url", default="https://gavacharles.github.io/kampala-affordability-explorer/")
a = ap.parse_args()

tpl = (EXP / "explorer_template.html").read_text(encoding="utf-8")
tpl = tpl.split("-->", 1)[1].lstrip() if tpl.startswith("<!--") else tpl
data = (ROOT / "paper1_affordability/outputs/interactive/explorer_data.json").read_text(encoding="utf-8")
body = tpl.replace("__DATA__", data)

TITLE = "Who can afford the housing on offer in Greater Kampala?"
DESC = ("97.5% of households in Greater Kampala cannot afford the typical listed 1–2 bedroom rental at 30% of "
        "income, and 78% even at 80%. Explore the map, change the assumptions, or play the tour.")
head = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="{DESC}">
<meta property="og:type" content="website">
<meta property="og:title" content="{TITLE}">
<meta property="og:description" content="{DESC}">
<meta property="og:url" content="{a.site_url}">
<meta property="og:image" content="{a.site_url}preview.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{TITLE}">
<meta name="twitter:description" content="{DESC}">
<meta name="twitter:image" content="{a.site_url}preview.png">
"""
page = head + body
page = page.replace("<div class=\"wrap\">", "</head>\n<body>\n<div class=\"wrap\">", 1) + "\n</body>\n</html>\n"
(EXP / "explorer.html").write_text(page, encoding="utf-8")

# ---- 1200 x 630 link-preview image
still = Image.open(ROOT / "paper1_affordability/outputs/animations/priced_out_threshold_still.png").convert("RGB")
w, h = still.size
mp = still.crop((int(0.17 * w), int(0.215 * h), int(0.83 * w), int(0.835 * h)))
mp = mp.resize((int(630 * mp.width / mp.height), 630))
img = Image.new("RGB", (1200, 630), "#f5f7f9")
img.paste(mp, (1200 - mp.width, 0))
d = ImageDraw.Draw(img)
fonts = "/System/Library/Fonts/Supplemental/"
try:
    fb, fr, fs = (ImageFont.truetype(fonts + "Arial Bold.ttf", 44), ImageFont.truetype(fonts + "Arial.ttf", 24),
                  ImageFont.truetype(fonts + "Arial.ttf", 18))
except OSError:
    fb = fr = fs = ImageFont.load_default()
x = 48
d.text((x, 60), "Who can afford", font=fb, fill="#1d2330")
d.text((x, 112), "the housing on offer", font=fb, fill="#1d2330")
d.text((x, 164), "in Greater Kampala?", font=fb, fill="#1d2330")
d.text((x, 262), "97.5%", font=ImageFont.truetype(fonts + "Arial Bold.ttf", 88) if fb != fr else fb, fill="#9b1030")
d.text((x, 362), "of households cannot afford the", font=fr, fill="#1d2330")
d.text((x, 394), "typical listed 1–2 bedroom rental", font=fr, fill="#1d2330")
d.text((x, 426), "at 30% of income", font=fr, fill="#1d2330")
d.text((x, 472), "Even at 80% of income: 78% priced out", font=fr, fill="#9b1030")
d.text((x, 540), "Interactive map  ·  change the assumptions  ·  play the tour", font=fs, fill="#5b6474")
d.text((x, 566), "10,643 online listings, 2025–26; modelled incomes (UBOS)", font=fs, fill="#5b6474")
img.save(EXP / "preview.png", optimize=True)
print("wrote paper1_affordability/docs/explorer/explorer.html and preview.png")
