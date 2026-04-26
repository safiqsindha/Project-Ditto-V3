"""
Renderer: converts abstract Constraint objects into human-readable,
domain-abstracted English.

NO game-domain vocabulary is permitted in any output string. The post-rendering
leakage check is invoked automatically by render_chain() and enforces both the
v2 programming-vocabulary list AND the chess+checkers glossary maintained in
src/leakage_glossary.py (single source of truth, see SPEC.md §Renderer leakage
vocabulary).

Two-tier check (Session 6 hardening):
  - check_leakage(rendered)            — HARD: word-boundary regex; raises in
                                         render_chain() if any match.
  - check_leakage_substring(rendered)  — SOFT: substring scan with explicit
                                         exemptions; warns on architecturally-
                                         suspect strings like "material_white"
                                         that the regex would not catch (since
                                         Python `\\b` treats `_` as a word
                                         char). Used during development and in
                                         pilot/full-generation scripts.

The leakage check is enforced in code; callers cannot bypass it.

Adapted from v2 renderer.py: extended leakage vocabulary for chess + checkers.
"""

from __future__ import annotations

import re
from typing import Iterable

from src.translation import (
    Constraint,
    CoordinationDependency,
    InformationState,
    OptimizationCriterion,
    ResourceBudget,
    SubGoalTransition,
    ToolAvailability,
)
from src.leakage_glossary import (
    HARD_CHECK_VOCAB as _GLOSSARY_HARD_VOCAB,
    SOFT_CHECK_VOCAB as _GLOSSARY_SOFT_VOCAB,
    SOFT_CHECK_EXEMPTIONS as _GLOSSARY_EXEMPTIONS,
)


# ---------------------------------------------------------------------------
# Per-type renderers (identical rendering logic to v2 — domain-blind)
# ---------------------------------------------------------------------------

def _render_resource_budget(c: ResourceBudget) -> str:
    pct = f"{c.amount * 100:.1f}%"
    parts = [f"ResourceBudget: {c.resource} at {pct}"]
    if c.decay != "none":
        parts.append(f"(decay={c.decay})")
    if c.recover_in is not None:
        parts.append(f"(recover_in={c.recover_in} steps)")
    return " ".join(parts)


def _render_tool_availability(c: ToolAvailability) -> str:
    state_str = c.state.upper()
    if c.state == "unavailable" and c.recover_in is None:
        return f"ToolAvailability: {c.tool} is now {state_str} (permanent)"
    elif c.state == "unavailable":
        return f"ToolAvailability: {c.tool} is now {state_str} (recover_in={c.recover_in})"
    else:
        return f"ToolAvailability: {c.tool} is now {state_str}"


def _render_subgoal_transition(c: SubGoalTransition) -> str:
    return (
        f"SubGoalTransition: phase shifted from '{c.from_phase}' to '{c.to_phase}'"
        f" (trigger={c.trigger})"
    )


def _render_information_state(c: InformationState) -> str:
    added = ", ".join(c.observable_added) if c.observable_added else "(empty)"
    removed = ", ".join(c.observable_removed) if c.observable_removed else "(empty)"
    return (
        f"InformationState: added=[{added}] removed=[{removed}]"
        f" uncertainty={c.uncertainty:.2f}"
    )


def _render_coordination_dependency(c: CoordinationDependency) -> str:
    return (
        f"CoordinationDependency: {c.role} depends on {c.dependency}"
        f" -> expected_action={c.expected_action}"
    )


def _render_optimization_criterion(c: OptimizationCriterion) -> str:
    return (
        f"OptimizationCriterion: objective={c.objective}"
        f" weight_shift={c.weight_shift}"
    )


_RENDERERS = {
    ResourceBudget:         _render_resource_budget,
    ToolAvailability:       _render_tool_availability,
    SubGoalTransition:      _render_subgoal_transition,
    InformationState:       _render_information_state,
    CoordinationDependency: _render_coordination_dependency,
    OptimizationCriterion:  _render_optimization_criterion,
}


def render_constraint(c: Constraint) -> str:
    """Render a single constraint as a one-line abstract English description."""
    renderer = _RENDERERS.get(type(c))
    if renderer is None:
        return f"UnknownConstraint: {c!r}"
    return renderer(c)


# ---------------------------------------------------------------------------
# Chain renderer
# ---------------------------------------------------------------------------

def render_chain(constraints: list[Constraint], perspective: str = "agent") -> str:
    """
    Render a list of constraints as numbered steps.

    Raises ValueError if game-domain vocabulary is detected in the output.

    Parameters
    ----------
    constraints : ordered list of Constraint objects
    perspective : trajectory perspective label (included in header)

    Returns
    -------
    Multi-line string, one step per constraint.
    """
    if not constraints:
        return f"# Constraint chain (perspective={perspective})\n(no constraints)\n"

    lines: list[str] = [f"# Constraint chain (perspective={perspective})"]
    step = 1
    for c in constraints:
        turn = getattr(c, "timestamp", 0)
        body = render_constraint(c)
        lines.append(f"Step {step} (step={turn}):")
        lines.append(f"  {body}")
        step += 1

    rendered = "\n".join(lines) + "\n"

    leaked = check_leakage(rendered)
    if leaked:
        raise ValueError(
            f"Game-domain vocabulary detected in rendered chain: {leaked}. "
            "Check translation.py for domain leakage."
        )

    return rendered


