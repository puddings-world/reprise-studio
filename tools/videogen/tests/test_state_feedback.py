import pytest

from videogen import feedback
from videogen.state import State
from conftest import SHOTS


@pytest.fixture
def st(tmp_path):
    s = State(tmp_path / "state.json")
    for sid in ("S01", "S02", "S03"):
        s.add_candidate(sid, f"keys/{sid}_s1.png")
        s.add_candidate(sid, f"keys/{sid}_s2.png")
    return s


def test_first_candidate_is_default_pick_and_state_round_trips(st, tmp_path):
    assert st.shot("S01")["pick"] == "keys/S01_s1.png"
    st.save()
    assert State(tmp_path / "state.json").shot("S01")["candidates"] == ["keys/S01_s1.png", "keys/S01_s2.png"]


def test_changing_pick_invalidates_edit_and_clip(st):
    s = st.shot("S02"); s["edit"], s["clip"] = "keys/S02_edit0.png", "clips/S02_v0.mp4"
    st.set_pick("S02", "keys/S02_s2.png")
    assert (s["edit"], s["clip"]) == (None, None)


def test_pick_must_be_an_existing_candidate(st):
    with pytest.raises(ValueError, match="not a candidate"):
        st.set_pick("S01", "keys/S01_s9.png")


def test_redo_seeds_are_fresh(st):
    assert st.next_seeds("S01", 2, [1, 2]) == [3, 4]
    fresh = State(st.path.parent / "other.json")
    assert fresh.next_seeds("S09", 2, [1, 2]) == [1, 2]


def test_pending_follows_missing_work_and_redo(st):
    assert st.pending(SHOTS, "keyframes") == []
    st.request_redo("S03", "keyframes", "more snow")
    assert st.pending(SHOTS, "keyframes") == ["S03"]
    assert st.pending(SHOTS, "clips") == ["S01", "S02", "S03"]
    assert st.take_redo("S03", "keyframes") == "more snow"
    assert st.take_redo("S03", "keyframes") is None


def test_image_for_prefers_accepted_edit(st):
    s = st.shot("S02"); s["edit"] = "keys/S02_edit0.png"
    assert st.image_for("S02") == "keys/S02_edit0.png"
    s["use_edit"] = False
    assert st.image_for("S02") == "keys/S02_s1.png"


# ---------------------------------------------------------------- feedback parsing
CANONICAL = """videogen-feedback stage=keyframes
pick S01=s2 S02=s1 S03=s1
redo S03: only the two of them from behind, far away
note S01: keep, but more stars
"""


def test_parse_canonical_page_output():
    fb = feedback.parse(CANONICAL)
    assert fb.stage == "keyframes"
    assert fb.picks == {"S01": "s2", "S02": "s1", "S03": "s1"}
    assert fb.redo == {"S03": "only the two of them from behind, far away"}
    assert fb.notes == {"S01": "keep, but more stars"}


def test_parse_first_review_page_legacy_format():
    text = '選圖 {"S01":1,"S16":2}\n重畫/備註：\nS16：只要兩個背影\nS05（選 2，備註）：再暗一點'
    fb = feedback.parse(text)
    assert fb.picks == {"S01": "s1", "S16": "s2"}
    assert fb.redo == {"S16": "只要兩個背影"}
    assert fb.notes == {"S05": "再暗一點"}


def test_parse_edit_stage_and_bare_redo():
    fb = feedback.parse("videogen-feedback stage=edit\nedit-off S02 S03\nredo S01")
    assert fb.stage == "edit" and fb.edit_off == {"S02", "S03"} and fb.redo == {"S01": ""}


def test_apply_sets_picks_and_queues_redo(st):
    log = feedback.apply(feedback.parse(CANONICAL), st)
    assert st.shot("S01")["pick"] == "keys/S01_s2.png"
    assert st.shot("S03")["redo"] == {"stage": "keyframes", "note": "only the two of them from behind, far away"}
    assert st.shot("S03")["pick"] == "keys/S03_s1.png"  # redo wins over a pick for the same shot
    assert any(line.startswith("S03: redo keyframes") for line in log)
    assert st.shot("S01")["notes"][-1]["note"] == "keep, but more stars"


def test_apply_edit_off_drops_the_clip(st):
    st.shot("S02")["clip"] = "clips/S02_v0.mp4"
    feedback.apply(feedback.parse("videogen-feedback stage=edit\nedit-off S02"), st)
    assert st.shot("S02")["use_edit"] is False and st.shot("S02")["clip"] is None


def test_apply_rejects_unknown_candidate(st):
    with pytest.raises(ValueError, match="no candidate tagged 's7'"):
        feedback.apply(feedback.parse("pick S01=s7"), st)
