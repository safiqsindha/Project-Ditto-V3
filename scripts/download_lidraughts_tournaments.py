"""
Download international draughts games from Lidraughts tournament exports.
Saves each tournament's games to a separate PDN file.
"""
import subprocess
import time
from pathlib import Path

OUTDIR = Path("data/draughts_intl/raw/lidraughts")
OUTDIR.mkdir(parents=True, exist_ok=True)

# Standard (international 10x10) tournament IDs from /api/tournament
TOURNAMENT_IDS = [
    "OyMkGyn0", "H8ZB9o6u", "cIiV3SOv", "1SrjOS7T", "nDOR8Bms",
    "22ULB64g", "4lJF5jVj", "w5qAlfzt", "CD7ENwMc", "6gdgwKzR",
    "lH1Jh0uq", "8pwm9PTF", "scaOsnX3", "bJyZx8KM", "wLuh9bkP",
    "8PClk66X", "BGuJHsEw", "F6vx5YbS", "pSiEMrJc", "bVwtXqNI",
    "MIzx95fC", "uPnabXyZ", "KjHFkgO9", "0am1Iqby", "2qTgFY6J",
    "Dz2wlLHv", "eNVJG0iz", "qNOZw675", "o3zqrydd", "YiFkHD7G",
    "QKFWQQJA",
]

total = 0
results = {}

for tid in TOURNAMENT_IDS:
    outfile = OUTDIR / f"{tid}.pdn"
    url = f"https://lidraughts.org/api/tournament/{tid}/games"

    # Use curl to download
    ret = subprocess.run(
        ["curl", "-s", url, "-H", "Accept: application/x-draughts-pdn", "-o", str(outfile)],
        capture_output=True
    )

    # Count games
    if outfile.exists():
        text = outfile.read_text(errors="replace")
        count = text.count("\n[Event ")
        if not text.startswith("[Event "):
            count_start = 1 if text.startswith("[Event ") else 0
        else:
            count_start = 1
        # simple line count
        count = sum(1 for line in text.split('\n') if line.startswith('[Event '))
    else:
        count = 0

    results[tid] = count
    total += count
    print(f"{tid}: {count} games  (running total: {total})")
    time.sleep(0.25)

print(f"\nTotal games downloaded: {total}")
print("Done!")
