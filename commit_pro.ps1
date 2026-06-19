Set-Location $PSScriptRoot

# Limpiar locks stale de git
$locks = @(".git\HEAD.lock", ".git\index.lock", ".git\objects\maintenance.lock")
foreach ($lock in $locks) {
    if (Test-Path $lock) {
        Remove-Item $lock -Force -ErrorAction SilentlyContinue
        Write-Host "Lock eliminado: $lock"
    }
}

# Commit de todos los cambios PRO pendientes
git add voice/tools/briefing_tools.py voice/tools/system_control.py `
        voice/mate_calendar_auth.py voice/.env.example voice/mate_orb.spec `
        voice/SETUP_PRO.md voice/mate_pro_test.py

git commit -m "feat(PRO): briefing + calendar_auth + smoke_test + SETUP_PRO.md

- tools/briefing_tools.py: briefing matutino unificado
- mate_calendar_auth.py: auth script standalone para Google Calendar
- .env.example: variables PRO documentadas
- system_control.py: briefing, estado rapido, busca en el navegador
- mate_orb.spec: briefing_tools en hiddenimports
- SETUP_PRO.md: guia completa de configuracion PRO
- mate_pro_test.py: smoke test de todos los modulos PRO"

Write-Host ""
Write-Host "Listo. Commits pendientes:"
git log --oneline -5
