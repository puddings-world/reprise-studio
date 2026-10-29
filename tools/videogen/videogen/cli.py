"""`python -m videogen` — the semi-automatic cover-MV loop.

    videogen init --title T --video V       start a project (or --audio A without a performance video)
    videogen character                      protagonist portrait candidates (review, pick -> assets/character.png)
    videogen storyboard --lyrics F.lrc      draft storyboard.json + prompt stubs from timed lyrics
    videogen doctor                         check project files, tools, unwritten TODOs and the GPU plan
    videogen keyframes [--only S01 S05]     still candidates for pending shots
    videogen review keyframes               build the review page (work/review/keyframes.html)
    videogen feedback < pasted.txt          apply picks / redo notes from a review page
    videogen edit                           optional expression pass on picked images
    videogen clips [--kinds perform]        animate approved images
    videogen assemble                       final MV with lyrics and the original audio
    videogen cover / cover-title            cover art candidates, then the typeset title on each
    videogen status                         where every shot stands
    videogen --host NAME attach             re-attach to a running host job and sync it

Global: --project DIR (default: current dir), --host NAME (default: VIDEOGEN_HOST or local).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import config

GPU_STAGES = ("character", "keyframes", "edit", "clips", "cover")
DOCTOR_LIST = 15  # problems printed before the rest is summarised


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="videogen", description="Semi-automatic cover-song anime MV pipeline.")
    ap.add_argument("--project", type=Path, default=Path("."), help="project directory (holds project.json)")
    ap.add_argument("--host", default=os.environ.get("VIDEOGEN_HOST", "local"),
                    help="execution host from project.json `hosts` (default: local)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init", help="create project.json, prompts.json and assets/ in --project")
    i.add_argument("--title", required=True); i.add_argument("--name")
    i.add_argument("--video", type=Path, help="performance recording (gives perform shots and the audio)")
    i.add_argument("--audio", type=Path, help="song audio (alone, or to replace the video's sound)")
    ch = sub.add_parser("character", help="protagonist portrait candidates (prompts.json `character`)")
    ch.add_argument("--outfits", nargs="+"); ch.add_argument("--seeds", type=int, nargs="+")
    sb = sub.add_parser("storyboard", help="draft storyboard.json and prompt stubs from timed lyrics")
    sb.add_argument("--lyrics", type=Path, help=".lrc, .ass or .srt (default: project.json lyrics_ass)")
    sb.add_argument("--offset", type=float, default=0.0, help="seconds added to every lyric time")
    sb.add_argument("--duration", type=float, help="song length in seconds (default: measured from the audio)")
    sb.add_argument("--force", action="store_true", help="replace an existing storyboard.json")
    sub.add_parser("doctor", help="check files, tools, GPU and the memory plan")
    sub.add_parser("show-config", help="print the effective config")
    sub.add_parser("status", help="per-shot progress table")
    sub.add_parser("attach", help="re-attach to the last job sent to --host and sync its results")
    k = sub.add_parser("keyframes", help="generate still candidates for pending shots")
    k.add_argument("--only", nargs="+"); k.add_argument("--seeds", type=int, nargs="+")
    e = sub.add_parser("edit", help="apply prompts.expression_edit to picked face shots")
    e.add_argument("--only", nargs="+")
    c = sub.add_parser("clips", help="animate approved images")
    c.add_argument("--only", nargs="+"); c.add_argument("--kinds", nargs="+", choices=["perform", "story", "image"])
    cv = sub.add_parser("cover", help="cover art candidates (prompts.json `cover`)")
    cv.add_argument("--seeds", type=int, nargs="+")
    sub.add_parser("cover-title", help="typeset the title on every cover art candidate (CPU)")
    a = sub.add_parser("assemble", help="cut the final MV")
    a.add_argument("--out", type=Path)
    r = sub.add_parser("review", help="build a review page for a stage")
    r.add_argument("stage", choices=["character", "storyboard", "keyframes", "edit", "clips"])
    r.add_argument("--only", nargs="+")
    f = sub.add_parser("feedback", help="apply feedback text (stdin or --file)")
    f.add_argument("--file", type=Path)
    w = sub.add_parser("_host-wrap", help=argparse.SUPPRESS)
    w.add_argument("--state-in", type=Path, required=True); w.add_argument("--export", type=Path, required=True)
    w.add_argument("rest", nargs=argparse.REMAINDER)
    return ap


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to a legacy code page
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = _parser().parse_args(argv)
    if args.cmd == "init":
        from .scaffold import init
        for path in init(args.project, args.title, args.name, args.video, args.audio):
            print("wrote", path)
        print("next: describe the protagonist in prompts.json (vars.HE_DESIGN, character.outfits), "
              "then `videogen character`")
        return
    cfg = config.load(args.project, args.host)
    host = cfg["hosts"][args.host]

    if args.cmd == "_host-wrap":
        from .remote import host_wrap
        rest = args.rest[1:] if args.rest[:1] == ["--"] else args.rest
        host_wrap(cfg, ["--project", str(args.project), "--host", args.host, *rest], args.state_in, args.export)
        return
    if args.cmd in GPU_STAGES and host["kind"] != "local" and not os.environ.get("VIDEOGEN_ON_HOST"):
        from .remote import run
        os.environ["VIDEOGEN_ON_HOST"] = "1"
        stage_argv = argv[argv.index(args.cmd):]
        return run(config.load(args.project, "local"), args.host, stage_argv)

    if args.cmd == "attach":
        from .remote import attach
        return attach(config.load(args.project, "local"), args.host)
    if args.cmd == "show-config":
        print(json.dumps(cfg, ensure_ascii=False, indent=1)); return
    if args.cmd == "doctor":
        return _doctor(cfg)
    if args.cmd == "storyboard":
        from .scaffold import storyboard, summary
        sb = storyboard(cfg, args.lyrics, args.offset, args.duration, args.force)
        print(summary(sb))
        print(f"{len(sb['shots'])} shots drafted (P perform, S story, I image). Next: write every TODO in "
              "storyboard.json and prompts.json, then `videogen review storyboard`")
        return

    from .stages import Project
    p = Project(cfg)
    if args.cmd == "status":
        return _status(p)
    if args.cmd == "character":
        from .character import generate
        generate(p, args.outfits, args.seeds)
    elif args.cmd == "keyframes":
        from .stages import keyframes
        keyframes(p, args.only, args.seeds)
    elif args.cmd == "edit":
        from .stages import edit
        edit(p, args.only)
    elif args.cmd == "clips":
        from .stages import clips
        clips(p, args.only, args.kinds)
    elif args.cmd == "cover":
        from .cover import art
        art(p, args.seeds)
    elif args.cmd == "cover-title":
        from .cover import titles
        titles(p)
    elif args.cmd == "assemble":
        from .stages import assemble
        assemble(p, args.out)
    elif args.cmd == "review":
        from .review import build
        print(build(p, args.stage, args.only))
    elif args.cmd == "feedback":
        from .feedback import apply, parse
        text = args.file.read_text(encoding="utf-8") if args.file else sys.stdin.read()
        fb = parse(text)
        for line in apply(fb, p.state):
            print(line)
        p.state.save()
        if fb.stage == "character" and fb.picks and not fb.redo:
            from .character import install
            print("character reference ->", install(p))
            if any(p.state.shot(s["id"])["candidates"] for s in p.shots()):
                print("note: existing keyframes used the previous character; redo the ones that show it")


def _doctor(cfg: dict) -> None:
    import shutil
    from . import hardware, media
    from .stages import Project
    ok = True
    try:
        problems = Project(cfg).problems()
    except SystemExit as e:
        problems = [str(e)]
    for msg in problems[:DOCTOR_LIST]:
        print("  ✗", msg); ok = False
    if len(problems) > DOCTOR_LIST:
        print(f"  … {len(problems) - DOCTOR_LIST} more")
    print("  ✓ project files" if not problems else "")
    try:
        print("  ✓ ffmpeg:", media.ffmpeg_exe())
    except SystemExit as e:
        print("  ✗", e); ok = False
    for mod in ("numpy", "PIL", "torch", "diffusers", "transformers", "huggingface_hub"):
        try:
            __import__(mod); print("  ✓", mod)
        except ImportError:
            print("  ✗", mod, "(GPU stages need `pip install -e tools/videogen[gpu]`)")
    dev = hardware.detect()
    print(f"  device: {dev.kind} {dev.name} free {dev.free_gb:.1f} / {dev.total_gb:.1f} GB")
    if dev.kind != "cpu":
        aw, ah = cfg["animate_size"]
        for role in ("image", "edit", "i2v"):
            print(f"    {role:8s}", hardware.plan(role, dev).placement)
        pl = hardware.plan("animate", dev, hardware.animate_kv_gb(aw, ah))
        print(f"    animate  {pl.placement}, reference K/V on {'CPU' if pl.kv_on_cpu else 'GPU'}")
    print("  hosts:", ", ".join(f"{n} ({h['kind']})" for n, h in cfg["hosts"].items()))
    print("  hf cache:", os.environ.get("HF_HOME", "~/.cache/huggingface (default)"))
    if not shutil.which("ffmpeg"):
        print("  note: final assembly burns lyrics with libass; use an ffmpeg build that has it")
    sys.exit(0 if ok else 1)


def _status(p) -> None:
    print(f"{'shot':5} {'kind':8} {'cand':>4}  {'pick':16} {'edit':5} {'clip':16} pending")
    for s in p.shots():
        st = p.state.shot(s["id"])
        pend = st["redo"]["stage"] + (": " + st["redo"]["note"] if st["redo"]["note"] else "") if st["redo"] else ""
        print(f"{s['id']:5} {s['kind']:8} {len(st['candidates']):>4}  {(st['pick'] or '-').split('/')[-1]:16} "
              f"{('yes' if st['edit'] and st['use_edit'] else '-'):5} {(st['clip'] or '-').split('/')[-1]:16} {pend}")


if __name__ == "__main__":
    main()
