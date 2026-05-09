from __future__ import annotations

import asyncio
import os
import json
import time
import uuid
from pathlib import Path
from typing import Any

import gradio as gr
import httpx
import websockets


API_BASE_URL = os.getenv("CO_WORKER_API_URL", "http://127.0.0.1:8000")
SIMULATION_ROOT = Path(__file__).resolve().parent / "simulations"


def _api_to_ws_base(api_base: str) -> str:
    if api_base.startswith("https://"):
        return "wss://" + api_base[len("https://"):]
    if api_base.startswith("http://"):
        return "ws://" + api_base[len("http://"):]
    return api_base


WS_BASE_URL = os.getenv("CO_WORKER_WS_URL", _api_to_ws_base(API_BASE_URL))


def _cursor_glyph(cursor_style: str) -> str:
    style = (cursor_style or "Block").lower()
    if style == "bar":
        return "|"
    if style == "dot":
        return "•"
    if style == "none":
        return ""
    return "▌"


def _typing_profile(cadence_mode: str) -> dict[str, float]:
    mode = (cadence_mode or "Balanced").lower()
    if mode == "fast":
        return {
            "flush_interval": 0.016,
            "minor_pause": 0.0,
            "major_pause": 0.0,
            "line_pause": 0.0,
        }
    if mode == "slow":
        return {
            "flush_interval": 0.09,
            "minor_pause": 0.05,
            "major_pause": 0.12,
            "line_pause": 0.16,
        }
    if mode == "human":
        return {
            "flush_interval": 0.045,
            "minor_pause": 0.03,
            "major_pause": 0.09,
            "line_pause": 0.12,
        }
    return {
        "flush_interval": 0.035,
        "minor_pause": 0.012,
        "major_pause": 0.03,
        "line_pause": 0.05,
    }


def _pause_for_tail(tail_text: str, profile: dict[str, float]) -> float:
    if not tail_text:
        return 0.0
    if tail_text.endswith("\n"):
        return profile["line_pause"]
    if tail_text.endswith((".", "?", "!")):
        return profile["major_pause"]
    if tail_text.endswith((",", ";", ":")):
        return profile["minor_pause"]
    return 0.0


def discover_simulations() -> list[str]:
    items = []
    print(f"Discovering simulations in {SIMULATION_ROOT}...")
    if SIMULATION_ROOT.exists():
        for config_path in sorted(SIMULATION_ROOT.glob("*/config.json")):
            items.append(config_path.parent.name)
    if "gucci-leadership-08" not in items:
        items.insert(0, "gucci-leadership-08")
    return items or ["gucci-leadership-08"]


def _format_stage_view(payload: dict[str, Any]) -> str:
    stage = payload.get("simulation_stage") or "discovery"
    stage_progress = payload.get("stage_progress") or {}
    completed = payload.get("completed_deliverables") or []
    next_actions = payload.get("required_next_actions") or []

    current_progress = stage_progress.get(stage)
    progress_text = f"{current_progress}%" if current_progress is not None else "n/a"

    completed_text = "\n".join([f"- {item}" for item in completed]) if completed else "- None yet"
    next_actions_text = "\n".join([f"- {item}" for item in next_actions]) if next_actions else "- None"

    # LOW: Add UI hint for stage progression
    hint_text = ""
    if next_actions and stage == "discovery":
        hint_text = (
            "\n\n💡 **Hint to progress:** "
            "Clearly articulate a specific business problem that needs solving. "
            "For example: 'High talent churn in Asia-Pacific regions' or 'Leadership pipeline gaps across luxury brands.' "
            "The framework is a solution, not the problem itself."
        )
    elif next_actions and stage == "alignment":
        hint_text = (
            "\n\n💡 **Hint to progress:** "
            "Work with the team to align on how this solution addresses the problem. "
            "Discuss stakeholder concerns and finalize the approach before planning execution."
        )

    return (
        f"### Stage View\n"
        f"- Current stage: **{stage}**\n"
        f"- Stage progress: **{progress_text}**\n\n"
        f"**Completed deliverables**\n{completed_text}\n\n"
        f"**Required next actions**\n{next_actions_text}{hint_text}"
    )


def _format_diagnostics(payload: dict[str, Any]) -> str:
    notes = payload.get("director_notes") or "(none)"
    co_worker = payload.get("co_worker") or "Unknown"
    next_agent = payload.get("next_suggested_agent") or "end"
    return (
        f"### Diagnostics\n"
        f"- Co-worker: **{co_worker}**\n"
        f"- Next suggested agent: **{next_agent}**\n\n"
        f"**Director notes**\n{notes}"
    )


