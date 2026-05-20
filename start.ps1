param()

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$FrontendDir = Join-Path $RootDir "src" "web"
$VenvDir = Join-Path $RootDir ".venv"

function Log($msg) { Write-Host ">>> $msg" -ForegroundColor Green }

# ---------- dependency check ----------

Log "Kontrola Python..."
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "Python nenalezen. Nainstaluj Python 3.10+ z https://python.org" -ForegroundColor Red
  exit 1
}

Log "Kontrola npm..."
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  Write-Host "npm nenalezen. Nainstaluj Node.js z https://nodejs.org" -ForegroundColor Red
  exit 1
}

# ---------- Python virtual environment ----------

$ActivateScript = Join-Path $VenvDir "Scripts" "Activate.ps1"
if (-not (Test-Path $ActivateScript)) {
  Log "Vytvarim Python virtual environment..."
  python -m venv $VenvDir
}

Log "Aktivuji virtual environment..."
& $ActivateScript

# ---------- install Python dependencies ----------

$Reqs = @(
  "src/S3_Storage/requirements.txt",
  "src/messagebroker/requirements.txt",
  "src/haystack/requirements.txt",
  "src/imgprocessing/requirements.txt"
)

foreach ($rel in $Reqs) {
  $abs = Join-Path $RootDir $rel
  if (Test-Path $abs) {
    Log "Instalace $rel ..."
    pip install -q -r $abs 2>&1 | Out-Null
  }
}

# ---------- install frontend dependencies ----------

$NodeModules = Join-Path $FrontendDir "node_modules"
if (-not (Test-Path $NodeModules)) {
  Log "Instalace frontend dependencies..."
  Push-Location $FrontendDir
  npm install
  Pop-Location
}

# ---------- database migrations ----------

Log "Aplikuji database migrations..."
Push-Location $RootDir
alembic upgrade head
Pop-Location

# ---------- start services ----------

$Processes = @()

function Start-Service($name, $cmd, $argsList, $workDir) {
  Log "Spoustim $name ..."
  $proc = Start-Process -NoNewWindow -PassThru -FilePath $cmd -ArgumentList $argsList -WorkingDirectory $workDir
  $Script:Processes += $proc
}

function Cleanup {
  Log "Ukoncuji vsechny sluzby..."
  foreach ($p in $Script:Processes) {
    if ((-not $p.HasExited)) {
      $p.Kill()
    }
  }
}

Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Cleanup } | Out-Null

Push-Location $RootDir

Start-Service "Message Broker" "uvicorn" @("src.messagebroker.main:app", "--reload", "--host", "127.0.0.1", "--port", "8001") $RootDir
Start-Service "Haystack Node" "uvicorn" @("src.haystack.main:app", "--reload", "--host", "127.0.0.1", "--port", "8002") $RootDir
Start-Service "Backend (S3 Gateway)" "uvicorn" @("src.S3_Storage.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000") $RootDir
Start-Service "Image Worker" "python" @("-m", "src.imgprocessing.worker") $RootDir
Start-Service "Frontend" "npm" @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort") $FrontendDir

Pop-Location

Log "Vsechny sluzby bezi. Pro ukonceni stiskni Ctrl+C."

# Wait for any process to exit
while ($true) {
  Start-Sleep -Seconds 2
  foreach ($p in $Script:Processes) {
    if ($p.HasExited) {
      Log "$($p.ProcessName) skoncil. Ukoncuji vse."
      Cleanup
      exit
    }
  }
}
