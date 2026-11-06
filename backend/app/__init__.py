import os

# Use MAVLink 2 message definitions. pymavlink picks them when it is first
# imported, so this must run before any "from pymavlink import ..." line,
# and this file runs before every other module in app/.
# MAVLink 2 has fields the mission code needs (mission_type,
# MISSION_CURRENT.total) and still understands MAVLink 1 packets.
# Without this, pymavlink starts on MAVLink 1 and only switches if the
# drone happens to send MAVLink 2 first.
os.environ.setdefault("MAVLINK20", "1")
