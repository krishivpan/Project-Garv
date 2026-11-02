"""Settings read from backend/.env (or from real environment variables)."""

import os
from pathlib import Path

from dotenv import load_dotenv

# backend/.env sits one folder above this file (backend/app/config.py).
# If the file doesn't exist, load_dotenv() simply does nothing.
load_dotenv(Path(__file__).parent.parent / ".env")

# Where to read MAVLink from. The default listens on the UDP port that
# SITL/MAVProxy is told to send to with --out=udp:127.0.0.1:14552.
MAVLINK_CONNECTION = os.getenv("MAVLINK_CONNECTION", "udpin:127.0.0.1:14552")
