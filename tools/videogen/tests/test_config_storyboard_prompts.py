import json
from pathlib import Path

import pytest

from videogen import config, storyboard
from videogen.prompts import Prompts
from conftest import PROMPTS, SHOTS


# ---------------------------------------------------------------- config
def test_deep_merge_keeps_untouched_nested_keys():
    merged = config.deep_merge({"models": {"image": "a", "i2v": "b"}, "fps": 24}, {"models": {"image": "c"}})
    assert merged == {"models": {"image": "c", "i2v": "b"}, "fps": 24}


@pytest.mark.parametrize("raw, value", [("960x528", [960, 528]), ("1,2,3", [1, 2, 3]), ("/tmp/w", "/tmp/w"),
                                        ("12", 12)])
def test_parse_env_value(raw, value):
    assert config.parse_env_value(raw) == value


def test_layering_defaults_project_env_cli(project):
    cfg = config.load(project, environ={"VIDEOGEN_ANIMATE_SIZE": "832x464"}, cli={"fps": 30})
    assert cfg["animate_size"] == [832, 464]          # env beats default
    assert cfg["fps"] == 30                            # CLI beats everything
    assert cfg["models"]["i2v"] == config.DEFAULTS["models"]["i2v"]
    assert cfg["workdir"] == str(project.resolve() / "work")


def test_host_profile_replaces_paths_and_workdir(project):
    cfg = config.load(project, host="gpu", environ={})
    assert cfg["source_video"] == "/remote/src.mp4"
    assert cfg["workdir"] == "/remote/work"
    assert config.resolve(cfg, "character") == project.resolve() / "assets" / "character.png"


def test_unknown_host_is_a_clear_error(project):
    with pytest.raises(SystemExit, match="unknown host 'nope'"):
        config.load(project, host="nope", environ={})


def test_missing_project_file_says_how_to_fix(tmp_path):
    with pytest.raises(SystemExit, match="project.json not found"):
        config.load(tmp_path, environ={})


# ---------------------------------------------------------------- storyboard
def test_valid_storyboard_has_no_problems():
    assert storyboard.validate({"shots": SHOTS}, {"close": [0, 0, 1, 1]}) == []


def test_storyboard_problems_are_specific():
    bad = [dict(SHOTS[0]), dict(SHOTS[1], start=2.5, framing="wide"), dict(SHOTS[2], kind="dream")]
    problems = storyboard.validate({"shots": bad}, {"close": [0, 0, 1, 1]})
    assert any("S02: starts at 2.5 but previous shot ends at 2.0" in p for p in problems)
    assert any("S02: framing 'wide'" in p for p in problems)
    assert any("S03: kind must be one of" in p for p in problems)


def test_frame_spans_tile_the_song_without_gaps():
    total = sum(storyboard.frame_span(s, 24) for s in SHOTS)
    assert total == round(SHOTS[-1]["end"] * 24)


@pytest.mark.parametrize("n, cap, expected", [(125, None, 125), (124, None, 125), (139, None, 141),
                                              (200, 145, 145), (1, None, 1)])
def test_wan_frames_are_4k_plus_1(n, cap, expected):
    assert storyboard.wan_frames(n, cap) == expected
    assert (expected - 1) % 4 == 0


# ---------------------------------------------------------------- prompts
def test_character_reference_only_when_the_prompt_names_him():
    p = Prompts(PROMPTS)
    assert p.needs_character(SHOTS[1]) and p.needs_character(SHOTS[2])
    assert not p.needs_character(SHOTS[0])


def test_keyframe_prompt_fills_vars_light_style_and_revision():
    text = Prompts(PROMPTS).keyframe(SHOTS[2], "warmer lamp")
    assert text.startswith("the man from image 1 in navy coat by a window.")
    assert "Lighting: desk lamp." in text and "anime still" in text and text.endswith("Revision request: warmer lamp")


def test_perform_prompt_uses_framing_and_light():
    text = Prompts(PROMPTS).image_prompt(SHOTS[1])
    assert "close-up" in text and "light moonlight" in text


def test_motion_adds_mood_only_with_the_protagonist():
    p = Prompts(PROMPTS)
    assert p.motion(SHOTS[2]).endswith("quietly sad")
    assert "quietly sad" not in p.motion(SHOTS[0])
    assert p.motion(SHOTS[1]) == "he sings, moonlight"


def test_i2v_negative_adds_extra_terms():
    assert Prompts(PROMPTS).negative("i2v") == "walking away, flicker"


def test_missing_prompt_entries_are_reported():
    assert Prompts({**PROMPTS, "shots": {}}).missing(SHOTS) == ["S01", "S03"]
