"""Production stages. Each one works only on shots that are pending in state.json, so any stage can be re-run
after feedback and only the rejected shots are regenerated.

keyframes  still image candidates per shot (perform shots: a restyled frame of the source video)
edit       optional pass applying `prompts.expression_edit` to picked images that show the protagonist
clips      animate every shot from its approved image
assemble   cut, transitions, lyrics, original audio -> final MV
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

import numpy as np

from . import config, media
from . import storyboard as sbmod
from .prompts import Prompts
from .state import State


class Project:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.dir = Path(cfg["project_dir"])
        self.work = Path(cfg["workdir"])
        self.sb = sbmod.load(self.dir / "storyboard.json")
        self.prompts = Prompts(json.loads((self.dir / "prompts.json").read_text(encoding="utf-8")))
        self.state = State(self.work / "state.json")
        self.fps = cfg["fps"]

    def path(self, key: str) -> Path:
        return config.resolve(self.cfg, key)

    def shots(self, only=None, kinds=None) -> list[dict]:
        return sbmod.select(self.sb["shots"], only, kinds)

    def problems(self) -> list[str]:
        out = sbmod.validate(self.sb, self.cfg.get("crops"))
        out += [f"{sid}: no prompts.json entry" for sid in self.prompts.missing(self.sb["shots"])]
        for key in ("source_video", "character", "lyrics_ass"):
            if key in self.cfg and not self.path(key).exists():
                out.append(f"{key}: {self.path(key)} does not exist")
        return out


def log(*a) -> None:
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def _device():
    from .hardware import detect
    d = detect()
    log(f"device: {d.kind} {d.name} free {d.free_gb:.1f}/{d.total_gb:.1f} GB")
    return d


# --------------------------------------------------------------------------------------------- keyframes
def keyframes(p: Project, only=None, seeds: list[int] | None = None) -> list[str]:
    from PIL import Image
    from .models import ImageModel, free_memory

    todo = [s for s in p.shots(only) if s["id"] in p.state.pending(p.shots(only), "keyframes") or only]
    if not todo:
        log("keyframes: nothing pending"); return []
    seeds = seeds or p.cfg["seeds"]
    w, h = p.cfg["work_size"]
    char = Image.open(p.path("character")).convert("RGB")
    model = ImageModel(p.cfg["models"]["image"], "image", _device())
    log(f"keyframes: {len(todo)} shots, plan {model.plan.placement}")
    made = []
    for s in todo:
        sid, note = s["id"], p.state.take_redo(s["id"], "keyframes")
        images = None
        if s["kind"] == "perform":
            mid = (s["start"] + s["end"]) / 2
            frame = media.read_clip(p.path("source_video"), mid, mid + 0.1, p.fps, p.cfg["crops"][s["framing"]])[0]
            src = p.work / "keys" / f"{sid}_source.png"
            src.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(frame).save(src)
            images = [char, Image.fromarray(frame)]
        elif p.prompts.needs_character(s):
            images = [char]
        prompt = p.prompts.image_prompt(s, note or "")
        for seed in (p.state.next_seeds(sid, len(seeds), seeds) if note else seeds):
            name = f"keys/{sid}_s{seed}.png"
            if not (p.work / name).exists():
                t = time.time()
                model.generate(prompt, images, w, h, p.cfg["steps"]["image"], seed).save(p.work / name)
                log(sid, f"seed {seed}", f"{time.time() - t:.0f}s")
            p.state.add_candidate(sid, name)
            made.append(name)
        if note:  # a redo round: the newest candidate becomes the default pick
            p.state.shot(sid)["pick"] = f"keys/{sid}_s{seed}.png"
        p.state.save()
    del model; free_memory()
    return made


# --------------------------------------------------------------------------------------------- edit
def edit(p: Project, only=None) -> list[str]:
    """Apply the expression edit to picked images of shots where the protagonist's face is visible."""
    from PIL import Image
    from .models import ImageModel, free_memory

    if not p.prompts.expression_edit:
        log("edit: prompts.json has no expression_edit; skipping"); return []
    faces = set(p.cfg.get("face_shots", []))
    todo = []
    for s in p.shots(only):
        st = p.state.shot(s["id"])
        redo = st["redo"] and st["redo"]["stage"] == "edit"
        if s["id"] in faces and st["pick"] and (not st["edit"] or redo):
            todo.append(s)
    if not todo:
        log("edit: nothing pending"); return []
    w, h = p.cfg["work_size"]
    model = ImageModel(p.cfg["models"]["edit"], "edit", _device())
    log(f"edit: {len(todo)} shots, plan {model.plan.placement}")
    made = []
    for s in todo:
        sid, st = s["id"], p.state.shot(s["id"])
        note = p.state.take_redo(sid, "edit")
        prompt = p.prompts.expression_edit + (f" Revision request: {note}" if note else "")
        rnd = len([n for n in st["notes"] if n["stage"] == "edit"])
        name = f"keys/{sid}_edit{rnd}.png"
        t = time.time()
        img = Image.open(p.work / st["pick"]).convert("RGB")
        seed = int(re.search(r"_s(\d+)", st["pick"]).group(1)) + rnd
        model.generate(prompt, [img], w, h, p.cfg["steps"]["edit"], seed,
                       negative=p.prompts.negative("image")).save(p.work / name)
        st["edit"], st["use_edit"], st["clip"] = name, True, None
        p.state.save(); made.append(name)
        log(sid, "edit", f"{time.time() - t:.0f}s")
    del model; free_memory()
    return made


