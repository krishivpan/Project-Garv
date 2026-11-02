"""The latest known vehicle state, and how MAVLink messages update it."""

import time
from dataclasses import dataclass

from pymavlink import mavutil

# MAVLink component id of the main autopilot (MAV_COMP_ID_AUTOPILOT1).
AUTOPILOT_COMPONENT_ID = 1


@dataclass
class VehicleState:
    # None means "not received yet" or "the vehicle says it's unknown".
    # It becomes null in the JSON.
    armed: bool | None = None
    mode: str | None = None
    lat: float | None = None
    lon: float | None = None
    alt_rel_m: float | None = None
    heading_deg: float | None = None
    groundspeed_ms: float | None = None
    battery_v: float | None = None
    battery_pct: int | None = None
    gps_fix: int | None = None
    satellites: int | None = None
    # time.monotonic() when the last autopilot HEARTBEAT arrived.
    # Used to work out the link status; it's not sent to the browser.
    last_heartbeat: float | None = None


def is_autopilot_heartbeat(msg) -> bool:
    """True only for HEARTBEATs from the autopilot itself.

    Ground stations (like MAVProxy) and other components also send
    heartbeats; we ignore those so they can't change mode or armed state.
    """
    return (
        msg.get_type() == "HEARTBEAT"
        and msg.get_srcComponent() == AUTOPILOT_COMPONENT_ID
        and msg.type != mavutil.mavlink.MAV_TYPE_GCS
    )


def apply_message(state: VehicleState, msg) -> None:
    """Copy the fields we care about from one MAVLink message into state."""
    msg_type = msg.get_type()

    if msg_type == "HEARTBEAT":
        if not is_autopilot_heartbeat(msg):
            return
        # base_mode is a set of bit flags; the SAFETY_ARMED bit means armed.
        state.armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
        # pymavlink knows ArduPilot's mode numbers, e.g. 5 -> "LOITER".
        state.mode = mavutil.mode_string_v10(msg)
        state.last_heartbeat = time.monotonic()

    elif msg_type == "GLOBAL_POSITION_INT":
        # lat/lon arrive as integers in degE7 (degrees * 10^7) -> divide by 1e7.
        # ArduPilot sends 0, 0 until it has a position estimate (no GPS lock
        # or no GPS at all), so we treat exactly 0, 0 as unknown.
        if msg.lat == 0 and msg.lon == 0:
            state.lat = None
            state.lon = None
        else:
            state.lat = msg.lat / 1e7
            state.lon = msg.lon / 1e7
        # relative_alt is millimetres above home -> divide by 1000 for metres.
        state.alt_rel_m = msg.relative_alt / 1000
        # hdg is centidegrees (degrees * 100) -> divide by 100.
        # 65535 is the special value for "heading unknown".
        state.heading_deg = None if msg.hdg == 65535 else msg.hdg / 100

    elif msg_type == "VFR_HUD":
        # groundspeed is already in metres per second; no conversion.
        state.groundspeed_ms = msg.groundspeed

    elif msg_type == "SYS_STATUS":
        # voltage_battery is millivolts -> divide by 1000 for volts.
        state.battery_v = msg.voltage_battery / 1000
        # battery_remaining is already a percentage; -1 means "unknown".
        state.battery_pct = None if msg.battery_remaining == -1 else msg.battery_remaining

    elif msg_type == "GPS_RAW_INT":
        # fix_type: 0-1 = no fix, 2 = 2D, 3 = 3D, higher = DGPS/RTK.
        state.gps_fix = msg.fix_type
        state.satellites = msg.satellites_visible
