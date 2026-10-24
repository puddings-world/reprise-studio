"""Storyboard schema (version 1): an ordered, gap-free list of shots covering the whole song.

Each shot: id, start, end (seconds), section, kind (perform | story | image), light, light_prompt,
transition_in, lyrics[], note; perform shots add framing (a key of the project's `crops`).
"""
from __future__ import annotations

import json
from pathlib import Path

KINDS = ("perform", "story", "image")
TRANSITIONS = ("cut", "dissolve", "light swell", "fade from black", "white flash")


def load(path: Path) -> dict:
    sb = json.loads(path.read_text(encoding="utf-8"))
    problems = validate(sb)
    if problems:
        raise SystemExit(f"{path}: invalid storyboard\n  " + "\n  ".join(problems))
    return sb


def validate(sb: dict, crops: dict | None = None) -> list[str]:
    """Human-readable problems; empty when the storyboard is usable."""
    out = []
    shots = sb.get("shots", [])
    if not shots:
        return ["no shots"]
    seen = set()
    for i, s in enumerate(shots):
        sid = s.get("id", f"#{i}")
        for key in ("id", "start", "end", "kind", "transition_in"):
            if key not in s:
                out.append(f"{sid}: missing '{key}'")
        if sid in seen:
            out.append(f"{sid}: duplicate id")
        seen.add(sid)
        if s.get("kind") not in KINDS:
            out.append(f"{sid}: kind must be one of {KINDS}")
        if s.get("transition_in") not in TRANSITIONS:
            out.append(f"{sid}: transition_in must be one of {TRANSITIONS}")
        if "start" in s and "end" in s and s["end"] <= s["start"]:
            out.append(f"{sid}: end must be after start")
        if s.get("kind") == "perform":
            if "framing" not in s:
                out.append(f"{sid}: perform shot needs 'framing'")
            elif crops is not None and s["framing"] not in crops:
                out.append(f"{sid}: framing '{s['framing']}' is not in project crops {sorted(crops)}")
        if i and "start" in s and abs(s["start"] - shots[i - 1].get("end", s["start"])) > 1e-6:
            out.append(f"{sid}: starts at {s['start']} but previous shot ends at {shots[i - 1].get('end')}")
    if shots[0].get("start", 0) != 0:
        out.append("first shot must start at 0")
    return out


def frame_span(shot: dict, fps: int) -> int:
    """Frames a shot occupies. Rounding both edges keeps consecutive shots gap-free."""
    return round(shot["end"] * fps) - round(shot["start"] * fps)


def wan_frames(n: int, cap: int | None = None) -> int:
    """Smallest Wan-compatible frame count (4k + 1) that covers n frames, optionally capped."""
    if cap is not None:
        n = min(n, cap)
    return (max(n, 1) - 1 + 3) // 4 * 4 + 1


def select(shots: list[dict], only: list[str] | None = None, kinds: list[str] | None = None) -> list[dict]:
    return [s for s in shots if (not only or s["id"] in only) and (not kinds or s["kind"] in kinds)]
