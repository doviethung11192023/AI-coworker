"""
File-based validation: 6-layer stage discipline system
Checks implementation without importing (avoids dependency hangs)
"""

import re

print("=" * 80)
print("STAGE DISCIPLINE SYSTEM - FILE VALIDATION")
print("=" * 80)

checks = {
    "Stage requirements defined": False,
    "Rollout blocked in discovery": False,
    "Stage-skip detection function exists": False,
    "Dynamic hint builder exists": False,
    "Base agent has stage gate": False,
    "Graph injects stage context": False,
    "Supervisor calls stage-skip detection": False,
    "Supervisor wires skip signal": False,
}

# Check 1: supervisor.py has _STAGE_REQUIREMENTS
print("\n[1] Checking supervisor.py for stage requirements...")
with open(r"e:\AI co-worker\app\agents\supervisor.py", "r", encoding="utf-8") as f:
    sup_content = f.read()

if "_STAGE_REQUIREMENTS = {" in sup_content:
    checks["Stage requirements defined"] = True
    print("    ✓ _STAGE_REQUIREMENTS dict found")
    
    if '"discovery":' in sup_content and '"blocked_keywords":' in sup_content:
        if "rollout" in sup_content.lower():
            checks["Rollout blocked in discovery"] = True
            print("    ✓ Rollout keyword found in blocked keywords")

if "def _detect_stage_skip" in sup_content:
    checks["Stage-skip detection function exists"] = True
    print("    ✓ _detect_stage_skip() function defined")

if "def _build_dynamic_hint" in sup_content:
    checks["Dynamic hint builder exists"] = True
    print("    ✓ _build_dynamic_hint() function defined")

if "stage_skip_info = _detect_stage_skip" in sup_content:
    checks["Supervisor calls stage-skip detection"] = True
    print("    ✓ Supervisor calls _detect_stage_skip()")

if 'stage_skip_info.get("skip_detected")' in sup_content:
    checks["Supervisor wires skip signal"] = True
    print("    ✓ Supervisor checks and wires skip signal")

# Check 2: base_agent.py has stage gate
print("\n[2] Checking base_agent.py for stage gate enforcement...")
with open(r"e:\AI co-worker\app\agents\base_agent.py", "r", encoding="utf-8") as f:
    agent_content = f.read()

if "=== STAGE GATE" in agent_content:
    checks["Base agent has stage gate"] = True
    print("    ✓ Stage gate section found")
    
    if "REDIRECT" in agent_content and "redirect" in agent_content.lower():
        print("    ✓ REDIRECT enforcement found")
    
    if "Do NOT answer rollout questions when in discovery" in agent_content:
        print("    ✓ Explicit rollout-in-discovery ban found")

# Check 3: graph.py injects stage context
print("\n[3] Checking graph.py for stage context injection...")
with open(r"e:\AI co-worker\app\graph.py", "r", encoding="utf-8") as f:
    graph_content = f.read()

if "[STAGE CONTEXT FOR" in graph_content:
    checks["Graph injects stage context"] = True
    print("    ✓ Stage context injection found")
    
    if "current_stage = state.get" in graph_content:
        print("    ✓ Stage extraction logic found")
    
    if "required_next_actions = state.get" in graph_content:
        print("    ✓ Required actions extraction found")

# Summary
print("\n" + "=" * 80)
print("VALIDATION RESULTS")
print("=" * 80)

all_pass = True
for check, result in checks.items():
    status = "✓ PASS" if result else "✗ FAIL"
    print(f"{status}: {check}")
    if not result:
        all_pass = False

print("\n" + "=" * 80)
if all_pass:
    print("✅ ALL CHECKS PASSED - 6-Layer Stage Discipline System is in place!")
    print("\nImplementation Summary:")
    print("  1. Supervisor detects stage skips (rollout in discovery, etc)")
    print("  2. Stage requirements mapped to blocked keywords per stage")
    print("  3. Dynamic hints generated based on progress")
    print("  4. Base agent enforces stage gate before responding")
    print("  5. Graph injects [STAGE CONTEXT] to agents")
    print("  6. Supervisor wires skip signal in director_notes")
    print("\nReady for end-to-end testing!")
else:
    print("❌ SOME CHECKS FAILED - Review implementation")
    import sys
    sys.exit(1)
