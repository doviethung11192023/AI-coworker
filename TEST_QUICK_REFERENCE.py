"""
QUICK REFERENCE - TEST DISCOVERY STAGE DISCIPLINE
===================================================
"""

import json

# ============================================================
# QUICK START CHECKLIST
# ============================================================

checklist = r"""
📋 QUICK START CHECKLIST - 5 PHÚT ĐỂ TEST
============================================

☐ 1. Start Ollama (Terminal 1):
     $ ollama serve
     Chờ: "listening on 127.0.0.1:11434"

☐ 2. Start Backend (Terminal 2):
     $ cd "e:\AI co-worker"
     $ set LOG_LEVEL=DEBUG
     $ python main.py
     Chờ: "Uvicorn running on http://127.0.0.1:8000"

☐ 3. Start Frontend (Terminal 3):
     $ cd "e:\AI co-worker"
     $ python gradio_app.py
     Chờ: "Running on local URL:  http://127.0.0.1:7860"

☐ 4. Open http://127.0.0.1:7860 in browser

☐ 5. Copy-paste test message vào chat

☐ 6. Đọc response + kiểm tra backend logs

Estimated time: 5 phút (sau khi services start)
"""

# ============================================================
# TEST MESSAGES (Copy-paste directly)
# ============================================================

test_messages = {
    "TEST 1: Stage Skip Attempt (Rollout in Discovery)": {
        "message": "How should we rollout this leadership system to all regions?",
        "stage": "DISCOVERY",
        "expected_behavior": "CHRO redirects with coaching about problem_statement",
        "expected_keywords": [
            "pump the brakes",
            "discovery",
            "problem",
            "first",
            "redirect"
        ],
        "NOT_expected": [
            "rollout",
            "timeline",
            "phase 1",
            "regions"
        ]
    },
    
    "TEST 2: Correct Answer (Problem Statement)": {
        "message": "The business problem we're solving is: Gucci Group leaders lack a shared mental model of our brand identity. We need to ensure all executives worldwide operate from the same 4 core values to maintain brand coherence.",
        "stage": "DISCOVERY",
        "expected_behavior": "Supervisor detects problem_statement deliverable, stage progresses or provides stage completion hint",
        "expected_keywords": [
            "problem",
            "complete",
            "alignment",
            "next",
            "4 pillar",
            "4 value"
        ],
        "NOT_expected": []
    },
    
    "TEST 3: Training Question in Alignment": {
        "message": "What's the training plan we'll use? I want to make sure managers are ready for the rollout.",
        "stage": "ALIGNMENT (假設已進入)",
        "expected_behavior": "CHRO redirects - stage blocks training questions, needs role family prioritization first",
        "expected_keywords": [
            "brakes",
            "alignment",
            "role families",
            "pillars",
            "critical"
        ],
        "NOT_expected": [
            "training",
            "plan",
            "rollout"
        ]
    },
    
    "TEST 4: Generic Problem (Should Get Feedback)": {
        "message": "We should implement a better communication system.",
        "stage": "DISCOVERY",
        "expected_behavior": "Agent challenges vagueness, asks for specific problem",
        "expected_keywords": [
            "vague",
            "specific",
            "problem",
            "why",
            "business impact"
        ],
        "NOT_expected": []
    }
}

# ============================================================
# WHAT TO MONITOR IN BACKEND LOGS
# ============================================================

backend_signals = {
    "Stage discipline is working": [
        "[INFO] Stage discipline alert: user asked about",
        "[DEBUG] _detect_stage_skip | skip_detected=True",
        "[DEBUG] Routing decision | reason=⚠️ Stage discipline"
    ],
    
    "Agent received stage context": [
        "[DEBUG] Agent start | name=chro",
        "[STAGE CONTEXT FOR",
        "Current stage: discovery"
    ],
    
    "Token streaming is active": [
        "[DEBUG] Supervisor raw response",
        "chunk events",
        "astream_events",
        "230+ chunk events"
    ],
    
    "Deliverable was detected": [
        "Deliverable detected: problem_statement",
        "Completed deliverables: ['problem_statement']",
        "Stage progress: 100%"
    ],
    
    "Stage transitioned": [
        "Stage complete",
        "Next stage: alignment",
        "Stage advancement"
    ]
}

