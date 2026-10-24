"""Run a GPU stage on another machine and sync the results back into the local work dir.

The local work dir is the source of truth. A remote run uploads `state.json`, runs the same `videogen`
command on the host (which keeps its own persistent workdir so earlier images are already there), then
returns every file that changed plus the updated state.

Backends implement `submit(bundle_dir, command) -> results_dir`. Only `rcs` (remote-console jobs) exists
today; an ssh/slurm backend is another class with the same method.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_FILES = ("project.json", "storyboard.json", "prompts.json")
OK_MARKER, FAIL_MARKER = "_videogen_ok", "_videogen_failed"


# ------------------------------------------------------------------ host side (runs on the GPU machine)
def host_wrap(cfg: dict, argv: list[str], state_in: Path, export_dir: Path) -> None:
    """Install the uploaded state, run one stage in-process, export changed files + state."""
    work = Path(cfg["workdir"])
    work.mkdir(parents=True, exist_ok=True)
    if state_in.exists():
        shutil.copy(state_in, work / "state.json")
    marker = time.time()
    os.environ["VIDEOGEN_ON_HOST"] = "1"  # we are the host: run the stage here, do not forward it again
    from . import cli
    export_dir.mkdir(parents=True, exist_ok=True)
    try:
        cli.main(argv)
        ok = True
    except BaseException:
        ok = False
        raise
    finally:  # export partial results either way; the marker tells the client whether the stage finished
        _export(work, export_dir, marker, ok)


def _export(work: Path, export_dir: Path, marker: float, ok: bool) -> None:
    for f in work.rglob("*"):
        if f.is_file() and (f.stat().st_mtime >= marker or f.name == "state.json"):
            dst = export_dir / f.relative_to(work)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, dst)
    (export_dir / (OK_MARKER if ok else FAIL_MARKER)).write_text(time.strftime("%Y-%m-%d %H:%M:%S"))


# ------------------------------------------------------------------ client side
def bundle(cfg: dict, host: dict, argv: list[str], dest: Path) -> list[str]:
    """Stage everything the host needs into `dest`; returns the job's file list (relative)."""
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(PACKAGE_DIR, dest / "videogen", ignore=shutil.ignore_patterns("__pycache__"))
    proj = Path(cfg["project_dir"])
    (dest / "project").mkdir(parents=True)
    for name in PROJECT_FILES:
        shutil.copy(proj / name, dest / "project" / name)
    # Upload path assets unless the host profile already points at its own copy.
    for key in ("character", "lyrics_ass", "source_video", "audio"):
        if key in cfg and key not in host.get("paths", {}) and not Path(cfg[key]).is_absolute():
            src = proj / cfg[key]
            if src.exists() and src.stat().st_size < host.get("upload_limit_mb", 50) * 1e6:
                (dest / "project" / cfg[key]).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, dest / "project" / cfg[key])
    state = Path(cfg["workdir"]) / "state.json"
    if state.exists():
        shutil.copy(state, dest / "state.json")
    return [str(p.relative_to(dest)).replace("\\", "/") for p in dest.rglob("*") if p.is_file()]


def sync_back(results: Path, workdir: Path) -> int:
    """Copy a host's exported work files home. Raises when the host stage did not finish."""
    if not (results / OK_MARKER).exists():
        partial = sum(1 for f in results.rglob("*") if f.is_file()) if results.exists() else 0
        reason = "failed" if (results / FAIL_MARKER).exists() else "returned no result"
        if partial:
            _copy_tree(results, workdir)
        raise SystemExit(f"remote stage {reason}; kept {partial} partial files. See the job log above.")
    return _copy_tree(results, workdir)


def _copy_tree(results: Path, workdir: Path) -> int:
    n = 0
    for f in results.rglob("*"):
        if f.is_file() and f.name not in (OK_MARKER, FAIL_MARKER):
            dst = workdir / f.relative_to(results)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, dst)
            n += 1
    return n


class RcsBackend:
    """remote-console (`rcs job run/logs/fetch`)."""

    def __init__(self, host: dict):
        self.host = host
        self.exe = host.get("rcs") or os.environ.get("RCS_EXE") or shutil.which("rcs") or str(
            Path(os.environ.get("LOCALAPPDATA", "")) / "remote-console" / "bin" / "rcs.exe")

    def _rcs(self, args: list[str], cwd: Path, **kw):
        env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
        return subprocess.run([self.exe, *args], cwd=cwd, env=env, text=True, encoding="utf-8",
                              errors="replace", **kw)

    def follow(self, dest: Path) -> Path:
        """Stream the most recent job's log until it ends, fetch it, return its exported directory."""
        self._rcs(["job", "logs", "--follow"], dest)
        self._rcs(["job", "fetch"], dest, capture_output=True)
        results = sorted((dest / ".rcs" / "results").glob("*"), key=lambda p: p.stat().st_mtime)
        if not results:
            raise SystemExit("rcs fetch returned no results")
        return results[-1] / "outputs" / "outputs"

    def submit(self, dest: Path, files: list[str], name: str, command: str) -> Path:
        job = {
            "version": 1, "name": name, "include": files, "setup": self.host.get("setup", []),
            "command": command, "outputs": ["outputs"], "env": self.host.get("env", {}),
            "require_gpu": self.host.get("require_gpu", True),
            "remote_root": self.host.get("remote_root", "/tmp/rcs-jobs"), "remote_python": "python3",
        }
        (dest / "rcs-job.json").write_text(json.dumps(job, indent=1), encoding="utf-8")
        run = self._rcs(["job", "run"], dest, capture_output=True)
        print(run.stdout.strip(), run.stderr.strip(), flush=True)
        if run.returncode:
            raise SystemExit("rcs job run failed")
        return self.follow(dest)


BACKENDS = {"rcs": RcsBackend}


def run(cfg: dict, host_name: str, argv: list[str]) -> None:
    host = cfg["hosts"][host_name]
    backend = BACKENDS.get(host["kind"])
    if not backend:
        raise SystemExit(f"host '{host_name}': unknown kind '{host['kind']}' (known: local, {', '.join(BACKENDS)})")
    dest = Path(cfg["project_dir"]) / ".videogen-jobs" / host_name
    files = bundle(cfg, host, argv, dest)
    python = host.get("python", "python3")
    quoted = " ".join(_q(a) for a in argv)
    command = (f"{python} -u -m videogen --project project --host {host_name} "
               f"_host-wrap --state-in state.json --export \"$RCS_OUTPUT_DIR/work\" -- {quoted}")
    stamp = time.strftime("%m%d-%H%M%S")
    results = backend(host).submit(dest, files, f"videogen-{argv[0]}-{stamp}", command)
    n = sync_back(results / "work", Path(cfg["workdir"]))
    print(f"synced {n} files into {cfg['workdir']}", flush=True)


def attach(cfg: dict, host_name: str) -> None:
    """Re-attach to the last job sent to a host (after a closed terminal or a dropped connection) and sync it."""
    host = cfg["hosts"][host_name]
    backend = BACKENDS.get(host["kind"])
    dest = Path(cfg["project_dir"]) / ".videogen-jobs" / host_name
    if not backend or not dest.exists():
        raise SystemExit(f"no job has been sent to host '{host_name}' from this project")
    n = sync_back(backend(host).follow(dest) / "work", Path(cfg["workdir"]))
    print(f"synced {n} files into {cfg['workdir']}", flush=True)


def _q(a: str) -> str:
    return a if all(c.isalnum() or c in "-_=./," for c in a) else "'" + a.replace("'", "'\\''") + "'"


if __name__ == "__main__":
    sys.exit("use `python -m videogen`")
