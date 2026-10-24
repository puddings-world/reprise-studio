import json

import numpy as np
import pytest
from PIL import Image

from videogen import hardware, media
from videogen.hardware import Device
from videogen.stages import Project, blend_in, lyrics_ass
from videogen import config


# ---------------------------------------------------------------- hardware planning
def test_big_gpu_keeps_everything_resident():
    assert hardware.plan("i2v", Device("cuda", 75, 80)).placement == "gpu"


def test_shared_gpu_swaps_whole_components():
    # 38 GB free on a shared H100: Qwen-Image-2.1's 17 GB encoder fits, the whole pipeline does not
    assert hardware.plan("image", Device("cuda", 38, 80)).placement == "model_offload"


def test_small_gpu_streams_blocks():
    assert hardware.plan("edit", Device("cuda", 38, 80)).placement == "group_offload"
    assert hardware.plan("animate", Device("cuda", 24, 24)).placement == "group_offload"


def test_animate_kv_cache_moves_to_cpu_when_it_does_not_fit():
    kv = hardware.animate_kv_gb(960, 528)
    assert 25 < kv < 40  # the ~34 GB that made the pilot OOM
    assert hardware.plan("animate", Device("cuda", 38, 80), kv).kv_on_cpu
    assert not hardware.plan("animate", Device("cuda", 140, 141), kv).kv_on_cpu


def test_free_gpu_keeps_weights_resident_and_spills_only_the_kv_cache():
    # an idle 80 GB card: 44 GB of Animate-2 weights fit, the extra 34 GB K/V cache does not
    pl = hardware.plan("animate", Device("cuda", 84.5, 85), hardware.animate_kv_gb(960, 528))
    assert pl.placement == "gpu" and pl.kv_on_cpu


def test_cpu_device_still_gets_a_plan():
    assert "CPU only" in hardware.plan("i2v", Device("cpu", 0, 0)).reason


# ---------------------------------------------------------------- media math
def test_crop_box_is_even_pixels():
    assert media.crop_box([0.16, 0.03, 0.88, 0.524], 1258, 1032) == (904, 508, 201, 30)


def test_even_trims_odd_edges():
    assert media.even(np.zeros((2, 519, 945, 3), np.uint8)).shape == (2, 518, 944, 3)


def test_fit_trims_long_clips_and_stretches_short_ones():
    clip = np.arange(10, dtype=np.uint8).reshape(10, 1, 1, 1).repeat(3, -1)
    assert media.fit(clip, 4)[:, 0, 0, 0].tolist() == [0, 1, 2, 3]
    slow = media.fit(clip[:3], 5)[:, 0, 0, 0]
    assert slow.tolist() == [0.0, 0.5, 1.0, 1.5, 2.0]


@pytest.mark.parametrize("shape", [(1, 4, 6, 8, 3), (4, 3, 6, 8), (3, 4, 6, 8)])
def test_to_uint8_normalises_layouts(shape):
    out = media.to_uint8(np.full(shape, 0.5, np.float32))
    assert out.shape == (4, 6, 8, 3) and out.dtype == np.uint8 and out[0, 0, 0, 0] == 128


def test_contact_strip_tiles_frames():
    frames = np.zeros((20, 90, 160, 3), np.uint8)
    assert media.contact_strip(frames, 5, 80).shape == (45, 400, 3)


# ---------------------------------------------------------------- assembly helpers
def test_blend_in_crossfades_from_the_previous_shot():
    cur = np.full((4, 1, 1, 3), 200.0); tail = np.zeros((2, 1, 1, 3))
    out = blend_in(cur, tail, "dissolve")
    assert out[0, 0, 0, 0] == pytest.approx(200 / 3) and out[1, 0, 0, 0] == pytest.approx(400 / 3)
    assert out[2, 0, 0, 0] == 200.0


