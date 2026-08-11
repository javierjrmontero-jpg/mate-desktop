# Flujo de trabajo — mate-desktop (orbe)

Todo ocurre en Windows: no hay despliegue remoto. El "deploy" es regenerar el EXE.

| | Ruta |
|---|---|
| Repo | `D:\mate-desktop` |
| Código del orbe | `voice\` |
| EXE generado | `voice\dist\MATE\MATE.exe` |
| GitHub | `javierjrmontero-jpg/mate-desktop` |

## Ciclo normal

```powershell
cd D:\mate-desktop
git pull origin main

# ... editar voice\mate_orb.py, voice\tools\*.py, etc.

.\commit_pro.ps1          # limpia los git locks de Windows
git add <archivos>
git commit -m "tipo(alcance): descripción"
git push origin main

# Regenerar el EXE (cerrar el orbe antes: bloquea dist\)
Stop-Process -Name "MATE" -Force -ErrorAction SilentlyContinue
.\build_exe.ps1
```

`build_exe.ps1` copia solo `voice\.env` y `voice\mate.crt` a `dist\MATE\` (paso 3b).
**Editar siempre `voice\.env`**, no la copia dentro de `dist\`: el build la sobrescribe.

## Configuración por dispositivo

`voice\.env` y `voice\mate.crt` están en `.gitignore` — no se suben nunca.
Para instalar en otra PC: comprimir `voice\dist\MATE\` y descomprimir allá.
`MATE_TLS_VERIFY=mate.crt` es ruta relativa y se resuelve junto al EXE, así que el zip es portable.

## Primer arranque

Si no hay token, el orbe abre el wizard (`mate_setup.py`) a los 500 ms.
Usar **"Iniciar sesión en el navegador"**: el login por email/password del wizard
no soporta MFA ni OAuth.

Cómo llega el token al orbe:

```
navegador → login web → frontend guarda token
                     └→ POST http://127.0.0.1:27125/set-token
                            └→ orbe lo cifra con DPAPI y arranca el worker
```

El puerto **27125** no es arbitrario: Obsidian Local REST API ocupa 27123 y 27124.

## Estado del repo

- `main` — línea integrada (Fase 6 + hardening), commit de merge `e9f98c8`
- `feature/fase6-obsidian-graphiti` + tag `fase6-20260810` — resguardo previo al merge,
  se puede borrar cuando `main` esté validado en uso

## Cosas que muerden

- **Cloudflare devuelve 403 a clientes programáticos** en `mate.molmont.com.ar`.
  El orbe usa `mate.local` (LAN) justamente por eso.
- **Cerrar el orbe antes de buildear**: si no, `Remove-Item` falla sobre `dist\MATE`.
- **Modelo STT**: la constante `WHISPER_MODEL` en `mate_orb.py` es la fuente única.
  `model_integrity.py` guarda hashes por tamaño de modelo, así que cambiarlo no dispara
  un falso positivo de tampering.
