import json

import pytest
from PIL import Image

from videogen import cli, config, media, remote
from videogen.character import CHAR, prompts_for
from videogen.feedback import apply, parse
from videogen.stages import Project, keyframes
from videogen.state import State

LRC = "[00:06.00]一二三四五\n[00:10.00]上山打老虎\n[00:14.00]老虎打不到\n[00:17.00]打到小松鼠\n"


@pytest.fixture
def fresh(tmp_path):
    """A project made by `videogen init` with a (fake) performance video."""
    video = tmp_path / "take.MP4"
    video.write_bytes(b"not really a video")
    d = tmp_path / "new-song"
    cli.main(["--project", str(d), "init", "--title", "新歌", "--video", str(video)])
    return d


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_init_creates_a_project_and_refuses_to_overwrite_it(fresh, tmp_path):
    cfg = _json(fresh / "project.json")
    assert cfg["title"] == "新歌" and cfg["source_video"] == cfg["audio"] == "assets/source.mp4"
    assert (fresh / "assets" / "source.mp4").exists() and "medium" in cfg["crops"]
    assert "HE_DESIGN" in _json(fresh / "prompts.json")["vars"]
    with pytest.raises(SystemExit, match="already exists"):
        cli.main(["--project", str(fresh), "init", "--title", "x", "--video", str(tmp_path / "take.MP4")])
    with pytest.raises(SystemExit, match="--video"):
        cli.main(["--project", str(tmp_path / "empty"), "init", "--title", "x"])


def test_a_new_project_reports_its_missing_storyboard(fresh):
    p = Project(config.load(fresh))
    assert p.problems() == ["storyboard.json missing: run `videogen storyboard --lyrics FILE`"]


def test_storyboard_command_drafts_from_lrc(fresh, tmp_path, capsys):
    lrc = tmp_path / "song.lrc"
    lrc.write_text(LRC, encoding="utf-8")
    cli.main(["--project", str(fresh), "storyboard", "--lyrics", str(lrc), "--duration", "30", "--offset", "1"])
    out = capsys.readouterr().out
    assert "intro" in out and "shots drafted" in out

    sb = _json(fresh / "storyboard.json")
    assert sb["song"] == "新歌" and sb["shots"][-1]["end"] == 30
    assert sb["shots"][1]["lyrics"] == ["一二三四五"] and sb["shots"][1]["start"] == 7.0  # offset applied
    assert _json(fresh / "project.json")["lyrics_ass"] == "assets/lyrics.ass"
    assert "上山打老虎" in (fresh / "assets" / "lyrics.ass").read_text(encoding="utf-8")
    stubs = _json(fresh / "prompts.json")["shots"]
    assert all(s["id"] in stubs for s in sb["shots"] if s["kind"] != "perform")

    with pytest.raises(SystemExit, match="--force"):
        cli.main(["--project", str(fresh), "storyboard", "--lyrics", str(lrc), "--duration", "30"])
    prompts = _json(fresh / "prompts.json")
    prompts["shots"]["S01"] = {"keyframe": "written", "motion": "written"}
    (fresh / "prompts.json").write_text(json.dumps(prompts), encoding="utf-8")
    cli.main(["--project", str(fresh), "storyboard", "--force", "--duration", "30"])  # re-reads lyrics.ass
    assert _json(fresh / "prompts.json")["shots"]["S01"]["keyframe"] == "written"


def test_stages_refuse_to_run_on_unwritten_text(fresh, tmp_path):
    lrc = tmp_path / "song.lrc"
    lrc.write_text(LRC, encoding="utf-8")
    cli.main(["--project", str(fresh), "storyboard", "--lyrics", str(lrc), "--duration", "30"])
    p = Project(config.load(fresh))
    with pytest.raises(SystemExit, match="storyboard.S01.light_prompt"):
        keyframes(p)
    assert any(t.startswith("still TODO") for t in p.problems())


def test_parse_duration_from_the_ffmpeg_banner():
    banner = "Input #0, mov,mp4\n  Duration: 00:03:42.80, start: 0.000000, bitrate: 2815 kb/s\n"
    assert media.parse_duration(banner) == pytest.approx(222.8)
    assert media.parse_duration("no such line") is None


