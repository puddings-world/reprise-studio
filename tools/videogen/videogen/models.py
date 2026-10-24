"""Model loaders behind four small interfaces, placed on whatever device `hardware.plan` allows.

Swapping a model means changing `models.<role>` in project.json; a different architecture means adding a
class here with the same `generate` signature.
"""
from __future__ import annotations

import gc

from . import hardware
from .hardware import Device, Plan


def _torch():
    import torch
    return torch


def free_memory() -> None:
    gc.collect()
    torch = _torch()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def local_path(repo: str) -> str:
    """Local snapshot of a model repo; downloads on first use (honours HF_HOME / HF_HUB_OFFLINE)."""
    from huggingface_hub import snapshot_download
    return snapshot_download(repo)


def _place(pipe, plan: Plan, device: Device, big: tuple[str, ...] = ("transformer",),
           encoders: tuple[str, ...] = ("text_encoder",)) -> None:
    torch = _torch()
    dev = torch.device(device.kind if device.kind != "cpu" else "cpu")
    if device.kind == "cpu" or plan.placement == "gpu":
        pipe.to(dev)
        return
    if plan.placement == "model_offload" and hasattr(pipe, "enable_model_cpu_offload"):
        pipe.enable_model_cpu_offload(device=dev)
        return
    _group_offload(pipe, dev, big, encoders, blocks=1 if plan.placement == "group_offload" else 8)


def _group_offload(pipe, dev, big, encoders, blocks: int) -> None:
    torch = _torch()
    from diffusers.hooks import apply_group_offloading
    stream = dev.type == "cuda" and blocks == 1  # diffusers only overlaps transfers for single-block groups
    for name in big:
        getattr(pipe, name).enable_group_offload(onload_device=dev, offload_device=torch.device("cpu"),
                                                 offload_type="block_level", num_blocks_per_group=blocks,
                                                 use_stream=stream)
    for name in encoders:
        if getattr(pipe, name, None) is not None:
            apply_group_offloading(getattr(pipe, name), onload_device=dev, offload_type="leaf_level",
                                   use_stream=stream)
    for name in ("vae", "image_encoder"):
        if getattr(pipe, name, None) is not None:
            getattr(pipe, name).to(dev)


class ImageModel:
    """Qwen-Image-2.1 (generation with up to ~10 reference images) or Qwen-Image-Edit-2509 (editing)."""

    def __init__(self, repo: str, role: str, device: Device):
        torch = _torch()
        self.role, self.torch = role, torch
        if role == "edit":
            from diffusers import QwenImageEditPlusPipeline as P
        else:
            from diffusers import QwenImage21Pipeline as P
        self.pipe = P.from_pretrained(local_path(repo), torch_dtype=torch.bfloat16)
        self.plan = hardware.plan(role, device)
        _place(self.pipe, self.plan, device)

    def generate(self, prompt: str, images, width: int, height: int, steps: int, seed: int, negative: str = ""):
        kw = dict(prompt=prompt, image=images, width=width, height=height, num_inference_steps=steps,
                  generator=self.torch.Generator("cpu").manual_seed(seed))
        if self.role == "edit":  # Edit-2509 needs true CFG; Qwen-Image-2.1 is sampled without guidance
            kw.update(negative_prompt=negative or " ", true_cfg_scale=4.0, guidance_scale=1.0)
        return self.pipe(**kw).images[0]


class AnimateModel:
    """Wan-Animate-2 (distilled): the driving video gives the motion, the reference image the look."""

    def __init__(self, repo: str, device: Device, width: int, height: int):
        torch = _torch()
        self.torch = torch
        self.plan = hardware.plan("animate", device, kv_gb=hardware.animate_kv_gb(width, height))
        _patch_animate(kv_on_cpu=self.plan.kv_on_cpu)
        from diffusers import ModularPipeline
        path = local_path(repo)
        pipe = ModularPipeline.from_pretrained(path)
        # The published index pins the transformer to a PR revision; load everything from the snapshot instead.
        pipe.load_components(pretrained_model_name_or_path=path, revision=None,
                             torch_dtype={"vae": torch.float32, "default": torch.bfloat16})
        dev = torch.device(device.kind)
        if self.plan.placement == "gpu" or device.kind == "cpu":
            for name in ("transformer", "text_encoder", "image_encoder", "vae"):
                getattr(pipe, name).to(dev)
        else:  # modular pipelines have no model offload; use coarse or fine block streaming
            _group_offload(pipe, dev, ("transformer",), ("text_encoder",),
                           blocks=8 if self.plan.placement == "model_offload" else 1)
        self.pipe = pipe

    def generate(self, reference, driving, prompt: str, negative: str, width: int, height: int, steps: int,
                 seed: int, fps: int):
        return self.pipe(prompt=prompt, negative_prompt=negative, image=reference, driving_video=driving, fps=fps,
                         width=width, height=height, num_inference_steps=steps,
                         generator=self.torch.Generator("cpu").manual_seed(seed), output="videos")


def _patch_animate(kv_on_cpu: bool) -> None:
    """Two runtime fixes for Wan-Animate-2 in diffusers 0.41.

    1. Its generation pass attends through a flex-attention BlockMask; run uncompiled, PyTorch falls back to
       dense math attention (hundreds of GB). Compile only the flex kernel so it coexists with offload hooks.
    2. Optionally keep the per-layer reference K/V cache in pinned CPU memory (tens of GB at 720p-ish).
    """
    torch = _torch()
    import torch.nn.attention.flex_attention as fa
    if not getattr(fa, "_videogen_compiled", False):
        fa.flex_attention = torch.compile(fa.flex_attention, dynamic=False)
        fa._videogen_compiled = True
    if kv_on_cpu:
        from diffusers.models.transformers import transformer_wan_animate_2 as wa2

        def store(self, key, value):
            self.key = key.to("cpu", non_blocking=True).pin_memory()
            self.value = value.to("cpu", non_blocking=True).pin_memory()

        def get(self):
            dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            return self.key.to(dev, non_blocking=True), self.value.to(dev, non_blocking=True)

        wa2.WanAnimate2KVLayerCache.store, wa2.WanAnimate2KVLayerCache.get = store, get


class I2VModel:
    """Wan2.2-TI2V-5B image-to-video."""

    def __init__(self, repo: str, device: Device):
        torch = _torch()
        from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
        self.torch = torch
        path = local_path(repo)
        vae = AutoencoderKLWan.from_pretrained(path, subfolder="vae", torch_dtype=torch.float32)
        self.pipe = WanImageToVideoPipeline.from_pretrained(path, vae=vae, torch_dtype=torch.bfloat16)
        self.plan = hardware.plan("i2v", device)
        _place(self.pipe, self.plan, device)

    def generate(self, image, prompt: str, negative: str, width: int, height: int, frames: int, steps: int,
                 seed: int):
        return self.pipe(image=image, prompt=prompt, negative_prompt=negative, width=width, height=height,
                         num_frames=frames, num_inference_steps=steps, guidance_scale=5.0,
                         generator=self.torch.Generator("cpu").manual_seed(seed), output_type="np").frames[0]
