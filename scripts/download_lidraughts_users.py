"""
Download international draughts games from Lidraughts user accounts.
Uses the /api/games/user/{username}?variant=standard endpoint.
"""
import subprocess
import time
import re
from pathlib import Path

OUTDIR = Path("data/draughts_intl/raw/lidraughts_users")
OUTDIR.mkdir(parents=True, exist_ok=True)

# Load player list from tournament games
USERS_FILE = Path("/tmp/lidraughts_users.txt")
if USERS_FILE.exists():
    users = [u.strip() for u in USERS_FILE.read_text().split('\n') if u.strip()]
else:
    # Fallback list of known international draughts players
    users = [
        "roepstoep", "roel_boomstra", "antiprism", "Roel_v_Herp", "WijnandsJ",
        "DamDB", "Woef69", "special", "Cacadosse",
    ]

MAX_PER_USER = 500
total = 0

for username in users:
    outfile = OUTDIR / f"{username}.pdn"
    if outfile.exists() and outfile.stat().st_size > 100:
        count = sum(1 for line in outfile.read_text(errors='replace').split('\n')
                    if line.startswith('[Event '))
        if count > 0:
            total += count
            print(f"{username}: {count} games (cached)  running total: {total}")
            continue

    url = f"https://lidraughts.org/api/games/user/{username}?max={MAX_PER_USER}&variant=standard"
    ret = subprocess.run(
        ["curl", "-s", url, "-H", "Accept: application/x-draughts-pdn", "-o", str(outfile)],
        capture_output=True,
        timeout=30
    )

    if outfile.exists() and outfile.stat().st_size > 0:
        text = outfile.read_text(errors='replace')
        count = sum(1 for line in text.split('\n') if line.startswith('[Event '))
    else:
        count = 0

    total += count
    if count > 0:
        print(f"{username}: {count} games  running total: {total}")
    time.sleep(0.2)

print(f"\nTotal games from users: {total}")
print("Done!")
