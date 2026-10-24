import json
from pathlib import Path

import pytest
from PIL import Image

SHOTS = [
    {"id": "S01", "start": 0.0, "end": 2.0, "kind": "image", "light": "night", "light_prompt": "moonlight",
     "transition_in": "fade from black", "lyrics": []},
    {"id": "S02", "start": 2.0, "end": 4.5, "kind": "perform", "framing": "close", "light": "night",
     "light_prompt": "moonlight", "transition_in": "dissolve", "lyrics": ["上天啊"]},
    {"id": "S03", "start": 4.5, "end": 6.0, "kind": "story", "light": "lamp", "light_prompt": "desk lamp",
     "transition_in": "cut", "lyrics": ["有個人在想她"]},
]

PROMPTS = {
    "style": "anime still",
    "negative_image": "photo",
    "negative_video": "flicker",
    "negative_i2v_extra": "walking away",
    "vars": {"HE": "the man from image 1", "COAT": "navy coat"},
    "framing": {"close": "close-up"},
    "perform_ref": "Redraw image 2 with {HE}, {COAT}, {framing}, light {light}.",
    "perform_motion": "he sings, {light}",
    "expression_edit": "make him sadder",
    "face_mood": "quietly sad",
    "shots": {
        "S01": {"keyframe": "Stars over a frozen bay, no people.", "motion": "stars twinkle"},
        "S03": {"keyframe": "{HE} in {COAT} by a window.", "motion": "he reads his phone"},
    },
}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    d = tmp_path / "song"
    (d / "assets").mkdir(parents=True)
    (d / "storyboard.json").write_text(json.dumps({"version": 1, "shots": SHOTS}, ensure_ascii=False), "utf-8")
    (d / "prompts.json").write_text(json.dumps(PROMPTS, ensure_ascii=False), "utf-8")
    (d / "project.json").write_text(json.dumps({
        "name": "song", "title": "測試歌", "character": "assets/character.png", "crops": {"close": [0, 0, 1, 0.5]},
        "face_shots": ["S02", "S03"],
        "hosts": {"local": {"kind": "local"},
                  "gpu": {"kind": "rcs", "workdir": "/remote/work", "paths": {"source_video": "/remote/src.mp4"}}},
        "source_video": "assets/source.mp4",
    }), "utf-8")
    Image.new("RGB", (64, 64), (20, 30, 40)).save(d / "assets" / "character.png")
    return d
