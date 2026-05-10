"""
Quick validation: 6-layer stage discipline system
Test core functions without needing full LLM stack
"""

import sys
sys.path.insert(0, r"e:\AI co-worker")

print("=" * 80)
print("STAGE DISCIPLINE SYSTEM - QUICK VALIDATION")
print("=" * 80)

# Test 1: Verify stage requirements are defined
print("\n✓ TEST 1: Stage requirements constants")
try:
    from app.agents.supervisor import _STAGE_REQUIREMENTS
    
    for stage in ["discovery", "alignment", "execution_planning"]:
        assert stage in _STAGE_REQUIREMENTS, f"Missing stage: {stage}"
        config = _STAGE_REQUIREMENTS[stage]
        assert "required_actions" in config
        assert "hint_base" in config
        assert "blocked_keywords" in config
        print(f"  ✓ {stage}: {len(config['blocked_keywords'])} blocked keywords configured")
    
    # Verify discovery blocks rollout
    discovery_blocked = _STAGE_REQUIREMENTS["discovery"]["blocked_keywords"]
    assert "rollout" in discovery_blocked, "CRITICAL: rollout not blocked in discovery!"
    print(f"  ✓ discovery blocks rollout: {[k for k in discovery_blocked if 'roll' in k.lower()]}")
    
except AssertionError as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)
except ImportError as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)

# Test 2: Verify stage-skip detection function signature
print("\n✓ TEST 2: Stage-skip detection function")
try:
    from app.agents.supervisor import _detect_stage_skip
    
    # Test with simple tuple messages
    messages = [("user", "How should we rollout this?")]
    result = _detect_stage_skip(messages, "discovery")
    
    assert isinstance(result, dict), "Result should be dict"
    assert "skip_detected" in result, "Result should have skip_detected key"
    assert result["skip_detected"] == True, "Should detect rollout in discovery"
    assert result.get("user_asked") == "rollout", "Should identify blocked keyword"
    
    print(f"  ✓ Detects rollout in discovery: {result}")
    
    # Test with allowed stage
    result2 = _detect_stage_skip(messages, "execution_planning")
    assert result2["skip_detected"] == False, "Rollout should be allowed in execution_planning"
    print(f"  ✓ Allows rollout in execution_planning: {result2}")
    
except AssertionError as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)

# Test 3: Verify dynamic hint builder
print("\n✓ TEST 3: Dynamic hint builder")
try:
    from app.agents.supervisor import _build_dynamic_hint
    
    hint_discovery = _build_dynamic_hint("discovery", {"discovery": 30})
    assert len(hint_discovery) > 0, "Hint should not be empty"
    assert "problem" in hint_discovery.lower(), "Discovery hint should mention problem"
    print(f"  ✓ Discovery hint (30% progress): {hint_discovery[:60]}...")
    
    hint_alignment = _build_dynamic_hint("alignment", {"alignment": 75})
    assert "75" in str(hint_alignment) or "75%" in str(hint_alignment) or "nearly" in hint_alignment.lower(), "Should show near-complete status"
    print(f"  ✓ Alignment hint (75% progress): {hint_alignment[:60]}...")
    
except AssertionError as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)

# Test 4: Verify base agent has stage gate section
print("\n✓ TEST 4: Base agent personality enforcement")
try:
    with open(r"e:\AI co-worker\app\agents\base_agent.py", "r") as f:
        content = f.read()
    
    assert "=== STAGE GATE ===" in content, "Missing stage gate section"
    print(f"  ✓ Base agent has stage gate section")
    
    assert "REDIRECT" in content, "Missing REDIRECT instruction"
    print(f"  ✓ Base agent has redirect enforcement")
    
    assert "=== PERSONALITY ENFORCEMENT ===" in content, "Missing personality section"
    print(f"  ✓ Base agent has personality enforcement section")
    
    assert "Do NOT answer rollout questions when in discovery" in content
    print(f"  ✓ Base agent explicitly bans rollout in discovery")
    
