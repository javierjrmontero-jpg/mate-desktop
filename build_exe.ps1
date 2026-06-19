# build_exe.ps1 -- Empaqueta MATE como EXE con PyInstaller
# Ejecutar desde la raiz del repo con el venv activo:
#   .\voice\mate-wakeword-env\Scripts\Activate.ps1
#   .\build_exe.ps1
#
# Output: voice\dist\MATE\MATE.exe

$ErrorActionPreference = "Stop"
$VoiceDir  = Join-Path $PSScriptRoot "voice"
$PipExe    = Join-Path $VoiceDir "mate-wakeword-env\Scripts\pip.exe"
$PyExe     = Join-Path $VoiceDir "mate-wakeword-env\Scripts\python.exe"

Write-Host ""
Write-Host "=== MATE -- Build EXE (PyInstaller) ===" -ForegroundColor Cyan
Write-Host ""

# 1. Instalar PyInstaller si no esta
Write-Host "[1/4] Verificando PyInstaller..." -ForegroundColor Yellow
& $PipExe install pyinstaller --quiet
Write-Host "  OK - PyInstaller listo." -ForegroundColor Green

# 1b. Instalar dependencias PRO opcionales (Google Calendar, WhatsApp)
Write-Host ""
Write-Host "[1b/4] Instalando dependencias PRO opcionales..." -ForegroundColor Yellow
$proDeps = @(
    "google-auth-oauthlib",
    "google-auth-httplib2",
    "google-api-python-client",
    "pywhatkit"
)
# Desactivar Stop temporalmente para que errores de pip no aborte el build
$prevPref = $ErrorActionPreference
$ErrorActionPreference = "Continue"
foreach ($dep in $proDeps) {
    $out = & $PipExe install $dep --quiet 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK - $dep" -ForegroundColor DarkGreen
    } else {
        Write-Host "  SKIP - $dep (opcional)" -ForegroundColor DarkYellow
    }
}
$ErrorActionPreference = $prevPref

# 2. Limpiar builds anteriores
Write-Host ""
Write-Host "[2/4] Limpiando builds anteriores..." -ForegroundColor Yellow
$DistDir  = Join-Path $VoiceDir "dist"
$BuildDir = Join-Path $VoiceDir "build"
if (Test-Path $DistDir)  { Remove-Item $DistDir  -Recurse -Force }
if (Test-Path $BuildDir) { Remove-Item $BuildDir -Recurse -Force }
Write-Host "  OK - Limpio." -ForegroundColor Green

# 3. Build
Write-Host ""
Write-Host "[3/4] Compilando (puede tardar 3-10 minutos)..." -ForegroundColor Yellow
Push-Location $VoiceDir
& $PyExe -m PyInstaller mate_orb.spec --noconfirm
Pop-Location

# 4. Verificar output
Write-Host ""
Write-Host "[4/4] Verificando output..." -ForegroundColor Yellow
$ExePath = Join-Path $VoiceDir "dist\MATE\MATE.exe"
if (Test-Path $ExePath) {
    $size = [math]::Round((Get-Item $ExePath).Length / 1MB, 1)
    Write-Host ""
    Write-Host "=== BUILD EXITOSO ===" -ForegroundColor Green
    Write-Host "  EXE : voice\dist\MATE\MATE.exe" -ForegroundColor Green
    Write-Host "  Size: $size MB" -ForegroundColor Green
    Write-Host "  Para distribuir: comprime la carpeta voice\dist\MATE\ como MATE.zip" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  ERROR: Build fallo. Revisa los errores arriba." -ForegroundColor Red
    exit 1
}