# --------------------------------------------------------------------------------------------- clips
def clips(p: Project, only=None, kinds=None) -> list[str]:
    from PIL import Image
    from .models import AnimateModel, I2VModel, free_memory

    shots = p.shots(only, kinds)
    pending = set(p.state.pending(shots, "clips"))
    todo = [s for s in shots if s["id"] in pending and p.state.image_for(s["id"])]
    made = []
    perform = [s for s in todo if s["kind"] == "perform"]
    if perform:
        aw, ah = p.cfg["animate_size"]
        model = AnimateModel(p.cfg["models"]["animate"], _device(), aw, ah)
        log(f"clips: {len(perform)} perform shots, plan {model.plan.placement}, kv on cpu {model.plan.kv_on_cpu}")
        for s in perform:
            made.append(_clip(p, s, lambda s, img, note: media.to_uint8(model.generate(
                img.resize((aw, ah), Image.LANCZOS),
                [Image.fromarray(f) for f in media.read_clip(p.path("source_video"), s["start"], s["end"], p.fps,
                                                               p.cfg["crops"][s["framing"]], (aw, ah))],
                p.prompts.motion(s) + (f", {note}" if note else ""), p.prompts.negative("video"),
                aw, ah, p.cfg["steps"]["animate"], _seed(p, s), p.fps))))
        del model; free_memory()
    still = [s for s in todo if s["kind"] != "perform"]
    if still:
        w, h = p.cfg["work_size"]
        model = I2VModel(p.cfg["models"]["i2v"], _device())
        log(f"clips: {len(still)} story/image shots, plan {model.plan.placement}")
        for s in still:
            n = sbmod.wan_frames(sbmod.frame_span(s, p.fps), p.cfg["i2v_max_frames"])
            made.append(_clip(p, s, lambda s, img, note: media.to_uint8(model.generate(
                img.resize((w, h), Image.LANCZOS), p.prompts.motion(s) + (f", {note}" if note else ""),
                p.prompts.negative("i2v"), w, h, n, p.cfg["steps"]["i2v"], _seed(p, s)))))
        del model; free_memory()
    return made


def _seed(p: Project, s: dict) -> int:
    st = p.state.shot(s["id"])
    m = re.search(r"_s(\d+)", st["pick"] or "")
    return (int(m.group(1)) if m else 1) + len([n for n in st["notes"] if n["stage"] == "clips"])


def _clip(p: Project, s: dict, gen) -> str:
    from PIL import Image
    sid, st = s["id"], p.state.shot(s["id"])
    note = p.state.take_redo(sid, "clips")
    version = len([n for n in st["notes"] if n["stage"] == "clips"])
    name = f"clips/{sid}_v{version}.mp4"
    t = time.time()
    frames = gen(s, Image.open(p.work / p.state.image_for(sid)).convert("RGB"), note)
    media.write_video(frames, p.work / name, p.fps)
    st["clip"] = name
    p.state.save()
    log(sid, s["kind"], frames.shape, f"{time.time() - t:.0f}s")
    return name


