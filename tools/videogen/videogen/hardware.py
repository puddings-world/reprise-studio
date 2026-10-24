"""Pick a device and a memory strategy from what the machine actually has, instead of assuming one GPU.

The planner is pure (numbers in, decision out) so it is unit-tested; `detect()` is the thin probe.
Sizes are bf16 weights in GB, measured from the published checkpoints.
"""
from __future__ import annotations

from dataclasses import dataclass

# Largest single component that must sit on the device at once, and the whole pipeline.
MODEL_GB = {
    "image": {"largest": 17.0, "total": 32.0},    # Qwen-Image-2.1: Qwen3-VL encoder 17, transformer 14
    "edit": {"largest": 41.0, "total": 58.0},     # Qwen-Image-Edit-2509: 20B transformer
    "animate": {"largest": 31.0, "total": 44.0},  # Wan-Animate-2 14B + UMT5 + CLIP + VAE
    "i2v": {"largest": 11.0, "total": 22.0},      # Wan2.2-TI2V-5B + UMT5
}
HEADROOM_GB = 8.0  # activations, VAE decode, allocator slack


@dataclass(frozen=True)
class Device:
    kind: str          # cuda | mps | cpu
    free_gb: float
    total_gb: float
    name: str = ""


@dataclass(frozen=True)
class Plan:
    placement: str      # gpu | model_offload | group_offload
    kv_on_cpu: bool = False
    reason: str = ""


def plan(model: str, device: Device, kv_gb: float = 0.0) -> Plan:
    """Memory strategy for a model on a device.

    gpu            everything resident (fastest)
    model_offload  whole components swap in and out (needs the largest one + headroom)
    group_offload  transformer blocks stream from CPU (slowest, fits ~10 GB)
    """
    if device.kind == "cpu":
        return Plan("gpu", reason="CPU only: runs, but expect hours per shot")
    size = MODEL_GB[model]
    free = device.free_gb - HEADROOM_GB
    kv_on_cpu = kv_gb > 0 and kv_gb > free - size["largest"]
    if size["total"] <= free:
        # Resident weights matter most; a K/V cache that does not also fit streams from pinned CPU memory.
        spill = size["total"] + kv_gb > free
        return Plan("gpu", spill, f"{size['total']:.0f} GB fits in {device.free_gb:.0f} GB free"
                    + ("; K/V cache on CPU" if spill else ""))
    if size["largest"] <= free:
        return Plan("model_offload", kv_on_cpu, f"largest part {size['largest']:.0f} GB fits; swap the rest")
    return Plan("group_offload", kv_gb > 0, f"only {device.free_gb:.0f} GB free; stream transformer blocks")


def animate_kv_gb(width: int, height: int, frames: int = 81, layers: int = 40, dim: int = 5120) -> float:
    """Reference K/V cache Wan-Animate-2 keeps for one segment (bf16 K and V for every layer)."""
    latent_frames = (frames - 1) // 4 + 1
    tokens = latent_frames * (height // 16) * (width // 16)
    return tokens * dim * 2 * 2 * layers / 1e9


def detect() -> Device:
    try:
        import torch
    except ImportError:
        return Device("cpu", 0, 0, "torch not installed")
    if torch.cuda.is_available():
        free, total = torch.cuda.mem_get_info()
        return Device("cuda", free / 1e9, total / 1e9, torch.cuda.get_device_name())
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        # Unified memory: report system RAM as the budget; MPS has no free-memory query.
        import psutil  # type: ignore[import-not-found]
        mem = psutil.virtual_memory()
        return Device("mps", mem.available / 1e9, mem.total / 1e9, "Apple GPU")
    return Device("cpu", 0, 0, "no GPU")
