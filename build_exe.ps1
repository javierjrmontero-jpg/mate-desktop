# build_exe.ps1 — Empaqueta MATE como EXE con PyInstaller
# Ejecutar desde la raíz del repo con el venv activo:
#   .\voice\mate-wakeword-env\Scripts\Activate.ps1
#   .\build_exe.ps1
#
# Output: voice\dist\MATE\MATE.exe

$ErrorActionPreference = "Stop"
$VoiceDir  = Join-Path $PSScriptRoot "voice"
$PipExe    = Join-Path $VoiceDir "mate-wakeword-env\Scripts\pip.exe"
$PyExe     = Join-Path $VoiceDir "mate-wakeword-env\Scripts\python.exe"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║       MATE — Build EXE (PyInstaller)         ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# 1. Instalar PyInstaller si no está
Write-Host "▶ Verificando PyInstaller..." -ForegroundColor Yellow
& $PipExe install pyinstaller --quiet
Write-Host "  ✓ PyInstaller listo." -ForegroundColor Green

# 2. Limpiar builds anteriores
Write-Host ""
Write-Host "▶ Limpiando builds anteriores..." -ForegroundColor Yellow
$DistDir  = Join-Path $VoiceDir "dist"
$BuildDir = Join-Path $VoiceDir "build"
if (Test-Path $DistDir)  { Remove-Item $DistDir  -Recurse -Force }
if (Test-Path $BuildDir) { Remove-Item $BuildDir -Recurse -Force }
Write-Host "  ✓ Limpio." -ForegroundColor Green

# 3. Build
Write-Host ""
Write-Host "▶ Compilando (puede tardar 3-10 minutos)..." -ForegroundColor Yellow
Push-Location $VoiceDir
& $PyExe -m PyInstaller mate_orb.spec --noconfirm
Pop-Location

# 4. Verificar output
$ExePath = Join-Path $VoiceDir "dist\MATE\MATE.exe"
if (Test-Path $ExePath) {
    $size = [math]::Round((Get-Item $ExePath).Length / 1MB, 1)
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║  ✅  Build exitoso                            ║" -ForegroundColor Green
    Write-Host "╠══════════════════════════════════════════════╣" -ForegroundColor Green
    Write-Host "║  EXE: voice\dist\MATE\MATE.exe               ║" -ForegroundColor Green
    Write-Host "║  Tamaño: $size MB" -ForegroundColor Green
    Write-Host "║                                              ║" -ForegroundColor Green
    Write-Host "║  Para distribuir: comprimí la carpeta        ║" -ForegroundColor Green
    Write-Host "║  voice\dist\MATE\ como MATE.zip              ║" -ForegroundColor Green
    Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  ✗ Build falló. Revisá los errores arriba." -ForegroundColor Red
    exit 1
}
