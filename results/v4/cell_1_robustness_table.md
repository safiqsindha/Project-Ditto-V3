# v4 Cell 1 — statistical methodology robustness table

Layer 1 actionable gap (real_match_rate − shuffled_match_rate), primary config (T=0.0/seed=42).

Methodology 3 is pulled from `results/phase1_v31_scored_full.json` (not recomputed).
Methodologies 1, 2, 4 are computed in this analysis.

| Cell | Methodology | n | gap | p_raw | p_bonferroni | CI 95% | tier |
|---|---|---|---|---|---|---|---|
| chess_standard | 1) two-sample proportion (v1) | 1200 | -0.0431 | <0.001 | n/a | [-0.0628, -0.0234] | reversed |
| chess_standard | 2) paired McNemar no filter (v2) | 3600 | -0.0431 | <0.001 | <0.001 | [-0.0565, -0.0297] | reversed |
| chess_standard | 3) paired McNemar actionable+Bonf (v3 pre-reg) | 1288 | -0.1871 | <0.001 | <0.001 | [-0.2138, -0.1604] | reversed |
| chess_standard | 4) paired McNemar actionable no Bonf | 1288 | -0.1871 | <0.001 | n/a | [-0.2138, -0.1604] | reversed |
| chess960 | 1) two-sample proportion (v1) | 1200 | -0.0383 | <0.001 | n/a | [-0.0569, -0.0198] | reversed |
| chess960 | 2) paired McNemar no filter (v2) | 3600 | -0.0383 | <0.001 | <0.001 | [-0.0510, -0.0256] | reversed |
| chess960 | 3) paired McNemar actionable+Bonf (v3 pre-reg) | 1250 | -0.2312 | <0.001 | <0.001 | [-0.2589, -0.2035] | reversed |
| chess960 | 4) paired McNemar actionable no Bonf | 1250 | -0.2312 | <0.001 | n/a | [-0.2589, -0.2035] | reversed |
| checkers_american | 1) two-sample proportion (v1) | 1200 | +0.0394 | 0.0019 | n/a | [+0.0136, +0.0653] | weak_mixed |
| checkers_american | 2) paired McNemar no filter (v2) | 3600 | +0.0394 | <0.001 | <0.001 | [+0.0217, +0.0571] | weak_mixed |
| checkers_american | 3) paired McNemar actionable+Bonf (v3 pre-reg) | 1496 | -0.1150 | <0.001 | <0.001 | [-0.1419, -0.0881] | reversed |
| checkers_american | 4) paired McNemar actionable no Bonf | 1496 | -0.1150 | <0.001 | n/a | [-0.1419, -0.0881] | reversed |
| draughts_intl | 1) two-sample proportion (v1) | 1200 | -0.0164 | 0.1446 | n/a | [-0.0378, +0.0050] | reversed |
| draughts_intl | 2) paired McNemar no filter (v2) | 3600 | -0.0164 | 0.0341 | 0.1364 | [-0.0313, -0.0015] | reversed |
| draughts_intl | 3) paired McNemar actionable+Bonf (v3 pre-reg) | 1533 | -0.1553 | <0.001 | <0.001 | [-0.1790, -0.1316] | reversed |
| draughts_intl | 4) paired McNemar actionable no Bonf | 1533 | -0.1553 | <0.001 | n/a | [-0.1790, -0.1316] | reversed |
