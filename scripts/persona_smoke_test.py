from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.agents.ceo_agent import create_ceo_agent
from app.agents.chro_agent import create_chro_agent
from app.agents.regional_agent import create_regional_agent


TEST_CASES = [
    (
        "CEO",
        create_ceo_agent(),
        "We cannot standardize leadership so aggressively that brands lose identity. What is the minimum common framework you would allow without weakening Gucci Group prestige?",
    ),
    (
        "CHRO",
        create_chro_agent(),
        "How would you map the leadership system first to Vision, Entrepreneurship, Passion, and Trust, and then calibrate behaviors by role family?",
    ),
    (
        "Regional",
        create_regional_agent(),
        "What local rollout risk would most likely block adoption of this framework in Europe, and what is one practical mitigation you would push for?",
    ),
]


def _extract_content(result) -> str:
    messages = result.get("messages") if isinstance(result, dict) else None
    if not messages:
        return "<no response>"
    last_message = messages[-1]
    return getattr(last_message, "content", str(last_message))


def main() -> None:
    for label, agent, prompt in TEST_CASES:
        print("=" * 80)
        print(f"{label} TEST PROMPT:")
        print(prompt)
        print("-" * 80)
        try:
            result = agent.invoke({"messages": [("user", prompt)]})
            print(f"{label} OUTPUT:")
            print(_extract_content(result))
        except Exception as exc:
            print(f"{label} ERROR: {exc}")
        print()


if __name__ == "__main__":
    main()