# --------------------------------------------------------------------------------------------- assemble
def lyrics_ass(src: Path, dst: Path, size: tuple[int, int], style: dict) -> None:
    """Rescale a lyrics .ass file to the output size and restyle its Lyric line."""
    text = src.read_text(encoding="utf-8-sig")
    text = re.sub(r"PlayResX:\s*\d+", f"PlayResX: {size[0]}", text)
    text = re.sub(r"PlayResY:\s*\d+", f"PlayResY: {size[1]}", text)

    def restyle(m):
        f = m.group(0).split(",")
        f[1], f[2], f[21] = style["font"], str(style["size"]), str(style["margin_v"])
        return ",".join(f)
    text = re.sub(r"^Style: Lyric,.*$", restyle, text, flags=re.M)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")


def blend_in(cur: np.ndarray, tail: np.ndarray, transition: str) -> np.ndarray:
    """Blend the first frames of `cur` over `tail` (the previous shot's continuation) for a transition."""
    out = cur.copy()
    k = len(tail)
    for j in range(k):
        w = (j + 1) / (k + 1)
        mix = tail[j] * (1 - w) + cur[j] * w
        if transition == "light swell":
            mix = mix + (255 - mix) * 0.35 * np.sin(np.pi * w)
        out[j] = mix
    return out


def assemble(p: Project, out: Path | None = None) -> Path:
    W, H = p.cfg["output_size"]
    k = p.cfg["transition_frames"]
    missing = [s["id"] for s in p.shots() if not p.state.shot(s["id"])["clip"]]
    if missing:
        raise SystemExit(f"assemble: no clip yet for {', '.join(missing)}; run `videogen clips` first")
    out = Path(out or p.work / f"{p.cfg.get('name', 'mv')}.mp4").resolve()
    p.work.mkdir(parents=True, exist_ok=True)
    ass = p.work / "lyrics.ass"
    vf = []
    if p.cfg.get("lyrics_ass"):
        lyrics_ass(p.path("lyrics_ass"), ass, (W, H), p.cfg["lyrics_style"])
        # ffmpeg runs inside the work dir and gets a bare file name: a drive letter ("C:") would otherwise be
        # read as a filter-option separator, and filter quoting differs per platform.
        vf = ["-vf", f"ass={ass.name}"]
    audio = p.path("audio" if p.cfg.get("audio") else "source_video").resolve()
    ff = subprocess.Popen([media.ffmpeg_exe(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(p.fps), "-i", "-", "-i", str(audio), "-map", "0:v",
                           "-map", "1:a", *vf, "-c:v", "libx264", "-crf", "17", "-preset", "slow",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)],
                          stdin=subprocess.PIPE, cwd=p.work)
    shots = p.shots()
    prev, prev_n = None, 0
    for i, s in enumerate(shots):
        n = sbmod.frame_span(s, p.fps)
        raw = media.read_video(p.work / p.state.shot(s["id"])["clip"], (W, H))
        cur = media.fit(raw, n)
        tr = s["transition_in"]
        if tr == "fade from black":
            m = min(2 * k, n); cur[:m] *= np.linspace(0, 1, m)[:, None, None, None]
        elif tr == "white flash" and i:
            for j in range(6):
                cur[j] = cur[j] * (j / 6) + 255 * (1 - j / 6)
        elif tr in ("dissolve", "light swell") and i:
            # the previous shot's spare frames when it has them, otherwise its held last frame
            idx = np.minimum(np.arange(prev_n, prev_n + k), len(prev) - 1)
            cur = blend_in(cur, prev[idx].astype(np.float32), tr)
        if i == len(shots) - 1:
            m = 2 * k; cur[-m:] *= np.linspace(1, 0, m)[:, None, None, None]
        ff.stdin.write(np.clip(cur, 0, 255).astype(np.uint8).tobytes())
        prev, prev_n = raw, min(n, len(raw))
        log(s["id"], tr, f"{len(raw)} -> {n} frames")
    ff.stdin.close()
    if ff.wait():
        raise SystemExit("assemble: ffmpeg failed")
    log("wrote", out)
    return out
