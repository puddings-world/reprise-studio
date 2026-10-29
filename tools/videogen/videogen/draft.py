"""Draft a storyboard from timed lyrics: shot timing, sections, a kind rhythm and prompt stubs.

The draft is mechanical on purpose. It gets the timing right (gap-free shots, instrumental breaks, length
limits) and leaves every creative decision as a `TODO` for the author (a person or an agent) to write. The
stages refuse to run on text that still says TODO.

Rules, all tunable under `draft` in project.json:
- one shot per sung line; a line is "sung" for about `tail + sec_per_char × characters` seconds;
- silence of at least `min_gap` seconds becomes its own image shot (intro, interlude, outro);
- shots shorter than `min_shot` merge into the next one, longer than `max_shot` split evenly;
- a line belongs to the chorus when it and a neighbour repeat together elsewhere in the song;
- inside each section, shots alternate perform / story (story / image when there is no performance video).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .lyrics import Line

TODO = "TODO"
DRAFT_DEFAULTS = {"min_shot": 2.0, "max_shot": 8.0, "min_gap": 4.0, "sec_per_char": 0.55, "tail": 1.5}


@dataclass
class Segment:
    start: float
    end: float
    lyrics: list[str] = field(default_factory=list)
    chorus: bool = False
    hold: bool = False  # a later part of a split shot: it continues the previous part's moment

    @property
    def sung(self) -> bool:
        return bool(self.lyrics)


def _norm(text: str) -> str:
    return re.sub(r"[\W_]+", "", text).lower()


def chorus_flags(texts: list[str]) -> list[bool]:
    """True for lines that repeat together with a neighbouring line somewhere else in the song.

    A single repeated line (a refrain like "上天啊" opening every verse) is not enough; a repeated pair is.
    """
    n = [_norm(t) for t in texts]
    pairs: dict[tuple[str, str], int] = {}
    for i in range(len(n) - 1):
        pairs[(n[i], n[i + 1])] = pairs.get((n[i], n[i + 1]), 0) + 1
    flags = [False] * len(n)
    for i in range(len(n) - 1):
        if pairs[(n[i], n[i + 1])] > 1:
            flags[i] = flags[i + 1] = True
    return flags


def segments(lines: list[Line], duration: float, d: dict) -> list[Segment]:
    """Gap-free segments covering [0, duration]: sung lines plus silent breaks of at least `min_gap`."""
    flags = chorus_flags([ln.text for ln in lines])
    segs: list[Segment] = []
    t = 0.0
    for i, ln in enumerate(lines):
        if ln.start >= duration:
            break
        if ln.start - t >= d["min_gap"]:
            segs.append(Segment(t, ln.start))
            start = ln.start
        elif segs:
            segs[-1].end = ln.start  # a short pause stays with the previous shot
            start = ln.start
        else:
            start = 0.0
        nxt = lines[i + 1].start if i + 1 < len(lines) else duration
        sung_end = ln.start + d["tail"] + d["sec_per_char"] * len(_norm(ln.text))
        end = min(nxt, duration, sung_end, ln.end if ln.end is not None else nxt)
        segs.append(Segment(start, max(end, start + 0.1), [ln.text], flags[i]))
        t = segs[-1].end
    if duration - t >= d["min_gap"]:
        segs.append(Segment(t, duration))
    elif segs:
        segs[-1].end = duration
    return _split_long(_merge_short(segs, d["min_shot"]), d["max_shot"])


def _merge_short(segs: list[Segment], min_shot: float) -> list[Segment]:
    out: list[Segment] = []
    carry: Segment | None = None
    for s in segs:
        if carry:  # fold the short shot into this one
            s = Segment(carry.start, s.end, carry.lyrics + s.lyrics, carry.chorus or s.chorus)
            carry = None
        if s.end - s.start < min_shot and s is not segs[-1]:
            carry = s
            continue
        out.append(s)
    if out and out[-1].end - out[-1].start < min_shot and len(out) > 1:
        last = out.pop()
        prev = out.pop()
        out.append(Segment(prev.start, last.end, prev.lyrics + last.lyrics, prev.chorus or last.chorus))
    return out


def _split_long(segs: list[Segment], max_shot: float) -> list[Segment]:
    out = []
    for s in segs:
        parts = max(1, math.ceil((s.end - s.start) / max_shot - 1e-9))
        step = (s.end - s.start) / parts
        for k in range(parts):  # the lyric stays on the first part; the rest hold the moment
            end = s.end if k == parts - 1 else s.start + (k + 1) * step
            out.append(Segment(s.start + k * step, end, s.lyrics if k == 0 else [], s.chorus, hold=k > 0))
    return out


def section_names(segs: list[Segment]) -> list[str]:
    """intro / verseN / chorusN / interlude / outro for each segment."""
    sung = [i for i, s in enumerate(segs) if s.sung]
    first, last = (sung[0], sung[-1]) if sung else (len(segs), -1)
    names: list[str] = []
    counts = {"verse": 0, "chorus": 0}
    prev = None
    for i, s in enumerate(segs):
        if i < first:
            kind = "intro"
        elif s.hold and not s.sung:
            kind = prev
        elif i > last:
            kind = "outro"
        elif not s.sung:
            kind = "interlude"
        else:
            kind = "chorus" if s.chorus else "verse"
        if kind in counts and kind != prev:
            counts[kind] += 1
        names.append(f"{kind}{counts[kind]}" if kind in counts else kind)
        prev = kind
    return names


def draft(lines: list[Line], duration: float, crops: dict, perform: bool, settings: dict | None = None) -> dict:
    """A storyboard dict (schema version 1) with TODO markers where the author has to write."""
    d = {**DRAFT_DEFAULTS, **(settings or {})}
    segs = segments(lines, duration, d)
    names = section_names(segs)
    framings = list(crops) if perform else []
    shots, nth, fcount = [], 0, 0
    for i, (s, sec) in enumerate(zip(segs, names)):
        new_section = i == 0 or sec != names[i - 1]
        nth = 0 if new_section else nth + 1
        vocal = s.sung or (s.hold and sec.startswith(("verse", "chorus")))
        if not vocal:
            kind = "image"
        elif framings:
            kind = "perform" if nth % 2 == 0 else "story"
        else:
            kind = "story" if nth % 2 == 0 else "image"
        transition = "fade from black" if i == 0 else "dissolve" if new_section or not vocal else "cut"
        shot = {"id": f"S{i + 1:02d}", "start": round(s.start, 2), "end": round(s.end, 2), "section": sec,
                "kind": kind, "light": "", "light_prompt": TODO, "transition_in": transition,
                "lyrics": s.lyrics, "note": ""}
        if kind == "perform":
            shot["framing"] = framings[fcount % len(framings)]
            fcount += 1
        shots.append(shot)
    for a, b in zip(shots, shots[1:]):  # rounding must not open gaps
        b["start"] = a["end"]
    shots[-1]["end"] = round(duration, 2)
    return {"version": 1, "duration": round(duration, 2), "shots": shots}


def prompt_stubs(sb: dict, existing: dict) -> dict:
    """prompts.json `shots` entries for shots that need one, keeping every entry already written."""
    out = dict(existing)
    for s in sb["shots"]:
        if s["kind"] != "perform" and s["id"] not in out:
            hint = "／".join(s["lyrics"]) or s["section"]
            out[s["id"]] = {"keyframe": f"{TODO}: {hint}", "motion": TODO}
    return out


def todos(obj, path: str = "") -> list[str]:
    """Dotted paths of every string that still contains TODO."""
    if isinstance(obj, str):
        return [path] if TODO in obj else []
    if isinstance(obj, dict):
        return [p for k, v in obj.items() for p in todos(v, f"{path}.{k}" if path else str(k))]
    if isinstance(obj, list):
        return [p for i, v in enumerate(obj) for p in todos(v, f"{path}[{i}]")]
    return []