# ---------------------------------------------------------------------------------------------- character
def _with_character_prompts(project, **over):
    prompts = _json(project / "prompts.json")
    prompts["vars"]["HE_DESIGN"] = "a gentle young man"
    prompts["character"] = {"sheet": "Portrait of {HE_DESIGN}. {outfit}.",
                            "outfits": {"A": "navy coat", "B": "TODO: second outfit"}, **over}
    (project / "prompts.json").write_text(json.dumps(prompts, ensure_ascii=False), encoding="utf-8")
    return Project(config.load(project))


def test_character_prompts_need_only_what_the_sheet_uses(fresh):
    p = _with_character_prompts(fresh)  # vars.HE (used later by keyframes) is still TODO: not needed here
    with pytest.raises(SystemExit, match="prompts.character.outfits.B"):
        prompts_for(p)
    p = _with_character_prompts(fresh, outfits={"A": "navy coat"})
    text = prompts_for(p, note="older")["A"]
    assert text.startswith("Portrait of a gentle young man. navy coat.") and text.endswith("Revision request: older")
    with pytest.raises(SystemExit, match="unknown outfit Z"):
        prompts_for(p, ["Z"])


def _character_candidates(project):
    st = State(project / "work" / "state.json")
    (project / "work" / "character").mkdir(parents=True)
    for tag, color in (("A_s1", (200, 0, 0)), ("A_s2", (0, 200, 0))):
        Image.new("RGB", (16, 16), color).save(project / "work" / "character" / f"char_{tag}.png")
        st.add_candidate(CHAR, f"character/char_{tag}.png")
    st.save()


def test_picking_a_character_installs_it_as_the_reference(fresh, tmp_path, capsys):
    _character_candidates(fresh)
    cli.main(["--project", str(fresh), "review", "character"])
    page = (fresh / "work" / "review" / "character.html").read_text(encoding="utf-8")
    assert 'data-value="A_s2"' in page

    fb = tmp_path / "fb.txt"
    fb.write_text("videogen-feedback stage=character\npick character=A_s2\n", encoding="utf-8")
    cli.main(["--project", str(fresh), "feedback", "--file", str(fb)])
    assert "character reference ->" in capsys.readouterr().out
    assert Image.open(fresh / "assets" / "character.png").getpixel((0, 0)) == (0, 200, 0)


def test_character_redo_and_storyboard_notes_through_feedback(tmp_path):
    st = State(tmp_path / "state.json")
    log = apply(parse("videogen-feedback stage=character\nredo character: 年紀大一點\n"), st)
    assert st.shot(CHAR)["redo"] == {"stage": "character", "note": "年紀大一點"} and log
    apply(parse("videogen-feedback stage=storyboard\nredo S03: 換成海邊\nnote S04: 慢一點\n"), st)
    assert st.shot("S03")["redo"] is None  # storyboard feedback never queues a GPU redo
    assert [n["note"] for n in st.shot("S03")["notes"]] == ["換成海邊"]
    assert st.shot("S04")["notes"][0]["stage"] == "storyboard"


def test_storyboard_review_page_marks_todos(fresh, tmp_path):
    lrc = tmp_path / "song.lrc"
    lrc.write_text(LRC, encoding="utf-8")
    cli.main(["--project", str(fresh), "storyboard", "--lyrics", str(lrc), "--duration", "30"])
    cli.main(["--project", str(fresh), "review", "storyboard"])
    page = (fresh / "work" / "review" / "storyboard.html").read_text(encoding="utf-8")
    assert 'class="tl"' in page and 'class="todo"' in page and "上山打老虎" in page
    assert 'class="redo"' not in page  # notes only


def test_bundle_works_before_a_storyboard_exists_and_uploads_design_refs(fresh, tmp_path):
    (fresh / "assets" / "me.jpg").write_bytes(b"jpg")
    raw = _json(fresh / "project.json")
    raw["character_design"] = {"refs": ["assets/me.jpg"]}
    (fresh / "project.json").write_text(json.dumps(raw), encoding="utf-8")
    files = remote.bundle(config.load(fresh), {"kind": "rcs"}, ["character"], tmp_path / "job")
    assert "project/assets/me.jpg" in files and "project/storyboard.json" not in files
