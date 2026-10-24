#!/usr/bin/env bash
# Idempotent setup for videogen on Linux / macOS (any machine: laptop, workstation, rented GPU box).
#
#   bash tools/videogen/scripts/setup.sh            # GPU stack, torch for CUDA 12.8
#   bash tools/videogen/scripts/setup.sh --cpu      # review / feedback / assemble only (no torch)
#
# Environment:
#   VIDEOGEN_VENV     venv location (default: tools/videogen/.venv). Use a big disk on shared servers.
#   TORCH_INDEX_URL   PyTorch wheel index (default: https://download.pytorch.org/whl/cu128).
#                     Pick the one matching `nvidia-smi` (cu126, cu128, ...). macOS uses PyPI automatically.
#   PIP_EXTRA         extra pip flags, e.g. "--no-deps" pins or a proxy.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${VIDEOGEN_VENV:-$HERE/.venv}"
MODE="gpu"; [[ "${1:-}" == "--cpu" ]] && MODE="cpu"

PY="$(command -v python3.12 || command -v python3.11 || command -v python3 || true)"
[[ -z "$PY" ]] && { echo "python3 >= 3.10 not found. Install it (e.g. 'brew install python@3.12' or 'apt install python3.12-venv')."; exit 1; }
"$PY" - <<'EOF' || { echo "python >= 3.10 required"; exit 1; }
import sys; sys.exit(sys.version_info < (3, 10))
EOF

[[ -x "$VENV/bin/python" ]] || "$PY" -m venv "$VENV"
"$VENV/bin/python" -m pip install -q --upgrade pip ${PIP_EXTRA:-}

if [[ "$MODE" == "gpu" ]]; then
  if [[ "$(uname)" == "Darwin" ]]; then
    "$VENV/bin/pip" install -q torch ${PIP_EXTRA:-}
  else
    # Installing from the CUDA index keeps torch matched to the driver; PyPI's default build may not be.
    "$VENV/bin/pip" install -q torch --index-url "${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu128}" ${PIP_EXTRA:-}
  fi
  "$VENV/bin/pip" install -q -e "$HERE[gpu,dev]" ${PIP_EXTRA:-}
else
  "$VENV/bin/pip" install -q -e "$HERE[dev]" imageio-ffmpeg ${PIP_EXTRA:-}
fi

"$VENV/bin/python" -m pytest -q "$HERE/tests"
echo
echo "videogen ready ($MODE). Activate with: source $VENV/bin/activate"
echo "Then check a project:  videogen --project data/videogen/<song> doctor"