except AssertionError as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)

# Test 5: Verify graph.py injects stage context
print("\n✓ TEST 5: Stage context injection in graph")
try:
    with open(r"e:\AI co-worker\app\graph.py", "r") as f:
        content = f.read()
    
    assert "[STAGE CONTEXT FOR" in content, "Missing stage context injection"
    print(f"  ✓ Graph injects stage context to agents")
    
    assert "current_stage = state.get" in content, "Missing stage extraction"
    print(f"  ✓ Graph extracts current_stage from state")
    
    assert "required_next_actions = state.get" in content, "Missing required actions extraction"
    print(f"  ✓ Graph extracts required_next_actions from state")
    
except AssertionError as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)

# Test 6: Verify supervisor has stage skip wiring
print("\n✓ TEST 6: Supervisor stage-skip wiring")
try:
    with open(r"e:\AI co-worker\app\agents\supervisor.py", "r") as f:
        content = f.read()
    
    assert "stage_skip_info = _detect_stage_skip" in content, "Supervisor should call _detect_stage_skip"
    print(f"  ✓ Supervisor calls _detect_stage_skip()")
    
    assert "stage_skip_info.get('skip_detected')" in content, "Supervisor should check skip_detected flag"
    print(f"  ✓ Supervisor checks skip_detected flag")
    
    assert "Stage discipline alert" in content, "Supervisor should set alert in director_notes"
    print(f"  ✓ Supervisor includes stage discipline alert in director_notes")
    
except AssertionError as e:
    print(f"  ✗ FAILED: {e}")
    sys.exit(1)

print("\n" + "=" * 80)
print("✅ ALL VALIDATIONS PASSED - 6-Layer Stage Discipline System is Ready!")
print("=" * 80)

print("""
IMPLEMENTATION SUMMARY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Layer 1: SUPERVISOR STAGE DETECTION ✓
  • _detect_stage_skip() detects rollout/deploy/etc in discovery stage
  • Returns: skip_detected flag + required_actions
  • Integrated into supervisor_node() to check every turn

Layer 2: STAGE REQUIREMENTS MAPPING ✓
  • _STAGE_REQUIREMENTS dict defines blocked keywords per stage
  • discovery blocks: rollout, deploy, implement, training, adoption, pilot...
  • alignment blocks: training, adoption, regional resistance, rollout...
  • execution_planning blocks: (none - all questions allowed)

Layer 3: DYNAMIC HINTS & REQUIREMENTS ✓
  • _build_dynamic_hint() generates context-aware hints based on progress
  • Hints change based on 0%, 50%, 75%+ completion
  • required_next_actions passed from supervisor to agent

Layer 4: AGENT STAGE GATE ENFORCEMENT ✓
  • Base agent system prompt has "=== STAGE GATE ===" section
  • Agent reads [STAGE CONTEXT] injected by graph.py
  • Explicitly bans stage-skip answers with REDIRECT instruction
  • Agents must check stage BEFORE answering user question

Layer 5: STAGE CONTEXT INJECTION ✓
  • graph.py _wrap_agent() injects "[STAGE CONTEXT FOR AGENT]" message
  • Contains current_stage + required_next_actions
  • Passed as SystemMessage before other context

Layer 6: SUPERVISOR SKIP ALERT ✓
  • supervisor_node() includes skip signal in director_notes
  • Format: "⚠️ Stage discipline alert: user asked [X] but we're in [Y]"
  • Required actions shown in reason field

VERIFICATION:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Stage requirements configured for all 3 stages
✓ Rollout blocked in discovery (core case)
✓ Stage-skip detection function working
✓ Dynamic hints properly context-aware
✓ Base agent has enforcement section
✓ Graph injects stage context
✓ Supervisor calls and wires detection

NEXT: Run end-to-end websocket test
  User: "How to rollout?" (in discovery)
  Expected: Supervisor detects skip → Routes to CHRO → CHRO redirects with coaching
""")
