"""Turning waypoints into a MAVLink mission, and uploading it to the drone."""

import time

from pymavlink import mavutil

MAX_RETRIES = 3          # give up after this many silent timeouts in a row
RETRY_TIMEOUT_S = 2      # how long to wait for the drone before retrying
RECV_TIMEOUT_S = 0.5     # how long each recv_match waits

# Messages that belong to the upload handshake. Everything else is telemetry.
MISSION_MESSAGES = ("MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK")


def build_mission_items(waypoints: list[dict]) -> list[dict]:
    """Waypoints [{"lat", "lon", "alt_m"}, ...] -> MISSION_ITEM_INT fields.

    Pure function: no network, so it can be checked with a print.
    Item order: 0 = home placeholder, 1 = takeoff, then one per waypoint.
    """
    m = mavutil.mavlink
    first = waypoints[0]

    def item(command, frame, lat, lon, alt_m):
        return {
            "frame": frame,
            "command": command,
            "current": 0,
            "autocontinue": 1,  # go straight on to the next item when done
            "param1": 0, "param2": 0, "param3": 0, "param4": 0,
            # x/y are lat/lon in degE7: degrees * 10^7, as whole numbers
            # (the reverse of the conversion in vehicle_state.py).
            "x": round(lat * 1e7),
            "y": round(lon * 1e7),
            "z": alt_m,  # metres
        }

    # Item 0 is "home" for ArduPilot, which replaces it with its real home
    # position. It still has to be sent, so use the first waypoint.
    items = [item(m.MAV_CMD_NAV_WAYPOINT, m.MAV_FRAME_GLOBAL, first["lat"], first["lon"], 0)]

    # Take off straight up to the first waypoint's altitude.
    # (ArduCopter ignores lat/lon on takeoff and climbs where it is.)
    items.append(item(m.MAV_CMD_NAV_TAKEOFF, m.MAV_FRAME_GLOBAL_RELATIVE_ALT, 0, 0, first["alt_m"]))

    # RELATIVE_ALT frame: z is metres above home, same meaning as alt_m.
    for wp in waypoints:
        items.append(item(m.MAV_CMD_NAV_WAYPOINT, m.MAV_FRAME_GLOBAL_RELATIVE_ALT, wp["lat"], wp["lon"], wp["alt_m"]))

    # seq = position in the list; the drone asks for items by this number.
    for seq, it in enumerate(items):
        it["seq"] = seq
    return items


def is_for_us(conn, msg, target_system: int) -> bool:
    """True if msg is a mission reply from our drone addressed to us.

    MAVProxy forwards everything, so we can also see the drone talking to
    MAVProxy; checking target_system/component filters that out.
    """
    return (
        msg.get_type() in MISSION_MESSAGES
        and msg.get_srcSystem() == target_system
        and msg.target_system == conn.mav.srcSystem
        and msg.target_component == conn.mav.srcComponent
    )


def upload_mission(conn, target_system: int, target_component: int, items: list[dict], handle_other) -> str:
    """Run the upload handshake. Returns "ok" or "failed: <reason>".

    The drone leads: we send MISSION_COUNT, it asks for each item by seq,
    and finishes with MISSION_ACK. Messages that aren't part of the
    handshake are passed to handle_other so telemetry keeps updating.
    """
    m = mavutil.mavlink

    def send_count():
        conn.mav.mission_count_send(target_system, target_component, len(items), m.MAV_MISSION_TYPE_MISSION)

    def send_item(seq):
        conn.mav.mission_item_int_send(target_system, target_component, mission_type=m.MAV_MISSION_TYPE_MISSION, **items[seq])

    send_count()
    last_seq = None              # last item the drone asked for
    last_heard = time.monotonic()
    retries = 0

    while True:
        msg = conn.recv_match(blocking=True, timeout=RECV_TIMEOUT_S)

        if msg is not None and not is_for_us(conn, msg, target_system):
            handle_other(msg)
            msg = None

        if msg is None:
            # Nothing from the drone for a while: repeat our last step.
            if time.monotonic() - last_heard > RETRY_TIMEOUT_S:
                retries += 1
                if retries > MAX_RETRIES:
                    return "failed: no reply from drone"
                if last_seq is None:
                    send_count()
                else:
                    send_item(last_seq)
                last_heard = time.monotonic()
            continue

        last_heard = time.monotonic()
        retries = 0

        if msg.get_type() == "MISSION_ACK":
            if msg.type == m.MAV_MISSION_ACCEPTED:
                return "ok"
            # Turn the result number into its name, e.g. MAV_MISSION_INVALID_PARAM1.
            reason = m.enums["MAV_MISSION_RESULT"][msg.type].name
            return f"failed: {reason}"

        # MISSION_REQUEST_INT or MISSION_REQUEST: send exactly what it asked
        # for (it may ask for the same item again if one got lost).
        if 0 <= msg.seq < len(items):
            last_seq = msg.seq
            send_item(msg.seq)
