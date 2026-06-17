# setup_mate.ps1 — Configura MATE en una PC nueva
# Ejecutar desde la raíz del repo: .\setup_mate.ps1
# Requiere PowerShell 5+ y Python 3.10-3.12 instalado.

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
$VoiceDir = Join-Path $RepoRoot "voice"
$VenvDir  = Join-Path $VoiceDir "mate-wakeword-env"
$EnvFile  = Join-Path $VoiceDir ".env"

Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║        MATE — Setup en PC nueva              ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 1. Verificar Python ───────────────────────────────────────────────────────
Write-Host "▶ Verificando Python..." -ForegroundColor Yellow
try {
    $pyver = python --version 2>&1
    if ($pyver -notmatch "Python 3\.(1[0-2])") {
        Write-Host "  ⚠  Versión detectada: $pyver" -ForegroundColor Yellow
        Write-Host "  Se recomienda Python 3.10–3.12. Continuando de todas formas..." -ForegroundColor Yellow
    } else {
        Write-Host "  ✓ $pyver" -ForegroundColor Green
    }
} catch {
    Write-Host "  ✗ Python no encontrado. Instalá Python 3.10-3.12 desde https://python.org" -ForegroundColor Red
    exit 1
}

# ── 2. Crear entorno virtual ──────────────────────────────────────────────────
Write-Host ""
Write-Host "▶ Creando entorno virtual..." -ForegroundColor Yellow
if (Test-Path $VenvDir) {
    Write-Host "  ✓ El venv ya existe, omitiendo creación." -ForegroundColor Green
} else {
    python -m venv $VenvDir
    Write-Host "  ✓ Venv creado en $VenvDir" -ForegroundColor Green
}

# ── 3. Activar venv e instalar dependencias ───────────────────────────────────
Write-Host ""
Write-Host "▶ Instalando dependencias (puede tardar unos minutos)..." -ForegroundColor Yellow
$PipExe = Join-Path $VenvDir "Scripts\pip.exe"
& $PipExe install --upgrade pip --quiet
& $PipExe install -r (Join-Path $VoiceDir "requirements.txt")
Write-Host "  ✓ Dependencias instaladas." -ForegroundColor Green

# ── 4. Descargar modelos openwakeword base ────────────────────────────────────
Write-Host ""
Write-Host "▶ Verificando modelo de wake word..." -ForegroundColor Yellow
$OnnxPath = Join-Path $VoiceDir "models\oye_mate.onnx"
if (Test-Path $OnnxPath) {
    Write-Host "  ✓ oye_mate.onnx encontrado." -ForegroundColor Green
} else {
    Write-Host "  ⚠  No se encontró models\oye_mate.onnx" -ForegroundColor Yellow
    Write-Host "     Copiá el archivo desde la PC original o el repositorio." -ForegroundColor Yellow
}

# ── 5. Configurar .env ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "▶ Configurando .env..." -ForegroundColor Yellow
if (Test-Path $EnvFile) {
    Write-Host "  ✓ .env ya existe. Editalo manualmente si necesitás cambiar algo." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  ¿Estás en la misma red que la VM (red local)? [s/N]" -ForegroundColor Cyan
    $local = Read-Host "  Respuesta"
    if ($local -match "^[sS]$") {
        $mateUrl = "https://mate.local"
    } else {
        $mateUrl = "https://molmont.duckdns.org"
    }

    Write-Host ""
    Write-Host "  Anthropic API Key (para visión de pantalla, dejá vacío para omitir):" -ForegroundColor Cyan
    $anthropicKey = Read-Host "  ANTHROPIC_API_KEY"

    $envContent = @"
# MATE — Configuración generada por setup_mate.ps1
MATE_URL=$mateUrl
ANTHROPIC_API_KEY=$anthropicKey
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
"@
    Set-Content -Path $EnvFile -Value $envContent -Encoding UTF8
    Write-Host "  ✓ .env creado." -ForegroundColor Green
}

# ── 6. Login al backend ───────────────────────────────────────────────────────
Write-Host ""
Write-Host "▶ Login al backend MATE..." -ForegroundColor Yellow
$PythonExe = Join-Path $VenvDir "Scripts\python.exe"
$TokenFile  = Join-Path $VoiceDir ".mate_token"
if (Test-Path $TokenFile) {
    Write-Host "  ✓ Token existente encontrado. Omitiendo login." -ForegroundColor Green
} else {
    Push-Location $VoiceDir
    try { & $PythonExe mate_login.py } catch { Write-Host "  ⚠  Login falló: $_" -ForegroundColor Yellow }
    Pop-Location
}

# ── 7. Spotify (opcional) ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "▶ ¿Configurar Spotify ahora? [s/N]" -ForegroundColor Cyan
$doSpotify = Read-Host "  Respuesta"
if ($doSpotify -match "^[sS]$") {
    Write-Host "  SPOTIFY_CLIENT_ID:" -ForegroundColor Cyan
    $sid = Read-Host "  "
    Write-Host "  SPOTIFY_CLIENT_SECRET:" -ForegroundColor Cyan
    $ssec = Read-Host "  "

    # Actualizar .env
    (Get-Content $EnvFile) `
        -replace "^SPOTIFY_CLIENT_ID=.*", "SPOTIFY_CLIENT_ID=$sid" `
        -replace "^SPOTIFY_CLIENT_SECRET=.*", "SPOTIFY_CLIENT_SECRET=$ssec" |
        Set-Content $EnvFile -Encoding UTF8

    # Exportar para que el auth script los lea
    $env:SPOTIFY_CLIENT_ID     = $sid
    $env:SPOTIFY_CLIENT_SECRET = $ssec
    Push-Location $VoiceDir
    try { & $PythonExe mate_spotify_auth.py } catch { Write-Host "  ⚠  Auth Spotify falló: $_" -ForegroundColor Yellow }
    Pop-Location
}

# ── Listo ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ✅  MATE configurado correctamente           ║" -ForegroundColor Green
Write-Host "╠══════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║  Para iniciar:  .\run_mate.bat               ║" -ForegroundColor Green
Write-Host "║  O doble clic en run_mate.bat                ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
