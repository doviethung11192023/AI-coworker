"""
RUN THESE COMMANDS TO START TESTING
====================================
Just copy-paste the commands below into your terminals
"""

import os

commands = {
    "Terminal 1 - OLLAMA": [
        "# Mở Terminal mới hoặc sử dụng terminal sẵn có",
        "# Chuyển đến folder AI co-worker",
        'cd "e:\\AI co-worker"',
        "",
        "# Khởi động Ollama (nếu chưa chạy)",
        "ollama serve",
        "",
        "# Chờ cho đến khi thấy:",
        "# 'listening on 127.0.0.1:11434'",
    ],
    
    "Terminal 2 - BACKEND": [
        "# Mở Terminal mới",
        'cd "e:\\AI co-worker"',
        "",
        "# Set log level DEBUG để xem stage discipline alerts",
        "set LOG_LEVEL=DEBUG",
        "",
        "# Khởi động FastAPI backend",
        "python main.py",
        "",
        "# Chờ cho đến khi thấy:",
        "# 'Uvicorn running on http://127.0.0.1:8000'",
        "# 'Application startup complete'",
    ],
    
    "Terminal 3 - FRONTEND": [
        "# Mở Terminal mới thứ 3",
        'cd "e:\\AI co-worker"',
        "",
        "# Khởi động Gradio frontend",
        "python gradio_app.py",
        "",
        "# Chờ cho đến khi thấy:",
        "# 'Running on local URL:  http://127.0.0.1:7860'",
    ],
}

print("="*70)
print("COMMAND REFERENCE - COPY-PASTE INTO EACH TERMINAL")
print("="*70)

for terminal_name, command_list in commands.items():
    print(f"\n\n{'='*70}")
    print(f"📌 {terminal_name}")
    print('='*70)
    for cmd in command_list:
        if cmd.startswith("#"):
            print(f"  {cmd}")
        elif cmd == "":
            print("")
        else:
            print(f"  > {cmd}")

print(f"\n\n{'='*70}")
print("BROWSER - AFTER ALL THREE TERMINALS ARE RUNNING")
print('='*70)
print("""
  1. Open browser: http://127.0.0.1:7860
  2. Wait for Gradio interface to load
  3. Check sidebar shows:
     - Simulation Stage: discovery
     - Required: ["problem_statement"]
     - Cadence: Balanced (or Human for slower typing)
  4. Ready to test!
""")

print(f"\n\n{'='*70}")
print("TEST MESSAGES - COPY INTO CHAT")
print('='*70)

test_msgs = {
    "Test 1 - Rollout Skip (Should redirect)": 
        "How should we rollout this leadership system to all regions?",
    
    "Test 2 - Correct Answer (Should advance stage)":
        "The business problem we're solving is: Gucci Group leaders lack a shared mental model of what drives our brand. We need to ensure all executives worldwide operate from the same 4 core values.",
    
    "Test 3 - Vague Problem (Should be challenged)":
        "We should implement a better communication system.",
    
    "Test 4 - In-stage Question (Should be answered)":
        "What are the key leadership competencies we should focus on?",
}

for test_name, msg in test_msgs.items():
    print(f"\n  📝 {test_name}:")
    print(f"     {msg}")

print(f"\n\n{'='*70}")
print("WHAT TO MONITOR")
print('='*70)

monitoring = """
  BACKEND TERMINAL (Terminal 2):
  ─────────────────────────────────
  Look for these log messages:
  
  ✓ Stage skip detected:
    "Stage discipline alert: user asked about 'rollout'"
  
  ✓ Deliverable detected:
    "Deliverable detected: problem_statement"
  
  ✓ Stage advanced:
    "Stage complete: discovery → alignment"
  
  ✓ Agent routing:
    "Routing decision | next_agent=chro"
  
  ✓ Token stream:
    "astream_events emitted 234 chunk events"
  

  FRONTEND (Browser):
  ─────────────────────────────────
  
  ✓ Typing effect visible
    Response appears character-by-character with cursor (▌)
  
  ✓ Redirect message appears
    Not a rollout plan, but coaching question
  
  ✓ Metadata updates
    simulation_stage, required_next_actions, etc.
  
  ✓ Personality present
    "I need to pump the brakes" (CHRO)
    "I need you to lock down" (CEO)
    "That won't work if we skip" (Regional)
"""
print(monitoring)

print(f"\n{'='*70}")
print("⏱️  TIMING")
print('='*70)
print("""
  • Ollama startup: 5-10 seconds
  • Backend startup: 3-5 seconds
  • Frontend startup: 2-3 seconds
  • Response time: 5-15 seconds per message (token stream)
  
  Total from start to first test: ~15-30 seconds
  Test duration: 2-3 minutes for all 4 tests
""")

print(f"\n{'='*70}")
print("🎯 EXPECTED RESULTS")
print('='*70)
print("""
  ✅ Test 1 (Rollout Skip):
     → CHRO redirects with coaching about problem_statement
     → NOT a rollout plan
     → Stage stays at "discovery"
  
  ✅ Test 2 (Problem Answer):
     → System acknowledges problem_statement deliverable
     → Stage advances to "alignment"
     → Required actions update to role_family, 4pillar_mapping
  
  ✅ Test 3 (Vague Problem):
     → Agent challenges vagueness
     → Asks for specific business impact
  
  ✅ Test 4 (In-stage Question):
     → Agent answers directly (not redirected)
     → Response aligned with stage (competencies ✓, rollout ✗)
""")

print(f"\n{'='*70}")
print("🚨 TROUBLESHOOTING")
print('='*70)
print("""
  Q: Ollama won't start
  A: Check port 11434 is available, or Ollama already running
     Try: lsof -i :11434 (Mac/Linux) or netstat -ano (Windows)
  
  Q: Backend crashes with import error
  A: Check venv is activated and requirements.txt installed
     Try: pip install -r requirements.txt
  
  Q: Response is instant (no typing effect)
  A: Gradio setting - change Cadence to "Human" (0.06s)
     Or Backend might be returning all tokens at once
  
  Q: Stage discipline not working
  A: Check backend logs for "Stage discipline alert"
     Run: python file_validate_stage.py to verify implementation
  
  Q: Response is generic (not CHRO personality)
  A: Check CHRO persona in app/core/prompts.py
     Check stage context injection in app/graph.py
     Verify [STAGE CONTEXT FOR CHRO] message in logs
""")

print(f"\n{'='*70}")
print("✅ READY TO TEST!")
print('='*70)
print("""
  Next step: Follow the commands above and test stage discipline
  Expected: Stage skips are detected, redirects work, personality present
""")
