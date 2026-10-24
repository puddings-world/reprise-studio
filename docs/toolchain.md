# Toolchain

| Tool | Used by | Where it comes from | Install |
|---|---|---|---|
| Node.js 18+ and npm | Vite preview, Remotion render | system | <https://nodejs.org> |
| Vite, React, Remotion | lyric-MV front end and MP4 output | `package.json` | `npm install` |
| Python 3.10+ | `tools/videogen` | system | `winget install Python.Python.3.12` / `brew install python@3.12` / `apt install python3.12-venv` |
| videogen venv | all videogen commands | `tools/videogen/.venv`, or `$VIDEOGEN_VENV` | `tools/videogen/scripts/setup.{sh,ps1}` |
| PyTorch (CUDA build) | videogen GPU stages | PyTorch wheel index matching the driver (`TORCH_INDEX_URL`, default cu128) | setup script (skipped with `--cpu` / `-Cpu`) |
| diffusers ≥ 0.41, transformers ≥ 5 | Qwen-Image-2.1, Qwen-Image-Edit-2509, Wan-Animate-2, Wan2.2-TI2V-5B | PyPI (`tools/videogen` extra `gpu`) | setup script |
| Model weights (~110 GB total) | videogen GPU stages | Hugging Face, cached in `$HF_HOME` | downloaded on first use |
| ffmpeg with libass | clip I/O and burning lyrics at assembly | system ffmpeg (`$VIDEOGEN_FFMPEG`, then PATH), else the imageio-ffmpeg binary | <https://ffmpeg.org/download.html> or `winget install Gyan.FFmpeg` |
| Noto Serif TC | burned-in lyrics | system font | <https://fonts.google.com/noto/specimen/Noto+Serif+TC> |
| rcs (remote-console) | optional: `--host` profiles of kind `rcs` | `%LOCALAPPDATA%\remote-console\bin`, PATH or `$RCS_EXE` | remote-console installer |

## Pipeline steps

| Step | Tools |
|---|---|
| Lyric MV preview and render | Node, Vite, Remotion |
| videogen `keyframes`, `edit`, `clips` | Python venv, PyTorch, diffusers, model weights; local GPU or a `--host` |
| videogen `review`, `feedback`, `status` | Python venv only (CPU) |
| videogen `assemble` | Python venv and ffmpeg with libass, plus Noto Serif TC |

Health checks: `videogen --project data/videogen/<song> doctor` and `npm run videogen:test`.
