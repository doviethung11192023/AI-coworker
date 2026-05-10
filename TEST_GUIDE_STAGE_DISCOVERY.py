"""
HƯỚNG DẪN TEST HỆ THỐNG STAGE DISCIPLINE TRÊN GRADIO
=============================================================

Khi user ở stage DISCOVERY và hỏi về ROLLOUT/DEPLOY, hệ thống sẽ:
1. Supervisor phát hiện stage skip
2. CHRO được route để redirect
3. Kết quả: User thấy coaching redirect chứ không phải rollout plan
"""

# ============================================================
# BƯỚC 1: KHỞI ĐỘNG HỆ THỐNG
# ============================================================

print("""
BƯỚC 1: KHỞI ĐỘNG OLLAMA (nếu chưa chạy)
==========================================
Terminal 1 - Ollama:
  $ ollama serve
  
Chờ cho đến khi thấy "listening on 127.0.0.1:11434"
""")

print("""
BƯỚC 2: KHỞI ĐỘNG FASTAPI BACKEND
===================================
Terminal 2 - Backend:
  $ cd "e:\AI co-worker"
  $ set LOG_LEVEL=DEBUG
  $ python main.py
  
Chờ cho đến khi thấy: "Uvicorn running on http://127.0.0.1:8000"
""")

print("""
BƯỚC 3: KHỞI ĐỘNG GRADIO FRONTEND
==================================
Terminal 3 - Frontend:
  $ cd "e:\AI co-worker"
  $ python gradio_app.py
  
Chờ cho đến khi thấy: "Running on local URL:  http://127.0.0.1:7860"
""")

# ============================================================
# BƯỚC 4: TEST SCENARIO DISCOVERY STAGE
# ============================================================

print("""
BƯỚC 4: TRUY CẬP GRADIO & TEST SCENARIO
========================================

1. Mở trình duyệt: http://127.0.0.1:7860

2. Hệ thống sẽ khởi động ở stage: DISCOVERY
   (Kiểm tra ở mục "Simulation Stage" trong sidebar)

3. Current Required Actions: ["problem_statement"]
   (Tức là cần user định nghĩa business problem trước)

4. Enabled Co-workers: CEO, CHRO, Regional (tất cả được enable)

5. Cadence Setting: Chọn "Balanced" hoặc "Human" để xem typing effect
   (Fast quá sẽ không thấy token-by-token)
""")

# ============================================================
# TEST CASE 1: DISCOVERY STAGE - ROLLOUT SKIP ATTEMPT
# ============================================================

print("""
╔═══════════════════════════════════════════════════════════════╗
║ TEST CASE 1: USER HỎI ROLLOUT TRONG DISCOVERY (STAGE SKIP)  ║
╚═══════════════════════════════════════════════════════════════╝

Nhập vào chat:
  "How should we rollout this leadership system to all regions?"

KỲ VỌNG KẾT QUẢ:
═══════════════════════════════════════════════════════════════

[Backend Logs - Thấy debug logs]
  Stage discipline alert: user asked about 'rollout' 
  but we're in discovery. 
  Agent will redirect to required action: problem_statement

[Frontend - Chat UI]
  1. Supervisor chọn CHRO để trả lời (vì CHRO có coaching power)
  2. CHRO response trả về:
     "I see you're thinking about rollout, which shows strategic thinking.
      But we're still in discovery, and we need problem_statement first.
      Let me redirect: What is the #1 business problem Gucci Group is 
      solving with this leadership system?"
  
  3. KHÔNG thấy rollout plan hoặc execution timeline

[Metadata - Thấy ở dưới chat]
  - next_agent: "chro"
  - simulation_stage: "discovery" (vẫn ở discovery!)
  - required_next_actions: ["problem_statement"] (chưa complete)
  - director_notes: "⚠️ Stage discipline alert: user asked about 'rollout'..."
""")

# ============================================================
# TEST CASE 2: DISCOVERY STAGE - CORRECT ANSWER
# ============================================================

