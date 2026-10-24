"""Cover / thumbnail: generate key art with the character, then set the title with a real font.

Text is typeset locally (PIL) rather than painted by the model, so every stroke of the Chinese title is right.
The art stage needs a GPU (`videogen cover`, remote-able); titling is CPU-only (`videogen cover-title`).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

DEFAULT_COVER = {
    "size": [1664, 928],          # 16:9-ish, multiples of 32; downscaled to 1280x720 for YouTube
    "seeds": [1, 2, 3, 4],
    "font": "NotoSerifTC",
    "title": "",
    "subtitle": "",
    "side": "left",               # where the title sits; the prompt should leave that side calm
}


def font_dirs() -> list[Path]:
    """Usual font locations on Windows, macOS and Linux (user dirs first)."""
    home = Path.home()
    dirs = [Path(os.environ.get("LOCALAPPDATA", home)) / "Microsoft" / "Windows" / "Fonts",
            Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
            home / "Library" / "Fonts", Path("/Library/Fonts"), Path("/System/Library/Fonts"),
            home / ".local" / "share" / "fonts", home / ".fonts", Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts")]
    return [d for d in dirs if d.exists()]


def find_font(name: str, dirs: list[Path] | None = None) -> Path | None:
    """First font file whose name starts with `name` (spaces and case ignored); a path is returned as-is."""
    if Path(name).is_file():
        return Path(name)
    key = name.replace(" ", "").lower()
    for d in dirs if dirs is not None else font_dirs():
        for f in sorted(d.rglob("*")):
            if f.suffix.lower() in (".ttf", ".otf", ".ttc") and f.stem.replace(" ", "").lower().startswith(key):
                return f
    return None


def _font(path: Path, size: int, weight: int):
    from PIL import ImageFont
    f = ImageFont.truetype(str(path), size)
    try:  # variable fonts: pick the weight; static fonts ignore this
        f.set_variation_by_axes([weight])
    except (OSError, ValueError, AttributeError):
        pass
    return f


def compose_title(art, title: str, subtitle: str, font_path: Path, side: str = "left", out_size=(1280, 720)):
    """Scrim + title + subtitle over the art, returned at `out_size`."""
    from PIL import Image, ImageDraw, ImageFilter
    img = art.convert("RGB").resize(out_size, Image.LANCZOS)
    W, H = img.size
    # A soft dark scrim on the title side keeps the type legible on any background.
    scrim = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(scrim)
    span = int(W * 0.55)
    for x in range(span):
        a = int(150 * (1 - x / span) ** 1.6)
        xx = x if side == "left" else W - 1 - x
        d.line([(xx, 0), (xx, H)], fill=a)
    img = Image.composite(Image.new("RGB", (W, H), (6, 12, 28)), img, scrim)

    title_font = _font(font_path, int(H * 0.14), 700)
    sub_font = _font(font_path, int(H * 0.048), 500)
    draw = ImageDraw.Draw(img)
    margin = int(W * 0.06)
    tb = draw.textbbox((0, 0), title, font=title_font)
    sb = draw.textbbox((0, 0), subtitle, font=sub_font) if subtitle else (0, 0, 0, 0)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    gap = int(H * 0.035)
    y = int(H * 0.60) - th
    x = margin if side == "left" else W - margin - tw
    # glow: a blurred copy of the title under the crisp one
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).text((x - tb[0], y - tb[1]), title, font=title_font, fill=200)
    glow = glow.filter(ImageFilter.GaussianBlur(int(H * 0.012)))
    img = Image.composite(Image.new("RGB", (W, H), (150, 190, 255)), img, glow.point(lambda v: v * 0.45))
    draw = ImageDraw.Draw(img)
    draw.text((x - tb[0], y - tb[1]), title, font=title_font, fill=(244, 241, 238))
    if subtitle:
        sx = x if side == "left" else W - margin - (sb[2] - sb[0])
        rule_y = y + th + gap
        draw.line([(sx, rule_y), (sx + int(W * 0.05), rule_y)], fill=(232, 180, 106), width=max(2, H // 360))
        draw.text((sx - sb[0], rule_y + gap - sb[1]), subtitle, font=sub_font, fill=(214, 222, 232))
    return img


def settings(cfg: dict) -> dict:
    return {**DEFAULT_COVER, **cfg.get("cover", {})}


def art(p, seeds: list[int] | None = None) -> list[str]:
    """GPU stage: cover art candidates from prompts.json `cover`."""
    from PIL import Image
    from .models import ImageModel, free_memory
    from .stages import _device, log
    c = settings(p.cfg)
    text = p.prompts.d.get("cover")
    if not text:
        raise SystemExit("prompts.json has no `cover` prompt")
    prompt = p.prompts._fill(text) + " " + p.prompts.d["style"]
    images = [Image.open(p.path("character")).convert("RGB")] if "{" + p.prompts.char_var + "}" in text else None
    model = ImageModel(p.cfg["models"]["image"], "image", _device())
    made = []
    for seed in seeds or c["seeds"]:
        name = f"cover/art_s{seed}.png"
        if not (p.work / name).exists():
            t = time.time()
            (p.work / "cover").mkdir(parents=True, exist_ok=True)
            model.generate(prompt, images, c["size"][0], c["size"][1], p.cfg["steps"]["image"], seed).save(p.work / name)
            log("cover", seed, f"{time.time() - t:.0f}s")
        made.append(name)
    del model; free_memory()
    return made


def titles(p) -> list[Path]:
    """CPU stage: typeset the title on every art candidate -> work/cover/cover_s<seed>.jpg (1280x720)."""
    from PIL import Image
    c = settings(p.cfg)
    font = find_font(c["font"])
    if not font:
        raise SystemExit(f"font '{c['font']}' not found in {', '.join(map(str, font_dirs()))}; "
                         "install it or set cover.font to a font file path")
    title = c["title"] or p.cfg.get("title", "")
    out = []
    for a in sorted((p.work / "cover").glob("art_s*.png")):
        img = compose_title(Image.open(a), title, c["subtitle"], font, c["side"])
        dst = a.with_name(a.name.replace("art_", "cover_").replace(".png", ".jpg"))
        img.save(dst, quality=92)
        out.append(dst)
        print(dst, file=sys.stdout, flush=True)
    return out
