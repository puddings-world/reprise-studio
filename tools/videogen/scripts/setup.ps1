# Idempotent setup for videogen on Windows.
#
#   powershell -ExecutionPolicy Bypass -File tools/videogen/scripts/setup.ps1          # GPU stack (CUDA 12.8 torch)
#   powershell -ExecutionPolicy Bypass -File tools/videogen/scripts/setup.ps1 -Cpu     # review / feedback / assemble only
#
# Environment: VIDEOGEN_VENV (venv location), TORCH_INDEX_URL (PyTorch wheel index matching your driver).
param([switch]$Cpu)
$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $PSScriptRoot
$Venv = if ($env:VIDEOGEN_VENV) { $env:VIDEOGEN_VENV } else { Join-Path $Here ".venv" }
$Index = if ($env:TORCH_INDEX_URL) { $env:TORCH_INDEX_URL } else { "https://download.pytorch.org/whl/cu128" }

$Py = Get-Command py -ErrorAction SilentlyContinue
if ($Py) { $Base = @("py", "-3") } else {
  $Py = Get-Command python -ErrorAction SilentlyContinue
  if (-not $Py) { throw "Python >= 3.10 not found. Install it: winget install Python.Python.3.12" }
  $Base = @("python")
}
& $Base[0] $Base[1..9] -c "import sys; sys.exit(sys.version_info < (3, 10))"
if ($LASTEXITCODE -ne 0) { throw "Python >= 3.10 required (winget install Python.Python.3.12)" }

$VPy = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $VPy)) { & $Base[0] $Base[1..9] -m venv $Venv }
& $VPy -m pip install -q --upgrade pip

if ($Cpu) {
  & $VPy -m pip install -q -e "$Here[dev]" imageio-ffmpeg
} else {
  & $VPy -m pip install -q torch --index-url $Index
  & $VPy -m pip install -q -e "$Here[gpu,dev]"
}
& $VPy -m pytest -q (Join-Path $Here "tests")
if ($LASTEXITCODE -ne 0) { throw "videogen tests failed" }
Write-Host ""
Write-Host "videogen ready. Activate with: $Venv\Scripts\Activate.ps1"
Write-Host "Then check a project:  videogen --project data/videogen/<song> doctor"
