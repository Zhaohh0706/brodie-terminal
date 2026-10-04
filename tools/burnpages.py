#!/usr/bin/env python3
"""Write a share page for every burn: burn/<seq>/index.html and burn/<seq>/card.jpg.

A post on X that links brodieonhood.com/burn/<seq> unfurls into the burn's own
card (og:image) instead of a bare link. The bot DMs the owner a one-tap "post to
X" button with that link once the page is live.

A page is written once and never redrawn: a burn doesn't change after it lands,
and a file that never changes keeps the ledger commits free of churn. The first
run backfills every burn so far. The "≈ USD" figure uses the ETH price of the run
that wrote the page, which for a new burn is minutes after it.

Reads data/tl.json (burns + market), so run it after scripts/inject.py. The card
is the bot's burn receipt (community-bot/brodie_bot/render.py burn_card) drawn at
X's 1200×630 instead of Telegram's 16:9; keep the two in step.

  python3 tools/burnpages.py            # write what's missing
  python3 tools/burnpages.py --force    # redraw every page (after a design change)
"""
import html, io, json, pathlib, sys, time
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
CARD = pathlib.Path(__file__).resolve().parent / "card"
SITE = "https://www.brodieonhood.com"
EXPLORER = "https://robinhoodchain.blockscout.com"
MILESTONES = (1e5, 2.5e5, 5e5, 1e6, 2.5e6, 5e6, 1e7, 2.5e7, 5e7, 1e8, 2.5e8, 5e8, 1e9)
W, H = 1200, 630

BG, SURFACE, LINE = (10, 14, 12), (22, 30, 26), (52, 69, 60)
INK, INK2, INK3 = (238, 243, 239), (169, 184, 175), (113, 130, 122)
LIME, FIRE = (204, 255, 0), (255, 122, 69)


@lru_cache(maxsize=None)
def font(name, size, weight=None):
    f = ImageFont.truetype(str(CARD / f"{name}.ttf"), size)
    if weight is not None:
        axes = []
        for ax in f.get_variation_axes():
            n = ax["name"].decode() if isinstance(ax["name"], bytes) else ax["name"]
            axes.append(weight if n == "Weight" else min(max(size, ax["minimum"]), ax["maximum"])
                        if n == "Optical Size" else ax["default"] if n != "Wonky" else 0)
        f.set_variation_by_axes(axes)
    return f


