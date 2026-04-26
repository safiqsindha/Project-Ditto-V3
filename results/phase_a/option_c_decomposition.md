# Phase A — Option C decomposition table

Layer 1 actionable gap (real_match_rate − shuffled_match_rate), primary config.

| Cell | col1: pre-registered | col2: trv-filtered | col3: Option B | col4: Option C | col4 same-level |
|---|---|---|---|---|---|
| **chess_standard** | -0.1871 | -0.1828 | -0.0675 | -0.1514 | -0.0802 |
| **chess960** | -0.2312 | -0.2272 | -0.0464 | -0.0904 | -0.0950 |
| **checkers_american** | -0.1150 | -0.1121 | -0.0087 | -0.0842 | -0.0264 |
| **draughts_intl** | -0.1553 | -0.1589 | -0.0724 | -0.1220 | -0.0644 |

**Pre-committed Phase A criterion**: chess_standard col3 (Option B) ≥ +0.02 → SUCCESS
**Phase A result**: col3 = -0.0675 → FAILED (unchanged)
**Option C result is informational** — does NOT retroactively change Phase A.
