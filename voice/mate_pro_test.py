#!/usr/bin/env python3
"""
MATE PRO Smoke Test
Verifica que todos los módulos PRO importan y sus funciones básicas funcionan
sin necesidad de hardware de audio ni credenciales externas.
"""

import sys
import os
from pathlib import Path

# Asegurar que tools/ está en el path
BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

PASS = "OK"
FAIL = "FAIL"
SKIP = "SKIP"

results = []


def check(name: str, fn, *args):
    try:
        result = fn(*args)
        status = PASS
        detail = str(result)[:80] if result else "(vacío)"
    except Exception as e:
        status = FAIL
        detail = str(e)[:100]
    results.append((status, name, detail))
    marker = "✓" if status == PASS else "✗"
    print(f"  {marker} {name}: {detail}")


print("=" * 60)
print("  MATE PRO — Smoke Test")
print("=" * 60)

# ── Memoria ───────────────────────────────────────────────────────────────────
print("\n[memory_tools]")
from tools.memory_tools import remember, recall, forget, list_memories, get_context_summary
check("remember",            remember, "test_key", "test_value_PRO")
check("recall",              recall, "test_key")
check("list_memories",       list_memories)
check("get_context_summary", get_context_summary)
check("forget",              forget, "test_key")

# ── Dev Agent ─────────────────────────────────────────────────────────────────
print("\n[dev_agent_tools]")
from tools.dev_agent_tools import run_python, list_scripts, run_last_script
check("run_python (hello)",  run_python, 'print("MATE Dev Agent OK")', "smoke_test")
check("list_scripts",        list_scripts)
check("run_last_script",     run_last_script)

# ── Ghost Operator ────────────────────────────────────────────────────────────
print("\n[ghost_operator] (solo importación — sin ejecutar pyautogui)")
try:
    from tools import ghost_operator
    print("  ✓ Import OK")
    results.append((PASS, "ghost_operator import", ""))
except Exception as e:
    print(f"  ✗ Import FAIL: {e}")
    results.append((FAIL, "ghost_operator import", str(e)))

# ── Mensajería ────────────────────────────────────────────────────────────────
print("\n[messaging_tools]")
from tools.messaging_tools import send_telegram, send_whatsapp
# Sin credenciales debe retornar instrucciones, no error
check("send_telegram (sin creds)",  send_telegram, "test")
check("send_whatsapp (sin número)", send_whatsapp, "test")

# ── Calendario ────────────────────────────────────────────────────────────────
print("\n[calendar_tools]")
from tools.calendar_tools import create_event, get_today_events, get_week_events
check("create_event (local fallback)", create_event, "Reunión test", "mañana", "10:00")
check("get_today_events",             get_today_events)
check("get_week_events",              get_week_events)

# ── Briefing ──────────────────────────────────────────────────────────────────
print("\n[briefing_tools]")
from tools.briefing_tools import get_morning_briefing, get_quick_status
check("get_morning_briefing", get_morning_briefing)
check("get_quick_status",     get_quick_status)

# ── Resumen ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
print(f"  Resultado: {passed}/{len(results)} OK  |  {failed} fallidos")
if failed == 0:
    print("  ✓ Todos los módulos PRO están listos.")
else:
    print("  ✗ Revisá los módulos marcados con ✗ arriba.")
print("=" * 60)
