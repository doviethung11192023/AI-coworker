import re


_DRAFT_PATTERNS = [
	r"\bdraft\b",
	r"draft-only",
	r"internal discussion",
]

_SOURCE_CONFIRM_PATTERNS = [
	r"confirm sources",
	r"verify sources",
	r"validate sources",
	r"check sources",
]

_WAGERING_PATTERNS = [
	r"\bguarantee\b",
	r"\bguaranteed\b",
	r"\bno risk\b",
	r"\bcertain win\b",
	r"\bbet\b",
	r"\bwager\b",
	r"\b100%\b",
	r"\bdefinitely\b",
]


def _matches_any(patterns, text: str) -> bool:
	return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def build_safety_flags(text: str) -> dict:
	"""Lightweight post-check for guardrail compliance."""
	if not isinstance(text, str):
		text = str(text)

	draft_language_present = _matches_any(_DRAFT_PATTERNS, text)
	source_confirmation_present = _matches_any(_SOURCE_CONFIRM_PATTERNS, text)
	wagering_language_detected = _matches_any(_WAGERING_PATTERNS, text)

	return {
		"draft_language_present": draft_language_present,
		"source_confirmation_present": source_confirmation_present,
		"wagering_language_detected": wagering_language_detected,
		"compliant": draft_language_present
		and source_confirmation_present
		and not wagering_language_detected,
	}