def glow(img, xy, r, color, alpha):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    x, y = xy
    ImageDraw.Draw(layer).ellipse((x - r, y - r, x + r, y + r), fill=color + (alpha,))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(r // 2)))


def art(size):
    a = Image.open(CARD / "dig.jpg").convert("RGB")
    s = min(a.size)
    a = a.crop(((a.width - s) // 2, (a.height - s) // 2, (a.width + s) // 2, (a.height + s) // 2))
    a = a.resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=36, fill=255)
    out = Image.new("RGBA", (size, size))
    out.paste(a, (0, 0), mask)
    return out


def next_goal(total):
    return next((m for m in MILESTONES if m > total), MILESTONES[-1])


def short(n):
    return f"{n / 1e6:g}M" if n >= 1e6 else f"{n / 1e3:g}K"


def card(b, total, usd):
    img = Image.new("RGBA", (W, H), BG + (255,))
    glow(img, (120, 600), 340, FIRE, 70)
    glow(img, (1000, 110), 290, LIME, 26)
    d = ImageDraw.Draw(img)

    side = 480
    ax, ay = W - side - 60, (H - side) // 2
    d.rounded_rectangle((ax - 3, ay - 3, ax + side + 3, ay + side + 3), radius=39, outline=LINE, width=3)
    img.alpha_composite(art(side), (ax, ay))

    x = 60
    when = time.strftime("%d %b %Y · %H:%M UTC", time.gmtime(b["t"])).upper()
    d.text((x, 54), f"BURN #{b['seq']}", font=font("JetBrainsMono", 26, 700), fill=LIME)
    d.text((x + d.textlength(f"BURN #{b['seq']}", font=font("JetBrainsMono", 26, 700)) + 22, 56), when,
           font=font("JetBrainsMono", 22, 400), fill=INK3)

    big, size = f"{b['tokens']:,.0f}", 128
    while size > 70 and d.textlength(big, font=font("Fraunces", size, 800)) > 560:
        size -= 6
    d.text((x - 4, 92), big, font=font("Fraunces", size, 800), fill=INK)
    d.text((x, 92 + size + 6), "BRODIE buried", font=font("InstrumentSans", 42, 600), fill=FIRE)

    y = 310
    d.line((x, y, x + 560, y), fill=LINE, width=2)
    cols = (("ETH SPENT", f"{b['eth']:.4f}"), ("≈ USD", f"${usd:,.0f}" if usd else "—"),
            ("ALL-TIME", f"{total:,.0f}"))
    for i, (label, value) in enumerate(cols):
        cx = x + i * 190
        d.text((cx, y + 24), label, font=font("JetBrainsMono", 18, 500), fill=INK3)
        d.text((cx, y + 50), value, font=font("Fraunces", 40, 700), fill=INK)

    y, goal = 446, next_goal(total)
    pct = min(1.0, total / goal)
    d.text((x, y), f"ROAD TO {short(goal)} BURNED", font=font("JetBrainsMono", 18, 500), fill=INK3)
    d.text((x + 560, y), f"{pct * 100:.0f}%", font=font("JetBrainsMono", 18, 700), fill=LIME, anchor="ra")
    d.rounded_rectangle((x, y + 32, x + 560, y + 48), radius=8, fill=SURFACE)
    d.rounded_rectangle((x, y + 32, x + max(16, int(560 * pct)), y + 48), radius=8, fill=LIME)
    n = b["seq"]
    d.text((x, y + 62), f"{n} burn{'s' if n != 1 else ''} so far", font=font("InstrumentSans", 20, 500), fill=INK2)

    d.text((x, H - 50), "70% of every trading fee  →  buys BRODIE  →  sent to 0x0",
           font=font("InstrumentSans", 20, 500), fill=INK3)
    buf = io.BytesIO()              # JPEG 4:4:4 reads the same as PNG at a third of the size
    img.convert("RGB").save(buf, "JPEG", quality=88, optimize=True, progressive=True, subsampling=0)
    return buf.getvalue()


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Burn #{seq} · {tokens} BRODIE buried</title>
<meta name="description" content="{desc}">
<meta name="theme-color" content="#0A0E0C">
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Brodie Terminal">
<meta property="og:url" content="{url}">
<meta property="og:title" content="Burn #{seq} · {tokens} $BRODIE buried">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{img}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Burn #{seq}: {tokens} BRODIE bought back and sent to 0x0">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@Brodieonhood">
<meta name="twitter:title" content="Burn #{seq} · {tokens} $BRODIE buried">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{img}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,700;9..144,800&family=Instrument+Sans:wght@400;500;600&family=JetBrains+Mono:wght@500;700&display=swap">
<style>
:root{{--bg:#0A0E0C;--surface:#101613;--line:#22302A;--ink:#EEF3EF;--ink-2:#A9B8AF;--ink-3:#71827A;--lime:#CCFF00;--lime-ink:#0A0E0C;--fire:#FF7A45}}
@media (prefers-color-scheme: light){{:root{{--bg:#F2F4F0;--surface:#FFFFFF;--line:#DCE3D8;--ink:#0F1613;--ink-2:#43514A;--ink-3:#6E7D74;--lime:#6E9400;--lime-ink:#FFFFFF;--fire:#D9541E}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 "Instrument Sans",system-ui,sans-serif}}
main{{max-width:760px;margin:0 auto;padding:28px 16px 48px}}
a{{color:inherit}}
.top{{display:flex;justify-content:space-between;align-items:center;gap:12px;font:500 13px "JetBrains Mono",monospace;letter-spacing:.06em;color:var(--ink-3);text-transform:uppercase}}
.top a{{text-decoration:none;border-bottom:1px solid transparent}}
.top a:hover{{color:var(--lime);border-bottom-color:var(--lime)}}
.kick{{margin:28px 0 4px;font:700 14px "JetBrains Mono",monospace;letter-spacing:.08em;color:var(--lime)}}
h1{{margin:0;font:800 clamp(34px,8vw,56px)/1.05 Fraunces,Georgia,serif;letter-spacing:-.01em}}
h1 span{{color:var(--fire)}}
.when{{margin:8px 0 22px;color:var(--ink-3);font:500 14px "JetBrains Mono",monospace}}
img{{display:block;width:100%;height:auto;border-radius:16px;border:1px solid var(--line)}}
dl{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;margin:22px 0;background:var(--line);border:1px solid var(--line);border-radius:14px;overflow:hidden}}
dl div{{background:var(--surface);padding:14px 16px;min-width:0}}
dt{{font:500 12px "JetBrains Mono",monospace;letter-spacing:.06em;color:var(--ink-3);text-transform:uppercase}}
dd{{margin:4px 0 0;font:700 20px Fraunces,Georgia,serif;overflow-wrap:anywhere}}
dd.mono{{font:500 14px "JetBrains Mono",monospace;padding-top:4px}}
.go{{display:flex;flex-wrap:wrap;gap:10px}}
.btn{{display:inline-block;padding:11px 18px;border-radius:999px;border:1px solid var(--line);text-decoration:none;font-weight:600}}
.btn.main{{background:var(--lime);border-color:var(--lime);color:var(--lime-ink)}}
.btn:hover{{border-color:var(--lime)}}
.how{{margin-top:28px;color:var(--ink-2);font-size:15px}}
@media (max-width:480px){{dl{{grid-template-columns:1fr}}.top span{{display:none}}}}
</style>
</head>
<body>
<main>
<div class="top"><a href="/#burn">← Brodie Terminal</a><span>$BRODIE · Robinhood Chain</span></div>
<p class="kick">BURN #{seq}</p>
<h1>{tokens} <span>BRODIE buried</span></h1>
<p class="when">{when}</p>
<img src="card.jpg" width="1200" height="630" alt="Burn #{seq}: {tokens} BRODIE bought back and sent to 0x0">
<dl>
<div><dt>ETH spent</dt><dd>{eth} ETH</dd></div>
<div><dt>≈ USD</dt><dd>{usd}</dd></div>
<div><dt>All-time buried, after this burn</dt><dd>{total} BRODIE</dd></div>
<div><dt>Burns so far</dt><dd>{seq}</dd></div>
<div><dt>Transaction</dt><dd class="mono"><a href="{tx_url}" rel="noopener">{tx_short}</a></dd></div>
<div><dt>Called by</dt><dd class="mono"><a href="{caller_url}" rel="noopener">{caller_short}</a></dd></div>
</dl>
<div class="go"><a class="btn main" href="/#burn">Open the live burn dashboard</a><a class="btn" href="{tx_url}" rel="noopener">View on Blockscout</a></div>
<p class="how">The creator's 70% share of every pool fee goes to a vault nobody holds keys to. Anyone can call <code>burnNow()</code>: it buys BRODIE from the pool and sends it to 0x0. The ≈ USD figure uses the ETH price when this page was made.</p>
</main>
</body>
</html>
"""


def page(b, total, usd):
    seq = b["seq"]
    tokens = f"{b['tokens']:,.0f}"
    desc = (f"Bought back with {b['eth']:.4f} ETH of creator fees and sent to 0x0. "
            f"{total:,.0f} BRODIE buried across {seq} burn{'s' if seq != 1 else ''} so far.")
    q = lambda s: html.escape(str(s), quote=True)
    return PAGE.format(
        seq=seq, tokens=q(tokens), desc=q(desc), url=f"{SITE}/burn/{seq}", img=f"{SITE}/burn/{seq}/card.jpg",
        when=q(time.strftime("%d %b %Y · %H:%M UTC", time.gmtime(b["t"]))), eth=f"{b['eth']:.4f}",
        usd=q(f"${usd:,.0f}" if usd else "—"), total=q(f"{total:,.0f}"),
        tx_url=q(f"{EXPLORER}/tx/{b['tx']}"), tx_short=q(b["tx"][:10] + "…" + b["tx"][-6:]),
        caller_url=q(f"{EXPLORER}/address/{b['caller']}"), caller_short=q(b["caller"][:8] + "…" + b["caller"][-4:]))


def main():
    force = "--force" in sys.argv
    tl = json.loads((ROOT / "data" / "tl.json").read_text())
    burns = sorted(tl["burns"]["burns"], key=lambda b: b["seq"])
    m = tl.get("market") or {}
    eth_usd = m["price"] / m["priceNative"] if m.get("price") and m.get("priceNative") else 0.0
    total, wrote = 0.0, []
    for b in burns:
        total += b["tokens"]
        out = ROOT / "burn" / str(b["seq"])
        if not force and (out / "index.html").exists() and (out / "card.jpg").exists():
            continue
        out.mkdir(parents=True, exist_ok=True)
        usd = b["eth"] * eth_usd
        (out / "card.jpg").write_bytes(card(b, total, usd))
        (out / "index.html").write_text(page(b, total, usd))
        wrote.append(b["seq"])
    print(f"burn pages: {len(burns)} burns, wrote {wrote or 'none'}")


if __name__ == "__main__":
    main()
