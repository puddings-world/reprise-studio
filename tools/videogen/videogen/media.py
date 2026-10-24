"""Video I/O through an ffmpeg binary, plus the pure frame math the stages share."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np


def ffmpeg_exe() -> str:
    """VIDEOGEN_FFMPEG > ffmpeg on PATH > the binary bundled with imageio-ffmpeg."""
    if os.environ.get("VIDEOGEN_FFMPEG"):
        return os.environ["VIDEOGEN_FFMPEG"]
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as e:
        raise SystemExit("ffmpeg not found: install it, `pip install imageio-ffmpeg`, or set VIDEOGEN_FFMPEG") from e


def parse_video_size(banner: str) -> tuple[int, int] | None:
    """(width, height) from ffmpeg's stream banner. Matches 'WxH' only where it is a frame size, so codec
    tags such as '0x31637661' are not mistaken for one."""
    for line in banner.splitlines():
        if "Video:" in line:
            m = re.search(r"(?<![0-9a-fA-Fx])([1-9]\d{1,4})x([1-9]\d{1,4})(?![0-9a-fA-F])", line)
            if m:
                return int(m.group(1)), int(m.group(2))
    return None


def probe_size(path: Path) -> tuple[int, int]:
    """(width, height) of a video's first stream, read from ffmpeg's banner (no ffprobe needed)."""
    err = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stderr
    size = parse_video_size(err)
    if not size:
        raise SystemExit(f"could not read the video size of {path}")
    return size


def crop_box(crop: list[float], src_w: int, src_h: int) -> tuple[int, int, int, int]:
    """Fractional (x0, y0, x1, y1) -> even (w, h, x, y) pixels for ffmpeg's crop filter."""
    x0, y0, x1, y1 = crop
    w, h = int((x1 - x0) * src_w) // 2 * 2, int((y1 - y0) * src_h) // 2 * 2
    return w, h, int(x0 * src_w), int(y0 * src_h)


def read_clip(src: Path, start: float, end: float, fps: int, crop: list[float] | None = None,
              size: tuple[int, int] | None = None) -> np.ndarray:
    """Frames [start, end) at `fps` as uint8 [T, H, W, 3], optionally cropped then resized."""
    filters = [f"fps={fps}"]
    out_w = out_h = None
    if crop:
        sw, sh = probe_size(src)
        w, h, x, y = crop_box(crop, sw, sh)
        filters.append(f"crop={w}:{h}:{x}:{y}")
        out_w, out_h = w, h
    if size:
        filters.append(f"scale={size[0]}:{size[1]}:flags=lanczos")
        out_w, out_h = size
    if out_w is None:
        out_w, out_h = probe_size(src)
    raw = subprocess.run([ffmpeg_exe(), "-v", "error", "-ss", f"{start}", "-t", f"{end - start}", "-i", str(src),
                          "-vf", ",".join(filters), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, out_h, out_w, 3)


def read_video(path: Path, size: tuple[int, int]) -> np.ndarray:
    raw = subprocess.run([ffmpeg_exe(), "-v", "error", "-i", str(path), "-vf",
                          f"scale={size[0]}:{size[1]}:flags=lanczos", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, size[1], size[0], 3)


def even(frames: np.ndarray) -> np.ndarray:
    """Trim an odd last row/column; yuv420p needs even dimensions."""
    return frames[:, : frames.shape[1] // 2 * 2, : frames.shape[2] // 2 * 2]


def write_video(frames: np.ndarray, path: Path, fps: int, crf: int = 16) -> None:
    frames = even(frames)
    _, h, w, _ = frames.shape
    path.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen([ffmpeg_exe(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
                          "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p",
                          str(path)], stdin=subprocess.PIPE)
    p.stdin.write(np.ascontiguousarray(frames).tobytes())
    p.stdin.close()
    if p.wait():
        raise RuntimeError(f"ffmpeg failed writing {path}")


def to_uint8(video) -> np.ndarray:
    """Normalise pipeline output (list / tensor / array, [B]?[T,H,W,C] or channels-first, 0-1 or 0-255)."""
    v = video[0] if isinstance(video, (list, tuple)) else video
    if hasattr(v, "detach"):
        v = v.detach().float().cpu().numpy()
    v = np.asarray(v)
    if v.ndim == 5:
        v = v[0]
    if v.shape[-1] != 3:
        v = np.moveaxis(v, 0 if v.shape[0] == 3 else 1, -1)
    if v.dtype != np.uint8:
        v = np.clip(v * 255 if v.max() <= 1.0 + 1e-3 else v, 0, 255).round().astype(np.uint8)
    return v


def fit(clip: np.ndarray, n: int) -> np.ndarray:
    """Exactly n frames as float32: the first n, or a smooth slow-down when the clip is shorter."""
    if len(clip) >= n:
        return clip[:n].astype(np.float32)
    pos = np.linspace(0, len(clip) - 1, n)
    lo = np.floor(pos).astype(int)
    w = (pos - lo)[:, None, None, None]
    hi = np.minimum(lo + 1, len(clip) - 1)
    return clip[lo].astype(np.float32) * (1 - w) + clip[hi].astype(np.float32) * w


def contact_strip(frames: np.ndarray, count: int = 5, width: int = 240) -> np.ndarray:
    """`count` evenly spaced frames side by side, each `width` wide (for clip review pages)."""
    from PIL import Image
    idx = np.linspace(0, len(frames) - 1, count).round().astype(int)
    h = round(frames.shape[1] * width / frames.shape[2])
    tiles = [np.asarray(Image.fromarray(frames[i]).resize((width, h), Image.LANCZOS)) for i in idx]
    return np.concatenate(tiles, axis=1)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