# Cell name → abstract perspective label (prevents game-domain leakage in chain header)
_CELL_TO_PERSPECTIVE: dict[str, str] = {
    "chess_standard":    "sequential_process_A",
    "chess960":          "sequential_process_B",
    "checkers_american": "sequential_process_C",
    "draughts_intl":     "sequential_process_D",
}


def render_trajectory_chain(constraints: list[Constraint], source: str = "chess_standard") -> str:
    """Convenience wrapper for render_chain using an abstract perspective label.

    Cell names like 'chess960' are mapped to abstract labels (sequential_process_*)
    before being written into the chain header, preventing leakage vocabulary from
    appearing in rendered output.
    """
    perspective = _CELL_TO_PERSPECTIVE.get(source, "sequential_process_A")
    return render_chain(constraints, perspective=perspective)


# ---------------------------------------------------------------------------
# Leakage vocabulary
# ---------------------------------------------------------------------------

# v2 programming vocabulary (inherited — unchanged)
_PROGRAMMING_VOCAB: frozenset[str] = frozenset({
    "def", "class", "import", "return", "async", "await", "yield", "lambda",
    "raise", "except", "finally", "with", "pass", "global", "nonlocal",
    "elif", "else", "while", "assert", "del", "exec", "print",
    "stdin", "stdout", "stderr", "traceback",
    "TypeError", "ValueError", "KeyError", "AttributeError", "ImportError",
    "RuntimeError", "IndexError", "NameError", "OSError", "FileNotFoundError",
    "PermissionError", "TimeoutError", "StopIteration", "AssertionError",
    "NotImplementedError", "RecursionError", "MemoryError", "OverflowError",
    "ZeroDivisionError", "UnicodeDecodeError", "UnicodeEncodeError",
    "ConnectionError", "BrokenPipeError", "FileExistsError", "IsADirectoryError",
    "ModuleNotFoundError", "SyntaxError", "IndentationError", "SystemExit",
    "Exception", "BaseException",
    "django", "flask", "fastapi", "numpy", "pandas", "scipy", "sklearn",
    "torch", "tensorflow", "keras", "requests", "httpx", "aiohttp",
    "pydantic", "sqlalchemy", "celery", "redis", "kafka", "boto3",
    "pytest", "unittest", "mock", "click", "typer", "argparse",
    "asyncio", "threading", "multiprocessing", "subprocess",
    "grep", "find", "sed", "awk", "curl", "wget", "ssh", "git",
    "make", "cmake", "pip", "conda", "npm", "yarn", "cargo",
    "docker", "kubectl", "terraform",
    "function", "method", "module", "package", "library", "framework",
    "variable", "parameter", "argument", "constant", "attribute", "property",
    "interface", "protocol", "decorator", "iterator", "generator", "coroutine",
    "database", "schema", "migration", "query", "transaction",
    "endpoint", "route", "middleware", "handler", "controller", "serializer",
    "compiler", "interpreter", "runtime", "bytecode",
    "thread", "process", "daemon", "signal", "socket",
    "api", "sdk", "cli", "ide",
    "github", "gitlab", "commit", "branch", "merge", "rebase",
    "build", "deploy", "release",
    "dotenv", "secret",
    "python", "javascript", "typescript", "java", "cpp", "ruby",
    "dockerfile", "makefile", "requirements",
})

# Game-domain vocabulary now lives in src/leakage_glossary.py (single source of truth).
# Combined hard-check vocabulary = v2 programming vocab + glossary high+medium severity.
_DEFAULT_LEAKAGE_VOCAB: frozenset[str] = (
    _PROGRAMMING_VOCAB | _GLOSSARY_HARD_VOCAB
)


# Pre-compile a single alternation regex for the hard check (~6× faster than
# iterating per-term, important when scanning thousands of chains).
def _compile_alternation(vocab: frozenset[str]) -> re.Pattern:
    # Sort longest-first so multi-word terms like "en passant" match before "en"
    sorted_terms = sorted(vocab, key=len, reverse=True)
    pattern = r"\b(?:" + "|".join(re.escape(t) for t in sorted_terms) + r")\b"
    return re.compile(pattern, flags=re.IGNORECASE)


_HARD_CHECK_REGEX: re.Pattern = _compile_alternation(_DEFAULT_LEAKAGE_VOCAB)

# Response-only vocab: drops the v2 programming vocabulary because many Python
# keywords overlap with common English words ("with", "pass", "else", "while",
# "print", "class", "return", "raise", "yield", "set", "list", "function",
# "method", "find", ...). Those produce false positives on free-form model
# responses (English natural language), confounding the experiment-relevant
# game-domain leakage signal.
#
# The chain-content leakage check (`check_leakage`) keeps the full vocab —
# chains are programmatically rendered, so any Python keyword in chain output
# would be a real bug. Different threat models, different vocabs.
_RESPONSE_LEAKAGE_REGEX: re.Pattern = _compile_alternation(_GLOSSARY_HARD_VOCAB)


