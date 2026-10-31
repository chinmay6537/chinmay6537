#!/usr/bin/env python3
"""Swaps GitHub's language colours in a top-langs card for the profile palette.

  python scripts/tint_langs.py assets/honor-langs.svg
"""
import re
import sys
from pathlib import Path

RAMP = ["#B3261E", "#E8E2D4", "#C9A86A", "#8C857A", "#2A2724"]

path = Path(sys.argv[1])
svg = path.read_text(encoding="utf-8")
# Legend dots come in rank order, and the donut's segments repeat the same colours.
legend = re.findall(r'<circle cx="5" cy="6" r="5" fill="(#[0-9a-fA-F]{3,8})"', svg)
if not legend or len(legend) > len(RAMP):
    sys.exit(f"Expected 1-{len(RAMP)} language dots, found {len(legend)}")
for colour, tint in zip(legend, RAMP):
    svg = re.sub(f'(fill|stroke)="{colour}"', rf'\1="@{tint}"', svg)
path.write_text(svg.replace('="@#', '="#'), encoding="utf-8")