# ============================================================
# METADATA TO CHECK IN UI
# ============================================================

metadata_checks = {
    "Discovery Stage - Before Answering": {
        "simulation_stage": "discovery",
        "required_next_actions": ["problem_statement"],
        "stage_progress": {"discovery": 0},
        "completed_deliverables": []
    },
    
    "Discovery Stage - After Stage Skip Detected": {
        "simulation_stage": "discovery",
        "director_notes": "⚠️ Stage discipline alert: user asked about 'rollout'",
        "required_next_actions": ["problem_statement"],
        "next_agent": "chro"
    },
    
    "Alignment Stage - After Transition": {
        "simulation_stage": "alignment",
        "required_next_actions": ["scope_clarification", "role_family_prioritization", "4pillar_mapping"],
        "stage_progress": {"discovery": 100},
        "completed_deliverables": ["problem_statement"]
    }
}

# ============================================================
# PERSONALITY MARKERS TO LISTEN FOR
# ============================================================

personality_markers = {
    "CHRO Personality (Coaching)": {
        "opening": "I need to pump the brakes here",
        "redirect_language": "we're still in discovery",
        "tone": "coaching, firm but supportive",
        "examples": [
            "I appreciate you're thinking ahead, but...",
            "Let me redirect to what matters first",
            "We need to lock down the problem definition",
            "Once we have that clarity..."
        ]
    },
    
    "CEO Personality (Protective)": {
        "opening": "I need you to lock down something far more critical",
        "redirect_language": ["brand DNA", "autonomy", "strategic tradeoff"],
        "tone": "decisive, protective, veto power",
        "examples": [
            "That's thinking about the symptom, not the disease",
            "We cannot compromise on brand coherence",
            "I'm going to veto this unless we..."
        ]
    },
    
    "Regional Personality (Practical)": {
        "opening": "That rollout plan sounds nice, but it won't work",
        "redirect_language": ["adoption reality", "field friction", "local resistance"],
        "tone": "blunt, practical, no-nonsense",
        "examples": [
            "I've seen this fail in the field",
            "Managers won't buy in if we skip this step",
            "Regional resistance is inevitable unless..."
        ]
    }
}

# ============================================================
# PRINT ALL INFO
# ============================================================

print(checklist)
print("\n" + "="*60)
print("TEST MESSAGES (COPY-PASTE DIRECTLY INTO CHAT)")
print("="*60 + "\n")

for test_name, test_data in test_messages.items():
    print(f"\n📝 {test_name}")
    print(f"   Message: {test_data['message']}")
    print(f"   Stage: {test_data['stage']}")
    print(f"   Expected: {test_data['expected_behavior']}")
    print(f"   Should see: {', '.join(test_data['expected_keywords'][:3])}...")
    print()

print("\n" + "="*60)
print("BACKEND LOG SIGNALS TO MONITOR")
print("="*60 + "\n")

for signal_name, signals in backend_signals.items():
    print(f"\n✓ {signal_name}:")
    for sig in signals:
        print(f"   • {sig}")

print("\n" + "="*60)
print("METADATA SNAPSHOTS TO EXPECT")
print("="*60 + "\n")

for snapshot_name, metadata in metadata_checks.items():
    print(f"\n📊 {snapshot_name}:")
    print(json.dumps(metadata, indent=2, ensure_ascii=False))

print("\n" + "="*60)
print("PERSONALITY MARKERS")
print("="*60 + "\n")

for persona, markers in personality_markers.items():
    print(f"\n🎭 {persona}:")
    print(f"   Opening: '{markers['opening']}'")
    print(f"   Tone: {markers['tone']}")

print("""

╔═══════════════════════════════════════════════════════════════╗
║ READY! 🚀                                                    ║
║                                                               ║
║ Next step: Follow the checklist above to start services      ║
║            then test messages one by one                     ║
╚═══════════════════════════════════════════════════════════════╝
""")
