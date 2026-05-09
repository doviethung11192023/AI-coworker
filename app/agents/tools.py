from langchain.tools import tool
from typing import Optional
from app.memory.vector_store import query_documents


def _normalize_query(query) -> str:
    if isinstance(query, dict):
        value = query.get("value") or query.get("query") or query.get("text")
        if isinstance(value, str):
            return value
        if value is not None:
            return str(value)
    if isinstance(query, str):
        return query
    if query is None:
        return ""
    return str(query)

@tool
def retrieve_simulation_docs(query: str, module: Optional[int] = None) -> str:
    """Retrieve relevant Gucci simulation documents and context."""
    query_text = _normalize_query(query).strip()
    if not query_text:
        return "Missing query. Ask the user to clarify what to retrieve."

    results = query_documents(query_text, module=module, n_results=3)
    if not results:
        return "No indexed documents found yet. Ask the user to verify sources or add docs."

    lines = []
    for idx, (doc, meta) in enumerate(results, start=1):
        title = (meta or {}).get("title") or (meta or {}).get("source") or f"Doc {idx}"
        lines.append(f"{idx}. {title}: {doc}")
    return "\n".join(lines)

@tool
def get_module_objectives(module: int) -> str:
    """Get clear objectives for current module."""
    objectives = {
        1: "Define Group DNA and Competency Model",
        2: "Design 360° feedback + Coaching program",
        3: "Create rollout plan and measurement framework"
    }
    return objectives.get(module, "Unknown module")


@tool
def prompt_library(prompt_type: str, brand: Optional[str] = None) -> str:
    """Return draft prompt snippets (headlines or disclaimers)."""
    prompt_type = (prompt_type or "").lower().strip()
    brand_name = brand or "Gucci Group"

    if prompt_type in ["headline", "headlines"]:
        return (
            f"Draft headlines for {brand_name}:\n"
            "1) Leadership that honors each brand DNA\n"
            "2) One group, distinct identities, shared excellence\n"
            "3) Elevating talent without diluting heritage"
        )
    if prompt_type in ["disclaimer", "disclaimers"]:
        return (
            "Draft disclaimers:\n"
            "1) This is a draft for internal discussion only.\n"
            "2) Please validate assumptions and sources before use.\n"
            "3) Final decisions require leadership approval."
        )

    return "Unknown prompt_type. Use 'headline' or 'disclaimer'."


@tool
def kpi_calculator(
    baseline: float,
    target: float,
    timeframe_months: int,
    audience_size: Optional[int] = None,
) -> str:
    """Simple KPI calculator stub for rollout planning."""
    if timeframe_months <= 0:
        return "Invalid timeframe. timeframe_months must be > 0."

    delta = target - baseline
    pct_change = (delta / baseline * 100.0) if baseline else 0.0
    monthly_delta = delta / timeframe_months

    lines = [
        f"Baseline: {baseline}",
        f"Target: {target}",
        f"Delta: {delta}",
        f"Percent change: {pct_change:.2f}%",
        f"Monthly delta: {monthly_delta:.2f}",
    ]
    if audience_size:
        per_person = delta / audience_size if audience_size else 0.0
        lines.append(f"Delta per person: {per_person:.4f}")
    return "\n".join(lines)


@tool
def ab_simulator(variant_a_rate: float, variant_b_rate: float, sample_size: int) -> str:
    """Simple A/B simulator stub based on rate comparison."""
    if sample_size <= 0:
        return "Invalid sample_size."

    lift = variant_b_rate - variant_a_rate
    winner = "B" if lift > 0 else "A" if lift < 0 else "Tie"
    abs_lift = abs(lift)
    return (
        f"Winner: {winner}\n"
        f"Absolute lift: {abs_lift:.4f}\n"
        f"Sample size: {sample_size}"
    )


@tool
def export_portfolio_pack(plan: str, posts: str, exec_update: str) -> str:
    """One-click portfolio pack export stub."""
    return (
        "PORTFOLIO PACK (DRAFT)\n"
        "=== PLAN ===\n"
        f"{plan}\n\n"
        "=== POSTS ===\n"
        f"{posts}\n\n"
        "=== EXEC UPDATE ===\n"
        f"{exec_update}\n"
        "Note: Please verify sources and confirm before final use."
    )

tools = [
    retrieve_simulation_docs,
    get_module_objectives,
    prompt_library,
    kpi_calculator,
    ab_simulator,
    export_portfolio_pack,
]