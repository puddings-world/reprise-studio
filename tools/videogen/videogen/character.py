"""Character design: candidate portraits per outfit, reviewed like keyframes, the pick becomes the project's
character reference (project.json `character`, usually assets/character.png).

prompts.json `character`:
    sheet    template; may use {outfit} and every var
    outfits  {key: outfit description}
project.json `character_design` (optional): size, seeds, refs (photos to base the design on).
With refs the editor model redraws them; without, the image model designs from text alone.
Candidates live in work/character/char_<outfit>_s<seed>.png under the pseudo shot id `character` in state.json.
"""
from __future__ import annotations

import shutil
import string
import time
from pathlib import Path

from .draft import todos

CHAR = "character"
DEFAULT_DESIGN = {"size": [1024, 1024], "seeds": [1, 2, 3], "refs": []}


def settings(cfg: dict) -> dict:
    return {**DEFAULT_DESIGN, **cfg.get("character_design", {})}


def ref_path(cfg: dict, ref: str) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else Path(cfg["project_dir"]) / path


def prompts_for(p, outfits: list[str] | None = None, note: str = "") -> dict[str, str]:
    """{outfit key: full prompt}; refuses while the character prompts still say TODO."""
    block = p.prompts.d.get("character")
    if not block or not block.get("outfits"):
        raise SystemExit("prompts.json has no `character` block with `sheet` and `outfits`")
    used = {name for _, name, _, _ in string.Formatter().parse(block["sheet"]) if name}
    variables = {k: v for k, v in p.prompts.d.get("vars", {}).items() if k in used}
    left = todos({"character": block, "vars": variables, "style": p.prompts.d.get("style", "")}, "prompts")
    if left:
        raise SystemExit("fill in prompts.json first: " + ", ".join(left))
    unknown = sorted(set(outfits or []) - set(block["outfits"]))
    if unknown:
        raise SystemExit(f"unknown outfit {', '.join(unknown)}; defined: {', '.join(block['outfits'])}")
    out = {}
    for key, outfit in block["outfits"].items():
        if outfits and key not in outfits:
            continue
        text = p.prompts._fill(block["sheet"], outfit=outfit) + " " + p.prompts.d["style"]
        out[key] = text + (f" Revision request: {note}" if note else "")
    return out


def generate(p, outfits: list[str] | None = None, seeds: list[int] | None = None) -> list[str]:
    """GPU stage: portraits for every outfit x seed not generated yet (fresh seeds after a redo note)."""
    from PIL import Image
    from .models import ImageModel, free_memory
    from .stages import _device, log

    c = settings(p.cfg)
    note = p.state.shot(CHAR)["redo"] and p.state.shot(CHAR)["redo"]["note"]
    texts = prompts_for(p, outfits, note or "")
    if note:
        seeds = seeds or p.state.next_seeds(CHAR, len(c["seeds"]), c["seeds"])
    seeds = seeds or c["seeds"]
    refs = [Image.open(ref_path(p.cfg, r)).convert("RGB") for r in c["refs"]]
    role = "edit" if refs else "image"
    model = ImageModel(p.cfg["models"][role], role, _device())
    log(f"character: {len(texts)} outfits x {len(seeds)} seeds, {role} model, plan {model.plan.placement}")
    (p.work / "character").mkdir(parents=True, exist_ok=True)
    made = []
    for key, text in texts.items():
        for seed in seeds:
            name = f"character/char_{key}_s{seed}.png"
            if not (p.work / name).exists():
                t = time.time()
                model.generate(text, refs or None, c["size"][0], c["size"][1], p.cfg["steps"][role], seed,
                               negative=p.prompts.negative("image")).save(p.work / name)
                log(key, f"seed {seed}", f"{time.time() - t:.0f}s")
            p.state.add_candidate(CHAR, name)
            made.append(name)
    p.state.take_redo(CHAR, CHAR)
    p.state.save()
    del model; free_memory()
    return made


def install(p) -> Path:
    """Copy the picked portrait to the project's character path."""
    pick = p.state.shot(CHAR)["pick"]
    if not pick:
        raise SystemExit("no character picked yet")
    dst = p.path("character")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(p.work / pick, dst)
    return dst
