# Sustainability Report Crawler - Run script

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# ── Suppress Streamlit's first-run email prompt ───────────────────────────────
$stCreds = "$env:USERPROFILE\.streamlit\credentials.toml"
if (-not (Test-Path $stCreds)) {
    New-Item -ItemType Directory -Force "$env:USERPROFILE\.streamlit" | Out-Null
    "[general]`nemail = `"`"`n" | Set-Content $stCreds -Encoding UTF8
}

# ── 1. Try uv (auto-install if missing) ──────────────────────────────────────
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv not found — installing..." -ForegroundColor Cyan
    try {
        $ErrorActionPreference = "Continue"
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
        $ErrorActionPreference = "Stop"
        $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    } catch {
        $ErrorActionPreference = "Stop"
        Write-Host "Could not auto-install uv — will use pip instead." -ForegroundColor Yellow
    }
}

if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "Starting app with uv..." -ForegroundColor Green
    uv run streamlit run app.py
    exit
}

# ── 2. Pip fallback (when uv is unavailable) ─────────────────────────────────
Write-Host "Falling back to pip..." -ForegroundColor Yellow

$venvActivate = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
}
& $venvActivate

Write-Host "Installing/updating dependencies..." -ForegroundColor Cyan

# Install tornado <6.5 first to avoid a Windows Defender .pyd lock bug
# in tornado 6.5+ that blocks pip from completing the install.
$installed = $false
try {
    pip install "tornado>=6.0.3,<6.5.0" --quiet
    pip install -r requirements.txt --quiet
    $installed = $true
} catch {}

if (-not $installed) {
    Write-Host "Retrying with --trusted-host (corporate SSL proxy workaround)..." -ForegroundColor Yellow
    pip install "tornado>=6.0.3,<6.5.0" --quiet `
        --trusted-host pypi.org --trusted-host files.pythonhosted.org
    pip install -r requirements.txt --quiet `
        --trusted-host pypi.org --trusted-host files.pythonhosted.org
}

Write-Host "Starting app..." -ForegroundColor Green
python -m streamlit run app.py
