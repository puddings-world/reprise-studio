"""`videogen init` and `videogen storyboard`: start a project, then draft its storyboard from timed lyrics.

Everything the author still has to write is marked TODO; `doctor` lists it and the GPU stages refuse to run
on it, so a half-written project fails early with a list instead of producing odd images.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import config, draft, lyrics, media

PROMPTS_TEMPLATE = {
    "style": "modern Japanese TV anime film still, cel shading, clean thin lineart, painterly background, "
             "cinematic composition, high quality",
    "negative_image": "photo, realistic, deformed face, extra fingers, noise, grain, oversharpened, text, watermark",
    "negative_video": "photo, realistic, flicker, deformed face, distorted eyes, melting, extra limbs, extra fingers, "
                      "text, subtitles, watermark, glitch, noise, static frame",
    "negative_i2v_extra": "standing up, walking out of frame, sudden movement, scene change",
    "vars": {
        "HE": "TODO: the protagonist as the models should see him or her, e.g. 'the anime young man from image 1 "
              "(same face, short black hair, narrow dark eyes)'",
        "OUTFIT": "TODO: the outfit, e.g. 'wearing a navy wool coat and a grey scarf'",
    },
    "character_var": "HE",
    "character": {
        "sheet": "Anime character portrait of {HE_DESIGN}: front view, head and shoulders, eyes open looking at the "
                 "viewer, calm expression, plain pale background. {outfit}.",
        "outfits": {"A": "TODO: outfit A, e.g. 'He wears a navy wool coat over a cream knit sweater'"},
    },
    "framing": {"medium": "medium shot from the waist up"},
    "perform_ref": "Redraw image 2 as an anime film still. Replace the real person in image 2 with {HE}, {OUTFIT}. "
                   "Keep exactly the pose, head angle, eyes, mouth shape, the hands and what they hold, and the "
                   "framing of image 2. Remove all text. Background: {framing}. Lighting: {light}.",
    "perform_motion": "TODO: one line for every performance shot, e.g. 'an anime young man in a navy coat sings "
                      "softly, small dim stage, {light}, anime cel shading'",
    "expression_edit": "",
    "face_mood": "",
    "shots": {},
    "cover": "TODO: the cover key visual; leave the title side calm",
}
DESIGN_VAR = ("HE_DESIGN", "TODO: who the protagonist is before a reference image exists, e.g. 'a gentle anime "
                           "young man in his late twenties, short messy black hair, narrow dark brown eyes'")


def init(project: Path, title: str, name: str | None = None, video: Path | None = None,
         audio: Path | None = None) -> list[Path]:
    """Create project.json, prompts.json and assets/ (media is copied in). Refuses to overwrite a project."""
    if (project / "project.json").exists():
        raise SystemExit(f"{project / 'project.json'} already exists")
    if not video and not audio:
        raise SystemExit("give --video (a performance recording) or --audio (the song alone)")
    assets = project / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    cfg: dict = {"name": name or project.name, "title": title, "character": "assets/character.png"}
    made = []
    if video:
        dst = assets / ("source" + video.suffix.lower())
        shutil.copy(video, dst); made.append(dst)
        cfg["source_video"] = cfg["audio"] = f"assets/{dst.name}"
        # Fractions of the source frame (x0, y0, x1, y1); trim burned-in subtitles or a watermark here.
        cfg["crops"] = {"medium": [0.0, 0.0, 1.0, 1.0]}
    if audio:
        dst = assets / ("audio" + audio.suffix.lower())
        shutil.copy(audio, dst); made.append(dst)
        cfg["audio"] = f"assets/{dst.name}"
    cfg["hosts"] = {"local": {"kind": "local"}}
    cfg["cover"] = {"title": title, "subtitle": "", "side": "left"}
    prompts = json.loads(json.dumps(PROMPTS_TEMPLATE))
    prompts["vars"][DESIGN_VAR[0]] = DESIGN_VAR[1]
    _write(project / "project.json", cfg)
    _write(project / "prompts.json", prompts)
    return [project / "project.json", project / "prompts.json", *made]


def storyboard(cfg: dict, lyrics_file: Path | None = None, offset: float = 0.0, duration: float | None = None,
               force: bool = False) -> dict:
    """Draft storyboard.json (and prompt stubs) from timed lyrics; returns the storyboard.

    With `lyrics_file` the lyrics are converted to assets/lyrics.ass (shifted by `offset`) and project.json
    is pointed at it, so the assembler burns in exactly the timing the storyboard was drafted from.
    """
    proj = Path(cfg["project_dir"])
    if (proj / "storyboard.json").exists() and not force:
        raise SystemExit("storyboard.json already exists; pass --force to replace it (prompts.json entries are kept)")
    if lyrics_file:
        lines = lyrics.load(lyrics_file, offset)
    elif cfg.get("lyrics_ass"):
        lines = lyrics.load(config.resolve(cfg, "lyrics_ass"), offset)
    else:
        raise SystemExit("no lyrics: pass --lyrics FILE (.lrc, .ass or .srt)")
    if duration is None:
        media_key = "audio" if cfg.get("audio") else "source_video"
        if not cfg.get(media_key):
            raise SystemExit("no audio or video in project.json to measure the song; pass --duration")
        duration = media.probe_duration(config.resolve(cfg, media_key))
    perform = bool(cfg.get("source_video") and cfg.get("crops"))
    sb = draft.draft(lines, duration, cfg.get("crops", {}), perform, cfg.get("draft"))
    sb["song"] = cfg.get("title", "")

    if lyrics_file:
        ass = proj / "assets" / "lyrics.ass"
        ass.parent.mkdir(parents=True, exist_ok=True)
        ass.write_text(lyrics.to_ass(lines, tuple(cfg["output_size"]), cfg["lyrics_style"]), encoding="utf-8")
        project_file = proj / "project.json"
        raw = json.loads(project_file.read_text(encoding="utf-8"))
        raw["lyrics_ass"] = "assets/lyrics.ass"
        _write(project_file, raw)

    prompts_file = proj / "prompts.json"
    prompts = json.loads(prompts_file.read_text(encoding="utf-8")) if prompts_file.exists() else \
        json.loads(json.dumps(PROMPTS_TEMPLATE))
    prompts["shots"] = draft.prompt_stubs(sb, prompts.get("shots", {}))
    _write(prompts_file, prompts)
    _write(proj / "storyboard.json", {"song": sb.pop("song"), **sb})
    return sb


def summary(sb: dict) -> str:
    """One line per section: time span, shot count and the kind rhythm (P perform, S story, I image)."""
    rows, cur = [], None
    for s in sb["shots"]:
        if s["section"] != (cur and cur["section"]):
            cur = {"section": s["section"], "start": s["start"], "end": s["end"], "kinds": ""}
            rows.append(cur)
        cur["end"] = s["end"]
        cur["kinds"] += s["kind"][0].upper()
    return "\n".join(f"{r['section']:10} {r['start']:6.1f}–{r['end']:6.1f}s  {len(r['kinds']):2} shots  {r['kinds']}"
                     for r in rows)


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
