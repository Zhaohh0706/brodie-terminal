# assets

`brodie_original.png` — the official $BRODIE V2 artwork, as published on the V2
contract's DexScreener listing (800×800 PNG).

`brodie360.webp` — the same image at 360px, WebP q78. This is the file embedded
in `index.html` as a data URI, so the page needs no external image host and the
logo renders even where outbound requests are blocked.

To regenerate after replacing the source:

```python
from PIL import Image; import base64
im = Image.open("brodie_original.png").convert("RGB")
im.thumbnail((360, 360), Image.LANCZOS)
im.save("brodie360.webp", "WEBP", quality=78, method=6)
print("data:image/webp;base64," + base64.b64encode(open("brodie360.webp","rb").read()).decode())
```

Paste the printed string over the existing `src="data:image/webp;base64,…"` in
`index.html` (it appears twice: the top bar and the masthead seal).
