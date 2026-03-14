# Sustainability Report Crawler - Run script
# Requires Python 3.10+ (3.11+ recommended). Crawlee 1.x does not support Python 3.9.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Prefer Python 3.11, then 3.10, then default python
$py = $null
foreach ($ver in @("3.11", "3.10")) {
    try {
        $out = & py -$ver -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) {
            $py = $out.Trim()
            break
        }
    } catch {}
}
if (-not $py) {
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
}

if (-not $py) {
    Write-Host "Python not found. Install Python 3.11+ from https://www.python.org/downloads/ or run: winget install Python.Python.3.11" -ForegroundColor Red
    exit 1
}

$verStr = & $py --version 2>&1
Write-Host "Using: $py ($verStr)"

# Check version is at least 3.10
$v = & $py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
if ($v) {
    $major, $minor = $v -split '\.'
    if ([int]$major -lt 3 -or ([int]$major -eq 3 -and [int]$minor -lt 10)) {
        Write-Host "This project requires Python 3.10+ (Crawlee 1.x). You have $verStr" -ForegroundColor Red
        Write-Host "Install Python 3.11: winget install Python.Python.3.11" -ForegroundColor Yellow
        exit 1
    }
}

# Use venv if present; otherwise run streamlit via python -m
$venvScript = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $venvScript) {
    Write-Host "Activating .venv..."
    & $venvScript
    & streamlit run app.py
} else {
    Write-Host "No .venv found. Install deps with: $py -m pip install -r requirements.txt" -ForegroundColor Yellow
    & $py -m streamlit run app.py
}