def test_light_swell_brightens_mid_transition():
    cur = np.full((3, 1, 1, 3), 100.0); tail = np.full((3, 1, 1, 3), 100.0)
    assert blend_in(cur, tail, "light swell")[1, 0, 0, 0] > 100


def test_lyrics_ass_rescaled_and_restyled(tmp_path):
    src = tmp_path / "in.ass"
    src.write_text("﻿[Script Info]\nPlayResX: 1260\nPlayResY: 1032\n\n[V4+ Styles]\n"
                   "Style: Lyric,Noto Serif TC,54,&H00F4F1EE,&H00F4F1EE,&H60301810,&H80000000,-1,0,0,0,100,100,6,0,1,"
                   "2.2,2,2,60,60,70,1\n\n[Events]\nDialogue: 0,0:00:00.15,0:00:03.00,Lyric,,0,0,0,,上天啊\n",
                   encoding="utf-8")
    lyrics_ass(src, tmp_path / "out.ass", (1280, 720), {"font": "Noto Serif TC", "size": 40, "margin_v": 42})
    out = (tmp_path / "out.ass").read_text(encoding="utf-8")
    assert "PlayResX: 1280" in out and "PlayResY: 720" in out
    assert "Style: Lyric,Noto Serif TC,40," in out and out.split("Style: Lyric")[1].split("\n")[0].endswith(",42,1")
    assert "上天啊" in out


# ---------------------------------------------------------------- project + review page
def test_project_problems_list_missing_assets(project):
    p = Project(config.load(project, environ={}))
    assert any("source_video" in m and "does not exist" in m for m in p.problems())


def test_review_page_lists_candidates_and_emits_feedback_format(project):
    from videogen.review import build
    p = Project(config.load(project, environ={}))
    (p.work / "keys").mkdir(parents=True)
    for sid in ("S01", "S02", "S03"):
        for k in (1, 2):
            Image.new("RGB", (64, 36), (k * 60, 0, 0)).save(p.work / "keys" / f"{sid}_s{k}.png")
            p.state.add_candidate(sid, f"keys/{sid}_s{k}.png")
    page = build(p, "keyframes").read_text(encoding="utf-8")
    assert page.count('class="shot ') == 3
    assert 'data-shot="S02" data-value="s2"' in page
    assert "videogen-feedback stage=" in page and "<title>測試歌 · keyframes</title>" in page


# ---------------------------------------------------------------- regressions from the first remote run
BANNER = ("  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(progressive), "
          "1258x1032 [SAR 1:1 DAR 629:516], 3612 kb/s, 60 fps, 60 tbr, 15360 tbn (default)\n")


def test_video_size_ignores_codec_tags():
    # '0x31637661' was read as a 0 x 31637661 frame, producing crop=0:21703434
    assert media.parse_video_size(BANNER) == (1258, 1032)
    assert media.parse_video_size("  Stream #0:0: Audio: aac, 44100 Hz\n") is None


def test_failed_host_stage_is_an_error_not_a_silent_success(tmp_path):
    from videogen import remote
    results, work = tmp_path / "results", tmp_path / "work"
    (results / "clips").mkdir(parents=True)
    (results / "clips" / "S01_v0.mp4").write_bytes(b"x")
    (results / remote.FAIL_MARKER).write_text("t")
    with pytest.raises(SystemExit, match="remote stage failed; kept 2 partial files"):
        remote.sync_back(results, work)
    assert (work / "clips" / "S01_v0.mp4").exists()  # finished shots are still kept
    with pytest.raises(SystemExit, match="returned no result"):
        remote.sync_back(tmp_path / "nothing", work)


def test_finished_host_stage_syncs_without_markers(tmp_path):
    from videogen import remote
    results, work = tmp_path / "results", tmp_path / "work"
    results.mkdir()
    (results / "state.json").write_text("{}")
    (results / remote.OK_MARKER).write_text("t")
    assert remote.sync_back(results, work) == 1
    assert not (work / remote.OK_MARKER).exists()
