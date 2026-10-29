"""Timed lyrics: read LRC, ASS or SRT into lines, and write the .ass file the assembler burns in.

A line's `end` is when the next timestamp says it stops: an explicit end in ASS/SRT, the next tag in LRC
(an empty LRC tag marks the end of a phrase), or None for a last LRC line with nothing after it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

FORMATS = (".lrc", ".ass", ".srt")
LRC_TAG = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")
ASS_TIME = re.compile(r"(\d+):(\d+):(\d+(?:\.\d+)?)")
SRT_TIME = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")


@dataclass
class Line:
    start: float
    end: float | None
    text: str


def parse_lrc(text: str) -> list[Line]:
    stamped = []
    for raw in text.splitlines():
        tags = LRC_TAG.findall(raw)
        body = LRC_TAG.sub("", raw).strip()
        for m, s in tags:  # one line may carry several timestamps (a repeated chorus line)
            stamped.append((int(m) * 60 + float(s), body))
    stamped.sort(key=lambda x: x[0])
    return [Line(t, stamped[i + 1][0] if i + 1 < len(stamped) else None, body)
            for i, (t, body) in enumerate(stamped) if body]


def _ass_seconds(stamp: str) -> float:
    h, m, s = ASS_TIME.match(stamp.strip()).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_ass(text: str) -> list[Line]:
    out = []
    # split on newlines only: str.splitlines() also breaks on control characters such as a stray form feed
    for raw in text.replace("\r\n", "\n").split("\n"):
        if not raw.startswith("Dialogue:"):
            continue
        f = raw.split(":", 1)[1].split(",", 9)
        body = re.sub(r"\{[^}]*\}", "", f[9]).replace("\\N", " ").replace("\\n", " ").strip()
        if body:
            out.append(Line(_ass_seconds(f[1]), _ass_seconds(f[2]), body))
    return sorted(out, key=lambda ln: ln.start)


def parse_srt(text: str) -> list[Line]:
    out = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        rows = block.split("\n")
        for i, row in enumerate(rows):
            if m := SRT_TIME.search(row):
                g = [int(x) for x in m.groups()]
                start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
                end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
                body = " ".join(r.strip() for r in rows[i + 1:] if r.strip())
                if body:
                    out.append(Line(start, end, re.sub(r"<[^>]+>", "", body)))
                break
    return sorted(out, key=lambda ln: ln.start)


def load(path: Path, offset: float = 0.0) -> list[Line]:
    """Lines from a lyrics file, shifted by `offset` seconds (a cover often starts later than the original)."""
    suffix = path.suffix.lower()
    if suffix not in FORMATS:
        raise SystemExit(f"{path}: lyrics must be one of {', '.join(FORMATS)}")
    text = path.read_text(encoding="utf-8-sig")
    lines = {".lrc": parse_lrc, ".ass": parse_ass, ".srt": parse_srt}[suffix](text)
    if not lines:
        raise SystemExit(f"{path}: no timed lyric lines found")
    shifted = [Line(ln.start + offset, None if ln.end is None else ln.end + offset, ln.text) for ln in lines]
    return [ln for ln in shifted if ln.start >= 0]


def _stamp(t: float) -> str:
    cs = round(t * 100)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, \
Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, \
MarginV, Encoding
Style: Lyric,{font},{size},&H00F4F1EE,&H00F4F1EE,&H60301810,&H80000000,-1,0,0,0,100,100,6,0,1,2.2,2,2,60,60,\
{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def to_ass(lines: list[Line], size: tuple[int, int], style: dict, hold: float = 6.0, gap: float = 0.15) -> str:
    """An .ass file with one fading `Lyric` event per line. A line without an end is held `hold` seconds;
    every line stops `gap` seconds before the next one so two lines never overlap."""
    out = [ASS_HEADER.format(w=size[0], h=size[1], **style)]
    for i, ln in enumerate(lines):
        end = ln.end if ln.end is not None else ln.start + hold
        if i + 1 < len(lines):
            end = min(end, lines[i + 1].start - gap)
        end = max(end, ln.start + 0.2)
        out.append(f"Dialogue: 0,{_stamp(ln.start)},{_stamp(end)},Lyric,,0,0,0,,{{\\fad(250,300)}}{ln.text}\n")
    return "".join(out)