print("""
╔═══════════════════════════════════════════════════════════════╗
║ TEST CASE 2: USER TRẢ LỜI ĐÚNG TRONG DISCOVERY              ║
╚═══════════════════════════════════════════════════════════════╝

Nhập vào chat:
  "The business problem we're solving is: Gucci Group leaders lack 
   a shared mental model of what drives our brand. We need to ensure
   all executives worldwide operate from the same 4 core values."

KỲ VỌNG KẾT QUẢ:
═══════════════════════════════════════════════════════════════

[Backend Logs]
  ✓ Deliverable detected: problem_statement
  Completed deliverables: ['problem_statement']
  Stage progress: 100% (discovery complete!)

[Frontend - Chat UI]
  1. Supervisor detects problem_statement is complete
  2. Suggests NEXT STAGE: alignment
  3. Agent (could be any: CEO/CHRO/Regional) responds:
     "Perfect. That's the binding business problem.
      Now we need to map this to role families and our 4 pillars..."
  
  4. Stage transitions to ALIGNMENT (nếu auto-transition enabled)

[Metadata]
  - simulation_stage: "alignment" (LỜI!) hoặc vẫn "discovery" + hint
  - required_next_actions: ["scope_clarification", "role_family_prioritization", "4pillar_mapping"]
  - stage_progress: {"discovery": 100}
""")

# ============================================================
# TEST CASE 3: ALIGNMENT STAGE - ROLLOUT BLOCK (KHÁC KEYWORD)
# ============================================================

print("""
╔═══════════════════════════════════════════════════════════════╗
║ TEST CASE 3: USER HỎI ROLLOUT TRONG ALIGNMENT (KHÁC KEYWORD)║
╚═══════════════════════════════════════════════════════════════╝

Giả sử hệ thống đã advance sang ALIGNMENT stage.

Nhập vào chat:
  "What's the training plan we'll use for manager readiness?"

KỲ VỌNG KẾT QUẢ:
═══════════════════════════════════════════════════════════════

[Backend Logs]
  Stage discipline alert: user asked about 'training' 
  but we're in alignment. 
  Blocked keywords in alignment: ['train_the_trainer', 'manager_readiness', 
  'adoption_rate', 'phase_1_beta', 'regional_resistance', 'rollout']

[Frontend - Chat UI]
  CHRO responds:
    "I need to pump the brakes here, because we're still in alignment.
     We need to map out which role families are most critical first,
     then ground them in our 4 pillars. Once we have that clarity...
     training discussion will make way more sense. Let me ask: 
     Which 3-5 role families drive brand execution?"

[Metadata]
  - simulation_stage: "alignment" (vẫn ở alignment)
  - required_next_actions: (chưa complete - chỉ required role_family_prioritization)
""")

# ============================================================
# OBSERVATION POINTS
# ============================================================

print("""
╔═══════════════════════════════════════════════════════════════╗
║ ĐIỂM QUAN TRỌNG CẦN QUAN SÁT                                 ║
╚═══════════════════════════════════════════════════════════════╝

1. PERSONALITY (Cách phản ứng phụ thuộc vào persona):
   - CEO: "I need you to lock down something far more critical..."
          (Protective, veto language)
   - CHRO: "I need to pump the brakes here, because we're still in [stage]..."
           (Coaching, redirecting to stage discipline)
   - Regional: "That rollout plan sounds nice, but it won't work 
               if we skip discovery..."
              (Practical, adoption reality focus)

2. STAGE GATE ENFORCEMENT:
   - Redirect message là indication stage gate is working
   - KHÔNG nên thấy rollout plan detail khi ở discovery
   - Nên thấy "First, let's focus on: [required_action]"

3. DIRECTOR NOTES:
   - Kiểm tra ở metadata phía dưới chat
   - Phải thấy "Stage discipline alert" khi có skip attempt
   - Phải thấy "💡 First, let's focus on: ..." hint

4. REQUIRED NEXT ACTIONS:
   - Discovery: ["problem_statement"]
   - Alignment: ["scope_clarification", "role_family_prioritization", "4pillar_mapping"]
   - Execution: ["pilot_selection", "training_plan", "adoption_metrics"]
   - Kiểm tra có update sau khi complete deliverables

5. TOKEN STREAMING:
   - Response phải hiện từng token (nếu chọn cadence > Fast)
   - Phải thấy cursor (▌ hoặc | hoặc · tùy setting)
   - Response phải mất ~5-15s tùy độ dài (không instant)

6. BACKEND LOGS:
   - Mở Terminal Backend để xem DEBUG logs
   - Phải thấy:
     * "Stage discipline alert" khi có skip
     * "Deliverable detected" khi user trả lời đúng
     * "Agent start | name=chro emotion=..."
     * "Supervisor decision | reason=..."
""")

