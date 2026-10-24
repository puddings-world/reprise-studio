"""Parse review feedback pasted back from a review page (or typed by hand) and apply it to the state.

Canonical format, one directive per line (the review pages produce it):

    videogen-feedback stage=keyframes
    pick S01=s1 S02=s2
    redo S16: only the two of them from behind, far away
    edit-off S04
    note S05: keep this but warmer

Also accepted: the first review page's legacy form `選圖 {"S01": 1, ...}` followed by
`S16：note` lines under `重畫/備註：`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .state import State


@dataclass
class Feedback:
    stage: str = "keyframes"
    picks: dict[str, str] = field(default_factory=dict)
    redo: dict[str, str] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)
    edit_off: set[str] = field(default_factory=set)


SHOT = r"(S\d+[A-Za-z]?)"
SEP = r"\s*[:：]\s*"


def _pick_value(v) -> str:
    v = str(v).strip()
    return f"s{v}" if v.isdigit() else v


def parse(text: str) -> Feedback:
    fb = Feedback()
    legacy_notes = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if m := re.match(r"videogen-feedback\s+stage=(\w+)", line):
            fb.stage = m.group(1)
        elif line.startswith("pick "):
            for sid, val in re.findall(SHOT + r"=(\S+)", line):
                fb.picks[sid] = _pick_value(val)
        elif m := re.match(r"redo\s+" + SHOT + SEP + "(.*)", line):
            fb.redo[m.group(1)] = m.group(2).strip()
        elif m := re.match(r"redo\s+" + SHOT + r"\s*$", line):
            fb.redo[m.group(1)] = ""
        elif m := re.match(r"note\s+" + SHOT + SEP + "(.*)", line):
            fb.notes[m.group(1)] = m.group(2).strip()
        elif m := re.match(r"edit-off\s+(.*)", line):
            fb.edit_off |= set(re.findall(SHOT, m.group(1)))
        elif m := re.match(r"選圖\s*(\{.*\})", line):
            fb.picks.update({k: _pick_value(v) for k, v in json.loads(m.group(1)).items()})
        elif line.startswith("重畫"):
            legacy_notes = True
        elif legacy_notes and (m := re.match(SHOT + r"(?:（選\s*(\d+)，備註）)?" + SEP + "(.*)", line)):
            sid, kept, note = m.groups()
            if kept:
                fb.notes[sid] = note.strip()
            else:
                fb.redo[sid] = note.strip()
    return fb


def apply(fb: Feedback, state: State) -> list[str]:
    """Apply feedback to the state; returns a short log of what changed."""
    log = []
    state.data["round"] = state.data.get("round", 0) + 1
    for sid, pick in fb.picks.items():
        if sid in fb.redo:
            continue
        if fb.stage == "keyframes":
            state.set_pick(sid, pick if pick.endswith(".png") else _candidate_name(state, sid, pick))
            log.append(f"{sid}: pick {state.shot(sid)['pick']}")
    for sid in fb.edit_off:
        state.shot(sid)["use_edit"] = False
        state.shot(sid)["clip"] = None
        log.append(f"{sid}: use the unedited image")
    for sid, note in fb.redo.items():
        state.request_redo(sid, fb.stage, note)
        log.append(f"{sid}: redo {fb.stage}" + (f" ({note})" if note else ""))
    for sid, note in fb.notes.items():
        state.shot(sid)["notes"].append({"round": state.data["round"], "stage": fb.stage, "note": note})
        log.append(f"{sid}: note '{note}'")
    return log


def _candidate_name(state: State, sid: str, tag: str) -> str:
    for c in state.shot(sid)["candidates"]:
        if c.endswith(f"_{tag}.png"):
            return c
    raise ValueError(f"{sid}: no candidate tagged '{tag}' ({', '.join(state.shot(sid)['candidates']) or 'none'})")