def _format_safety_flags(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("safety_flags") or {}


def _call_chat_api(
    message: str,
    simulation_id: str,
    enable_ceo: bool,
    enable_chro: bool,
    enable_regional: bool,
    thread_id: str,
) -> dict[str, Any]:
    payload = {
        "message": message,
        "simulation_id": simulation_id,
        "thread_id": thread_id,
        "current_module": 1,
        "model_type": "local",
        "enable_ceo": enable_ceo,
        "enable_chro": enable_chro,
        "enable_regional": enable_regional,
    }

    response = httpx.post(f"{API_BASE_URL}/chat", json=payload, timeout=120.0)
    response.raise_for_status()
    return response.json()


def send_message(
    message: str,
    history: list[dict[str, str]],
    simulation_id: str,
    enable_ceo: bool,
    enable_chro: bool,
    enable_regional: bool,
    thread_id: str | None,
):
    message = (message or "").strip()
    if not message:
        return history, thread_id or str(uuid.uuid4()), "", {}, _format_stage_view({}), _format_diagnostics({})

    active_thread_id = thread_id or str(uuid.uuid4())
    user_entry = {"role": "user", "content": message}
    try:
        payload = _call_chat_api(
            message=message,
            simulation_id=simulation_id,
            enable_ceo=enable_ceo,
            enable_chro=enable_chro,
            enable_regional=enable_regional,
            thread_id=active_thread_id,
        )

        assistant_text = payload.get("response", "")
        updated_history = history + [user_entry, {"role": "assistant", "content": assistant_text}]
        return (
            updated_history,
            payload.get("thread_id", active_thread_id),
            payload.get("director_notes") or "",
            _format_safety_flags(payload),
            _format_stage_view(payload),
            _format_diagnostics(payload),
        )
    except Exception as exc:
        error_text = f"Error calling backend: {exc}"
        updated_history = history + [user_entry, {"role": "assistant", "content": error_text}]
        return (
            updated_history,
            active_thread_id,
            error_text,
            {},
            _format_stage_view({}),
            _format_diagnostics({}),
        )


def _build_ui_payload(
    history: list[dict[str, str]],
    thread_id: str,
    notes: str,
    flags: dict[str, Any],
    stage_md: str,
    diagnostics_md: str,
):
    return history, history, thread_id, "", notes, flags, stage_md, diagnostics_md


async def stream_message(
    message: str,
    history: list[dict[str, str]],
    simulation_id: str,
    enable_ceo: bool,
    enable_chro: bool,
    enable_regional: bool,
    thread_id: str | None,
    cadence_mode: str,
    cursor_style: str,
):
    message = (message or "").strip()
    if not message:
        yield _build_ui_payload(
            history=history,
            thread_id=thread_id or str(uuid.uuid4()),
            notes="",
            flags={},
            stage_md=_format_stage_view({}),
            diagnostics_md=_format_diagnostics({}),
        )
        return

    active_thread_id = thread_id or str(uuid.uuid4())
    user_entry = {"role": "user", "content": message}
    updated_history = history + [user_entry, {"role": "assistant", "content": ""}]

    notes = ""
    flags: dict[str, Any] = {}
    stage_payload: dict[str, Any] = {}
    diagnostics_payload: dict[str, Any] = {}
    assistant_text = ""
    pending = ""
    profile = _typing_profile(cadence_mode)
    cursor = _cursor_glyph(cursor_style)
    last_flush = 0.0
    flush_interval = profile["flush_interval"]

    yield _build_ui_payload(
        history=updated_history,
        thread_id=active_thread_id,
        notes=notes,
        flags=flags,
        stage_md=_format_stage_view(stage_payload),
        diagnostics_md=_format_diagnostics(diagnostics_payload),
    )

    payload = {
        "message": message,
        "simulation_id": simulation_id,
        "thread_id": active_thread_id,
        "current_module": 1,
        "model_type": "local",
        "enable_ceo": enable_ceo,
        "enable_chro": enable_chro,
        "enable_regional": enable_regional,
    }

    try:
        async with websockets.connect(f"{WS_BASE_URL}/ws/chat") as ws:
            await ws.send(json.dumps(payload))

            while True:
                raw_event = await ws.recv()
                event = json.loads(raw_event)
                event_type = event.get("type")

                if event_type == "started":
                    active_thread_id = event.get("thread_id") or active_thread_id
                    continue

                if event_type == "chunk":
                    pending += event.get("content") or ""
                    now = time.monotonic()
                    if pending and (now - last_flush >= flush_interval or pending.endswith(("\n", ".", "?", "!", ":", ";"))):
                        assistant_text += pending
                        pending = ""
                        last_flush = now
                        updated_history[-1]["content"] = assistant_text + cursor
                        yield _build_ui_payload(
                            history=updated_history,
                            thread_id=active_thread_id,
                            notes=notes,
                            flags=flags,
                            stage_md=_format_stage_view(stage_payload),
                            diagnostics_md=_format_diagnostics(diagnostics_payload),
                        )
                        pause = _pause_for_tail(assistant_text, profile)
                        if pause > 0:
                            await asyncio.sleep(pause)
                    continue

                if event_type == "meta":
                    notes = event.get("director_notes") or ""
                    flags = _format_safety_flags(event)
                    stage_payload = {
                        "simulation_stage": event.get("simulation_stage"),
                        "stage_progress": event.get("stage_progress"),
                        "completed_deliverables": event.get("completed_deliverables"),
                        "required_next_actions": event.get("required_next_actions"),
                    }
                    diagnostics_payload = {
                        "director_notes": notes,
                        "co_worker": event.get("co_worker"),
                        "next_suggested_agent": event.get("next_suggested_agent"),
                    }
                    continue

                if event_type == "done":
                    done_text = event.get("response") or ""
                    assistant_text = done_text or (assistant_text + pending)
                    pending = ""
                    updated_history[-1]["content"] = assistant_text
                    yield _build_ui_payload(
                        history=updated_history,
                        thread_id=event.get("thread_id") or active_thread_id,
                        notes=notes,
                        flags=flags,
                        stage_md=_format_stage_view(stage_payload),
                        diagnostics_md=_format_diagnostics(diagnostics_payload),
                    )
                    break

                if event_type == "error":
                    error_text = event.get("detail") or "Backend websocket error."
                    updated_history[-1]["content"] = error_text
                    yield _build_ui_payload(
                        history=updated_history,
                        thread_id=active_thread_id,
                        notes=error_text,
                        flags={},
                        stage_md=_format_stage_view({}),
                        diagnostics_md=_format_diagnostics({"director_notes": error_text}),
                    )
                    break
    except Exception as exc:
        error_text = f"Error calling backend stream: {exc}"
        updated_history[-1]["content"] = error_text
        yield _build_ui_payload(
            history=updated_history,
            thread_id=active_thread_id,
            notes=error_text,
            flags={},
            stage_md=_format_stage_view({}),
            diagnostics_md=_format_diagnostics({"director_notes": error_text}),
        )


def new_session():
    return [], [], str(uuid.uuid4()), "", {}, _format_stage_view({}), _format_diagnostics({})


with gr.Blocks(title="Edtronaut AI Co-Worker Demo") as demo:
    gr.Markdown("# Edtronaut AI Co-Worker Demo\nChat demo running against the FastAPI backend.")

    thread_state = gr.State(str(uuid.uuid4()))
    chat_state = gr.State([])

    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="Conversation", height=560)
            message_box = gr.Textbox(
                label="Message",
                placeholder="Type your message here and press Enter...",
                lines=3,
            )
            with gr.Row():
                send_btn = gr.Button("Send", variant="primary")
                clear_btn = gr.Button("New Session")

        with gr.Column(scale=2):
            simulation_id = gr.Dropdown(
                choices=discover_simulations(),
                value="gucci-leadership-08",
                label="simulation_id",
                allow_custom_value=True,
            )
            enable_ceo = gr.Checkbox(value=True, label="Enable CEO")
            enable_chro = gr.Checkbox(value=True, label="Enable CHRO")
            enable_regional = gr.Checkbox(value=True, label="Enable Regional")
            cadence_mode = gr.Dropdown(
                choices=["Fast", "Balanced", "Human", "Slow"],
                value="Human",
                label="Typing cadence",
            )
            cursor_style = gr.Dropdown(
                choices=["Block", "Bar", "Dot", "None"],
                value="Block",
                label="Cursor style",
            )
            director_notes = gr.Textbox(label="director_notes", lines=6)
            safety_flags = gr.JSON(label="safety_flags")
            stage_view = gr.Markdown()
            diagnostics = gr.Markdown()

    send_btn.click(
        fn=stream_message,
        inputs=[message_box, chat_state, simulation_id, enable_ceo, enable_chro, enable_regional, thread_state, cadence_mode, cursor_style],
        outputs=[chatbot, chat_state, thread_state, message_box, director_notes, safety_flags, stage_view, diagnostics],
    )
    message_box.submit(
        fn=stream_message,
        inputs=[message_box, chat_state, simulation_id, enable_ceo, enable_chro, enable_regional, thread_state, cadence_mode, cursor_style],
        outputs=[chatbot, chat_state, thread_state, message_box, director_notes, safety_flags, stage_view, diagnostics],
    )
    clear_btn.click(
        fn=new_session,
        inputs=[],
        outputs=[chatbot, chat_state, thread_state, director_notes, safety_flags, stage_view, diagnostics],
    )


if __name__ == "__main__":
    demo.queue()
    print("Gradio UI: http://127.0.0.1:7860")
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False, theme=gr.themes.Soft())