# ============================================================
# TROUBLESHOOTING
# ============================================================

print("""
╔═══════════════════════════════════════════════════════════════╗
║ TROUBLESHOOTING                                              ║
╚═══════════════════════════════════════════════════════════════╝

Nếu KHÔNG thấy stage discipline redirect:
1. Kiểm tra Ollama đang chạy: curl http://127.0.0.1:11434/api/tags
2. Kiểm tra Backend logs có "Stage discipline alert"?
3. Chạy python validate_stage_discipline.py để confirm implementation
4. Kiểm tra base_agent.py có "[STAGE CONTEXT FOR" inject không?

Nếu Response quá nhanh (không thấy typing):
1. Gradio setting: Chọn "Human" mode (0.06s cadence)
2. Hoặc "Slow" mode (0.10s cadence)
3. Kiểm tra backend logs có astream_events token stream?

Nếu Stage không transition sang ALIGNMENT:
1. Confirm problem_statement deliverable detected?
2. Kiểm trap stage_progress có 100%?
3. Kiểm tra supervisor_node() auto-transition logic

Nếu CHRO response generic (không coaching):
1. Kiểm tra CHRO persona definition có coaching language?
2. Kiểm tra base_agent.py STAGE GATE section loaded?
3. Kiểm tra graph.py inject stage context message?

Nếu Websocket disconnect:
1. Kiểm tra Backend port 8000 available?
2. Kiểm tra Gradio ws:// URL correct?
3. Kiểm tra CORS settings ở main.py?
4. Check: asyncio.shield() protection là active?
""")

# ============================================================
# EXPECTED FLOW DIAGRAM
# ============================================================

print(r"""
╔═══════════════════════════════════════════════════════════════╗
║ EXPECTED FLOW DIAGRAM                                        ║
╚═══════════════════════════════════════════════════════════════╝

[DISCOVERY STAGE]
     ↓
User: "How to rollout?"
     ↓
Supervisor._detect_stage_skip():
  ✓ Detects "rollout" in blocked keywords for discovery
  ✓ Returns: skip_detected=True, user_asked="rollout"
     ↓
Supervisor decides: Route to CHRO (để coaching)
     ↓
Graph._wrap_agent("chro"):
  ✓ Injects "[STAGE CONTEXT FOR CHRO] Current stage: discovery"
  ✓ Injects emotion context (default: collaborative)
  ✓ Injects peer context (CEO/Regional stances)
     ↓
CHRO Agent processes:
  1. Reads system prompt STAGE GATE section
  2. Sees "[STAGE CONTEXT] Current stage: discovery"
  3. Checks: "Is rollout question aligned with discovery?" → NO
  4. Reads redirect template
  5. Uses CHRO persona voice: "I need to pump the brakes..."
  6. Generates coaching question about problem_statement
     ↓
LLM generates response → Token stream via astream_events
     ↓
FastAPI websocket → chunk events (token-by-token)
     ↓
Gradio UI → renders with typing effect + cursor
     ↓
User sees coaching redirect, NOT rollout plan ✓
""")

print("""
╔═══════════════════════════════════════════════════════════════╗
║ READY TO TEST! 🚀                                            ║
╚═══════════════════════════════════════════════════════════════╝

Summary:
  ✓ 6-layer stage discipline implementation complete
  ✓ All components validated
  ✓ Ready for end-to-end UI testing

Next steps:
  1. Start Ollama, Backend, Gradio
  2. Open http://127.0.0.1:7860
  3. Test Case 1: Ask rollout in discovery → See coaching redirect
  4. Test Case 2: Answer problem statement → See stage transition
  5. Test Case 3: Ask training in alignment → See another redirect
  6. Monitor Backend logs for "Stage discipline alert" markers

Expected outcome:
  Stage discipline is ENFORCED - user cannot skip stages even if they try
  Personality is PRESENT - CHRO sounds like coach, not generic assistant
  Token streaming is ACTIVE - Responses render with typing effect
""")
