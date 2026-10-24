import json
import subprocess

import numpy as np
import pytest

from videogen import config, media
from videogen.stages import Project, assemble


def _has_libass() -> bool:
    try:
        out = subprocess.run([media.ffmpeg_exe(), "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    except (OSError, SystemExit):
        return False
    return " ass " in out


@pytest.mark.skipif(not _has_libass(), reason="needs an ffmpeg build with libass")
def test_assemble_cuts_clips_burns_lyrics_and_muxes_audio(project):
    """End to end on tiny clips. On Windows the tmp path has a drive letter, which once broke the ass filter."""
    cfg_file = project / "project.json"
    cfg = json.loads(cfg_file.read_text("utf-8"))
    cfg.update(output_size=[64, 36], fps=12, transition_frames=2, audio="assets/tone.m4a", lyrics_ass="assets/l.ass")
    cfg_file.write_text(json.dumps(cfg), "utf-8")
    subprocess.run([media.ffmpeg_exe(), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                    "-c:a", "aac", str(project / "assets" / "tone.m4a")], check=True)
    (project / "assets" / "l.ass").write_text(
        "[Script Info]\nPlayResX: 1260\nPlayResY: 1032\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, "
        "PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Lyric,Arial,54,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:01.00,0:00:03.00,Lyric,,0,0,0,,上天啊\n", encoding="utf-8")
    p = Project(config.load(project, environ={}))
    for i, s in enumerate(p.shots()):
        name = f"clips/{s['id']}_v0.mp4"
        frames = np.full((10, 36, 64, 3), 60 * (i + 1), np.uint8)  # shorter than the slot: exercises slow-down
        media.write_video(frames, p.work / name, 12)
        p.state.shot(s["id"])["clip"] = name
    out = assemble(p)
    banner = subprocess.run([media.ffmpeg_exe(), "-hide_banner", "-i", str(out)], capture_output=True,
                            text=True).stderr
    assert "Video: h264" in banner and "Audio: aac" in banner
    assert "Duration: 00:00:06" in banner or "Duration: 00:00:05.9" in banner


def test_assemble_refuses_until_every_shot_has_a_clip(project):
    p = Project(config.load(project, environ={}))
    with pytest.raises(SystemExit, match="no clip yet for S01, S02, S03"):
        assemble(p)
