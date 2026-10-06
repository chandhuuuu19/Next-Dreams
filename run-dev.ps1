param(
    [switch]$ApplyMigrations,
    [switch]$SkipFrontend,
    [switch]$SkipBackend,
    [ValidateRange(1,65535)][int]$BackendPort = 8000,
    [ValidateRange(1,65535)][int]$FrontendPort = 3000
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendRoot = Join-Path $ProjectRoot 'backend'
$BackendPython = Join-Path $BackendRoot '.venv\Scripts\python.exe'

if ($ApplyMigrations) {
    if (-not (Get-Command 'supabase' -ErrorAction SilentlyContinue)) {
        throw 'Supabase CLI is not installed. Install it, authenticate, and link this folder to your project before applying migrations.'
    }
    Push-Location $ProjectRoot
    try { & supabase db push; if ($LASTEXITCODE -ne 0) { throw 'Supabase migration push failed.' } }
    finally { Pop-Location }
}

if (-not $SkipBackend) {
    if (-not (Test-Path -LiteralPath $BackendPython)) {
        throw "Backend virtual environment not found at $BackendPython. Create it and install backend/requirements-lock.txt first."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $BackendRoot '.env'))) {
        Write-Warning 'backend/.env is missing. Copy backend/.env.example and configure Supabase before using authentication.'
    }
    if (Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue) {
        throw "Backend port $BackendPort is already in use. Choose another with -BackendPort."
    }
    Start-Process -FilePath 'powershell.exe' -WorkingDirectory $BackendRoot -ArgumentList @('-NoExit','-Command',"& '$BackendPython' -m uvicorn app.main:app --reload --port $BackendPort")
}

if (-not $SkipFrontend) {
    if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot 'node_modules'))) {
        throw 'Node dependencies are missing. Run pnpm install first.'
    }
    $PnpmCommand = (Get-Command 'pnpm' -ErrorAction Stop).Source
    $frontendCommand = "`$env:NEXT_PUBLIC_API_BASE_URL='http://localhost:$BackendPort'; & '$PnpmCommand' dev --port $FrontendPort"
    Start-Process -FilePath 'powershell.exe' -WorkingDirectory $ProjectRoot -ArgumentList @('-NoExit','-Command',$frontendCommand)
}

Write-Host 'Nexora development services launched in separate PowerShell windows.'
Write-Host "Frontend requested at http://localhost:$FrontendPort; API requested at http://localhost:$BackendPort."
Write-Host 'Apply the Supabase migration to your configured project before testing database-backed features.'
