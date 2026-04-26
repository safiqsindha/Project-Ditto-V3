# Phase A — Decomposition Table

Layer 1 actionable gap (real_match_rate − shuffled_match_rate), primary config (T=0.0/seed=42).

| Cell | Pre-registered (original ref) | Trivial-coincidence filtered | Downweighted reference (Option B) |
|---|---|---|---|
| **chess_standard** | -0.1871 (n=1288) | -0.1828 (n=1258) | -0.0675 (n=1288) |
| **chess960** | -0.2312 (n=1250) | -0.2272 (n=1215) | -0.0464 (n=1250) |
| **checkers_american** | -0.1150 (n=1496) | -0.1121 (n=1436) | -0.0087 (n=1496) |
| **draughts_intl** | -0.1553 (n=1533) | -0.1589 (n=1460) | -0.0724 (n=1533) |

**Pre-committed success criterion**: chess_standard gap (col 3) ≥ +0.02 = SUCCESS
**Observed**: chess_standard col 3 gap = -0.0675
**Result**: FAILED

