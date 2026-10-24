"""Prompt building from a project's prompts.json.

prompts.json holds every word the models see, so a new song means new data, not new code:

    style, negative_image, negative_video, negative_i2v_extra   strings
    vars        {"HE": "...", "COAT": "...", ...}   placeholders usable in any text below
    character_var  name of the var that marks "this shot needs the character reference" (default "HE")
    framing     {framing key: words}
    perform_ref     template; may use {framing} and {light}
    perform_motion  template; may use {light}
    expression_edit  instruction for the optional expression pass
    face_mood   text appended to I2V motion when the protagonist is on screen
    shots       {shot id: {"keyframe": str, "motion": str}}
"""
from __future__ import annotations

import string


class Prompts:
    def __init__(self, data: dict):
        self.d = data
        self.char_var = data.get("character_var", "HE")

    def _fill(self, text: str, **extra) -> str:
        return string.Formatter().vformat(text, (), {**self.d.get("vars", {}), **extra})

    def uses_character(self, shot_id: str) -> bool:
        return "{" + self.char_var + "}" in self.d["shots"][shot_id]["keyframe"]

    def keyframe(self, shot: dict, revision_note: str = "") -> str:
        text = self._fill(self.d["shots"][shot["id"]]["keyframe"])
        text += f" Lighting: {shot.get('light_prompt', '')}. {self.d['style']}"
        if revision_note:
            text += f" Revision request: {revision_note}"
        return text

    def perform_ref(self, shot: dict, revision_note: str = "") -> str:
        text = self._fill(self.d["perform_ref"], framing=self.d["framing"][shot["framing"]],
                          light=shot.get("light_prompt", ""))
        text += " " + self.d["style"]
        if revision_note:
            text += f" Revision request: {revision_note}"
        return text

    def image_prompt(self, shot: dict, revision_note: str = "") -> str:
        """The still-image prompt for any shot kind."""
        if shot["kind"] == "perform":
            return self.perform_ref(shot, revision_note)
        return self.keyframe(shot, revision_note)

    def needs_character(self, shot: dict) -> bool:
        return shot["kind"] == "perform" or self.uses_character(shot["id"])

    def motion(self, shot: dict) -> str:
        if shot["kind"] == "perform":
            return self._fill(self.d["perform_motion"], light=shot.get("light_prompt", ""))
        text = self._fill(self.d["shots"][shot["id"]]["motion"])
        if self.uses_character(shot["id"]) and self.d.get("face_mood"):
            text += ", " + self.d["face_mood"]
        return text

    def negative(self, kind: str) -> str:
        if kind == "image":
            return self.d.get("negative_image", "")
        neg = self.d.get("negative_video", "")
        return (self.d.get("negative_i2v_extra", "") + ", " + neg) if kind == "i2v" else neg

    @property
    def expression_edit(self) -> str:
        return self.d.get("expression_edit", "")

    def missing(self, shots: list[dict]) -> list[str]:
        """Shot ids that need a prompts.json entry but have none."""
        return [s["id"] for s in shots if s["kind"] != "perform" and s["id"] not in self.d.get("shots", {})]
