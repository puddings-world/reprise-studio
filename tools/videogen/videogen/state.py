"""Per-project production state (work/state.json): candidates, picks, edits, clips and review notes per shot.

Every stage reads and writes this file, which is what makes the loop resumable and lets feedback target
single shots. File names are relative to the work dir.
"""
from __future__ import annotations

import json
from pathlib import Path

EMPTY_SHOT = {"candidates": [], "pick": None, "edit": None, "use_edit": True, "clip": None,
              "redo": None, "notes": []}
STAGES = ("keyframes", "edit", "clips")


class State:
    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"shots": {}, "round": 0}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")

    def shot(self, sid: str) -> dict:
        s = self.data["shots"].setdefault(sid, {})
        for k, v in EMPTY_SHOT.items():
            s.setdefault(k, list(v) if isinstance(v, list) else v)
        return s

    # -- keyframes -------------------------------------------------------------------------------
    def add_candidate(self, sid: str, name: str) -> None:
        s = self.shot(sid)
        if name not in s["candidates"]:
            s["candidates"].append(name)
        if s["pick"] is None:
            s["pick"] = name  # first candidate is the default pick until the owner chooses

    def used_seeds(self, sid: str) -> set[int]:
        return {int(c.rsplit("_s", 1)[1].split(".")[0]) for c in self.shot(sid)["candidates"] if "_s" in c}

    def next_seeds(self, sid: str, count: int, base: list[int]) -> list[int]:
        """Default seeds first; for redo rounds, fresh seeds above everything already tried."""
        used = self.used_seeds(sid)
        free = [b for b in base if b not in used]
        seed = max(used | set(base)) + 1
        while len(free) < count:
            free.append(seed); seed += 1
        return free[:count]

    # -- downstream invalidation -----------------------------------------------------------------
    def set_pick(self, sid: str, name: str) -> None:
        s = self.shot(sid)
        if name not in s["candidates"]:
            raise ValueError(f"{sid}: '{name}' is not a candidate ({', '.join(s['candidates']) or 'none yet'})")
        if s["pick"] != name:
            s["pick"], s["edit"], s["clip"] = name, None, None

    def image_for(self, sid: str) -> str | None:
        s = self.shot(sid)
        return s["edit"] if (s["edit"] and s["use_edit"]) else s["pick"]

    def request_redo(self, sid: str, stage: str, note: str) -> None:
        if stage not in STAGES:
            raise ValueError(f"stage must be one of {STAGES}")
        s = self.shot(sid)
        s["redo"] = {"stage": stage, "note": note}
        s["notes"].append({"round": self.data["round"], "stage": stage, "note": note})
        if stage == "keyframes":
            s["edit"], s["clip"] = None, None
        elif stage == "edit":
            s["clip"] = None
        else:
            s["clip"] = None

    def take_redo(self, sid: str, stage: str) -> str | None:
        """The pending revision note for this stage, cleared once a stage consumes it."""
        s = self.shot(sid)
        if s["redo"] and s["redo"]["stage"] == stage:
            note = s["redo"]["note"]
            s["redo"] = None
            return note
        return None

    def pending(self, shots: list[dict], stage: str) -> list[str]:
        """Shot ids that still need work at a stage."""
        out = []
        for sh in shots:
            s = self.shot(sh["id"])
            redo = s["redo"] and s["redo"]["stage"] == stage
            if stage == "keyframes" and (not s["candidates"] or redo):
                out.append(sh["id"])
            elif stage == "clips" and (not s["clip"] or redo):
                out.append(sh["id"])
        return out