def check_leakage(
    rendered: str,
    vocab: set[str] | frozenset[str] | None = None,
) -> list[str]:
    """
    Hard leakage check: return any game-domain or programming-domain vocabulary
    found in the rendered output as a whole-word, case-insensitive match.

    Parameters
    ----------
    rendered : string produced by render_chain()
    vocab    : optional override; defaults to combined programming + glossary
               high+medium severity vocabulary. Pass empty set in unit tests
               that explicitly test clean output.

    Returns
    -------
    List of leaking terms (empty list means no leakage).

    Notes
    -----
    Python `\\b` treats `_` as a word character. As a result, this check does
    NOT catch terms embedded in compound labels like "material_white" — that
    leakage class is caught by check_leakage_substring() instead.
    """
    if vocab is None:
        # Use the pre-compiled regex for the default vocab (fast path)
        return sorted(set(m.lower() for m in _HARD_CHECK_REGEX.findall(rendered)))

    # Custom vocab: per-term iteration (used in tests)
    leaked: list[str] = []
    for term in vocab:
        pattern = r"\b" + re.escape(term) + r"\b"
        if re.search(pattern, rendered, flags=re.IGNORECASE):
            leaked.append(term)
    return leaked


def check_response_leakage(response: str) -> list[str]:
    """
    Game-domain-only leakage scan, intended for free-form model responses.

    Differs from `check_leakage()` in vocabulary, not algorithm: same
    word-boundary regex, but uses the glossary's HARD_CHECK_VOCAB (game
    domain only) and skips the v2 programming vocabulary that produces
    false positives on English text.

    Use case: scanning Anthropic Messages API responses for real
    chess/checkers vocabulary leakage from the model. Free-form English
    naturally contains words like "with", "else", "while", "print" that
    are Python keywords in `_PROGRAMMING_VOCAB` — those false positives
    would dominate any real signal at Phase 1 scale (57k+ responses).

    For chain CONTENT leakage (rendered constraint chains, where Python
    keywords would indicate a real rendering bug) keep using `check_leakage()`.

    Returns sorted list of game-domain terms found, lowercase.
    """
    return sorted(set(m.lower() for m in _RESPONSE_LEAKAGE_REGEX.findall(response)))


def check_leakage_substring(
    rendered: str,
    exempt_compounds: frozenset[str] | None = None,
) -> list[str]:
    """
    Soft leakage check: relaxed-boundary scan that treats `_` as a NON-word char.

    Catches glossary terms embedded inside compound labels like "material_white"
    or "king_safety" that the hard check (\\b...\\b) misses because Python
    treats `_` as a word character. Crucially, it does NOT pure-substring match
    — that produced false positives on common English words ("permanent"
    contains "man"; "defend" contains "fen").

    Boundary rule: glossary term must be preceded and followed by either:
      - start/end of string, OR
      - a non-alphanumeric character (which now includes `_`).

    Examples (term="white"):
      - "material_white"  → MATCH  (preceded by `_`, end of string)
      - " white piece"    → MATCH  (spaces around)
      - "whitespace"      → no match (followed by `s` letter)

    Examples (term="man"):
      - "permanent"       → no match (preceded by `r` letter)
      - "[man]"           → MATCH  (brackets are non-alnum)

    Examples (term="fen"):
      - "defend"          → no match (preceded by `e`, followed by `d` letter)
      - "FEN string"      → MATCH

    Parameters
    ----------
    rendered         : string produced by render_chain()
    exempt_compounds : approved abstract compound labels (e.g. "phase_opening")
                       that contain a glossary term but are explicitly allowed.
                       Defaults to SOFT_CHECK_EXEMPTIONS from leakage_glossary.

    Returns
    -------
    Sorted list of leaking terms found (de-duplicated, lowercase).

    Use this in pilot/full-generation scripts as a development guardrail. It is
    NOT invoked automatically by render_chain() because borderline cases require
    judgment; the hard check is the enforced gate.
    """
    if exempt_compounds is None:
        exempt_compounds = _GLOSSARY_EXEMPTIONS

    # Mask exempt compounds with a non-alphanumeric placeholder so their
    # embedded glossary terms aren't flagged.
    masked = rendered
    for compound in sorted(exempt_compounds, key=len, reverse=True):
        masked = re.sub(re.escape(compound), "<<EXEMPT>>", masked, flags=re.IGNORECASE)

    leaked: set[str] = set()
    for term in _GLOSSARY_SOFT_VOCAB:
        # Relaxed boundary: not preceded/followed by [a-zA-Z0-9]; underscore is OK.
        pattern = (
            r"(?<![a-zA-Z0-9])"
            + re.escape(term)
            + r"(?![a-zA-Z0-9])"
        )
        if re.search(pattern, masked, flags=re.IGNORECASE):
            leaked.add(term.lower())
    return sorted(leaked)


# Backwards-compatible alias used by scorer and tests
check_programming_leakage = check_leakage
