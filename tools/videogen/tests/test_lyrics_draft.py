import pytest

from videogen import draft, lyrics
from videogen.lyrics import Line
from videogen.storyboard import validate

STYLE = {"font": "Noto Serif TC", "size": 40, "margin_v": 42}


# ---------------------------------------------------------------------------------------------- lyrics
def test_lrc_handles_metadata_repeated_tags_and_phrase_ends():
    text = "[ti:歌]\n[00:01.00]第一句\n[00:04.50]\n[00:10.00][01:00.00]副歌\n[00:20.00]最後\n"
    lines = lyrics.parse_lrc(text)
    assert [(ln.start, ln.end, ln.text) for ln in lines] == [
        (1.0, 4.5, "第一句"), (10.0, 20.0, "副歌"), (20.0, 60.0, "最後"), (60.0, None, "副歌")]


def test_ass_strips_overrides_and_survives_a_stray_form_feed():
    # A broken "\fad" written through a Python string becomes a form feed; it must not split the line.
    text = ("[Events]\nDialogue: 0,0:00:00.15,0:00:03.00,Lyric,,0,0,0,,{\x0cad(250,300)}上天啊\n"
            "Dialogue: 0,0:01:03.15,0:01:07.20,Lyric,,0,0,0,,{\\fad(250,300)}一,二\\N三\n")
    assert [(ln.start, ln.end, ln.text) for ln in lyrics.parse_ass(text)] == [
        (0.15, 3.0, "上天啊"), (63.15, 67.2, "一,二 三")]


def test_srt_blocks():
    text = "1\n00:00:01,000 --> 00:00:03,500\n<i>第一句</i>\n\n2\n00:00:04,000 --> 00:00:06,000\n第二\n句\n"
    assert [(ln.start, ln.end, ln.text) for ln in lyrics.parse_srt(text)] == [
        (1.0, 3.5, "第一句"), (4.0, 6.0, "第二 句")]


def test_load_shifts_by_offset_and_drops_lines_before_zero(tmp_path):
    f = tmp_path / "a.lrc"
    f.write_text("[00:01.00]早\n[00:05.00]晚\n", encoding="utf-8")
    assert [(ln.start, ln.text) for ln in lyrics.load(f, offset=-2)] == [(3.0, "晚")]
    with pytest.raises(SystemExit, match="must be one of"):
        lyrics.load(tmp_path / "a.txt")


def test_to_ass_round_trips_and_never_overlaps():
    lines = [Line(1.0, 9.0, "一"), Line(5.0, 7.0, "二"), Line(10.0, None, "三")]
    back = lyrics.parse_ass(lyrics.to_ass(lines, (1280, 720), STYLE))
    assert [ln.text for ln in back] == ["一", "二", "三"]
    assert back[0].end == pytest.approx(4.85) and back[2].end == pytest.approx(16.0)
    assert "PlayResX: 1280" in lyrics.to_ass(lines, (1280, 720), STYLE)


# ---------------------------------------------------------------------------------------------- draft
def test_a_repeated_pair_is_chorus_but_a_lone_refrain_is_not():
    texts = ["上天啊", "第一段", "副歌一", "副歌二", "上天啊", "第二段", "副歌一", "副歌二"]
    assert draft.chorus_flags(texts) == [False, False, True, True, False, False, True, True]


def _song():
    # 6 s intro, four lines, an 11 s instrumental break, two lines, 8 s outro
    return [Line(6.0, None, "一二三四五"), Line(10.0, None, "上山打老虎"), Line(14.0, None, "老虎打不到"),
            Line(17.0, None, "打到小松鼠"), Line(31.0, None, "松鼠有幾隻"), Line(35.0, None, "讓我數一數")], 47.0


def test_segments_cover_the_song_and_break_out_silences():
    lines, dur = _song()
    segs = draft.segments(lines, dur, draft.DRAFT_DEFAULTS)
    assert segs[0].start == 0 and segs[-1].end == dur
    assert all(a.end == pytest.approx(b.start) for a, b in zip(segs, segs[1:]))
    names = draft.section_names(segs)
    assert names[0] == "intro" and names[-1] == "outro" and "interlude" in names
    for s in segs:
        assert s.end - s.start <= draft.DRAFT_DEFAULTS["max_shot"] + 1e-9


def test_short_lines_merge_and_long_ones_split():
    d = {**draft.DRAFT_DEFAULTS, "min_gap": 100}
    segs = draft.segments([Line(0.0, None, "啊"), Line(1.0, None, "一"), Line(3.0, None, "很長的一句")], 30.0, d)
    assert segs[0].lyrics == ["啊", "一"]
    # the last line runs to the end of the song (27 s): four parts of at most 8 s, the lyric on the first
    assert segs[1].lyrics == ["很長的一句"] and len(segs) == 5
    assert all(not s.lyrics and s.hold for s in segs[2:])


def test_draft_is_a_valid_storyboard_with_a_kind_rhythm():
    lines, dur = _song()
    crops = {"close": [0, 0, 1, 1], "medium": [0, 0, 1, 1]}
    sb = draft.draft(lines, dur, crops, perform=True)
    assert validate(sb, crops) == []
    shots = sb["shots"]
    assert shots[0]["kind"] == "image" and shots[0]["transition_in"] == "fade from black"
    sung = [s for s in shots if s["lyrics"]]
    assert sung[0]["kind"] == "perform" and sung[1]["kind"] == "story"
    assert [s["framing"] for s in shots if s["kind"] == "perform"][:2] == ["close", "medium"]
    assert all(s["light_prompt"] == draft.TODO for s in shots)


def test_without_a_performance_video_there_are_no_perform_shots():
    lines, dur = _song()
    sb = draft.draft(lines, dur, {}, perform=False)
    assert validate(sb) == [] and {s["kind"] for s in sb["shots"]} <= {"story", "image"}


def test_prompt_stubs_keep_written_entries():
    sb = {"shots": [{"id": "S01", "kind": "image", "lyrics": [], "section": "intro"},
                    {"id": "S02", "kind": "perform", "lyrics": ["唱"], "section": "verse1"},
                    {"id": "S03", "kind": "story", "lyrics": ["一", "二"], "section": "verse1"}]}
    out = draft.prompt_stubs(sb, {"S01": {"keyframe": "stars", "motion": "twinkle"}})
    assert out["S01"]["keyframe"] == "stars" and "S02" not in out
    assert out["S03"] == {"keyframe": "TODO: 一／二", "motion": "TODO"}


def test_todos_lists_dotted_paths():
    assert draft.todos({"a": "ok", "b": {"c": "TODO: x", "d": ["fine", "TODO"]}}) == ["b.c", "b.d[1]"]
