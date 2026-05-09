from typing import Iterable, Set


DEFAULT_TOOLS: Set[str] = {
    "retrieve_simulation_docs",
    "get_module_objectives",
    "prompt_library",
    "kpi_calculator",
    "ab_simulator",
    "export_portfolio_pack",
}

TOOLS_BY_SIMULATION = {
    "gucci-leadership-08": {
        "retrieve_simulation_docs",
        "get_module_objectives",
        "prompt_library",
        "kpi_calculator",
        "ab_simulator",
        "export_portfolio_pack",
    }
}


def get_allowed_tools(simulation_id: str | None) -> Set[str]:
    if simulation_id and simulation_id in TOOLS_BY_SIMULATION:
        return set(TOOLS_BY_SIMULATION[simulation_id])
    return set(DEFAULT_TOOLS)


def tool_is_allowed(tool_name: str, allowed: Iterable[str]) -> bool:
    return tool_name in set(allowed)
