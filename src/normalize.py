"""
Action string normalisation for consistent scorer matching.

Applied at both reference-build time (to focal_action) and at eval time
(to model responses) so that trivial formatting differences don't count
as mismatches.

Copied verbatim from v2 (domain-blind — no modifications needed).
"""

from __future__ import annotations

import re


def normalize_action(s: str) -> str:
    """
    Normalise an action string to a canonical lower-case form.

    Rules applied in order
    ----------------------
    1. Strip leading/trailing whitespace.
    2. Lowercase.
    3. Remove punctuation characters other than underscores and spaces.
    4. Collapse multiple consecutive spaces to one.
    5. Strip again.
    """
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-z0-9_ ]", "", s)
    s = re.sub(r" +", " ", s).strip()
    return s
