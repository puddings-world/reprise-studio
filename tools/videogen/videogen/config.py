"""Layered configuration: built-in defaults < project.json < environment < CLI flags.

Nothing here knows about a particular machine. Paths in a project file are relative to the project
directory; machine-specific locations (work dir, model cache, remote inputs) come from the environment
or from a runner profile.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "fps": 24,
    "output_size": [1280, 720],
    "work_size": [1280, 704],      # keyframes and I2V; multiples of 32
    "animate_size": [960, 528],    # performance shots; upscaled at assembly
    "seeds": [1, 2],
    "models": {
        "image": "Qwen/Qwen-Image-2.1",
        "edit": "Qwen/Qwen-Image-Edit-2509",
        "animate": "Wan-AI/Wan2.2-Animate-2-14B-Distilled-Diffusers",
        "i2v": "Wan-AI/Wan2.2-TI2V-5B-Diffusers",
    },
    "steps": {"image": 40, "edit": 40, "animate": 10, "i2v": 40},
    "i2v_max_frames": 145,
    "transition_frames": 12,
    "lyrics_style": {"font": "Noto Serif TC", "size": 40, "margin_v": 42},
    # Named execution hosts. "local" runs in this process; others are defined per project (see README).
    "hosts": {"local": {"kind": "local"}},
}

# Environment variables that override config keys (dotted paths).
ENV_KEYS = {
    "VIDEOGEN_WORKDIR": "workdir",
    "VIDEOGEN_ANIMATE_SIZE": "animate_size",
    "VIDEOGEN_SEEDS": "seeds",
}


def deep_merge(base: dict, over: dict) -> dict:
    """Return a new dict: `over` merged into `base`, recursing into nested dicts."""
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def set_dotted(cfg: dict, dotted: str, value: Any) -> None:
    *parents, leaf = dotted.split(".")
    node = cfg
    for p in parents:
        node = node.setdefault(p, {})
    node[leaf] = value


def parse_env_value(raw: str) -> Any:
    """'960x528' -> [960, 528]; '1,2' -> [1, 2]; JSON when it parses; otherwise the raw string."""
    if "x" in raw and all(p.isdigit() for p in raw.split("x")):
        return [int(p) for p in raw.split("x")]
    if "," in raw and all(p.strip().lstrip("-").isdigit() for p in raw.split(",")):
        return [int(p) for p in raw.split(",")]
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def env_overrides(environ: dict[str, str] | None = None) -> dict:
    environ = os.environ if environ is None else environ
    out: dict = {}
    for var, dotted in ENV_KEYS.items():
        if environ.get(var):
            set_dotted(out, dotted, parse_env_value(environ[var]))
    return out


def load(project_dir: Path, host: str = "local", cli: dict | None = None,
         environ: dict[str, str] | None = None) -> dict:
    """Effective config for a project directory as seen from `host`.

    A host profile (``hosts.<name>`` in project.json) can carry ``paths`` that replace path settings on that
    machine (e.g. a pre-uploaded source video) and a ``workdir``.
    """
    project_file = project_dir / "project.json"
    if not project_file.exists():
        raise SystemExit(f"{project_file} not found. Create one with `videogen init {project_dir}`.")
    cfg = deep_merge(DEFAULTS, json.loads(project_file.read_text(encoding="utf-8")))
    if host not in cfg["hosts"]:
        raise SystemExit(f"unknown host '{host}'; defined hosts: {', '.join(cfg['hosts'])}")
    profile = cfg["hosts"][host]
    cfg = deep_merge(cfg, profile.get("paths", {}))
    if profile.get("workdir"):
        cfg["workdir"] = profile["workdir"]
    cfg = deep_merge(cfg, env_overrides(environ))
    cfg = deep_merge(cfg, {k: v for k, v in (cli or {}).items() if v is not None})
    cfg["host"] = host
    cfg["project_dir"] = str(project_dir.resolve())
    cfg.setdefault("workdir", str(project_dir.resolve() / "work"))
    return cfg


def resolve(cfg: dict, key: str) -> Path:
    """Resolve a project-relative path setting (absolute paths are kept)."""
    p = Path(cfg[key])
    return p if p.is_absolute() else Path(cfg["project_dir"]) / p
