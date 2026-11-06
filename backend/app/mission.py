"""Building, checking, uploading and downloading MAVLink missions."""

import math
import time

from pymavlink import mavutil

m = mavutil.mavlink

# Safety limits. The backend enforces these; the frontend mirrors them in
# src/Waypoints/uploadMission.ts for early feedback, so keep the two in step.
MIN_ALT_M = 5          # metres above home: clear of people and low obstacles
MAX_ALT_M = 120        # metres above home: a common legal ceiling for drones
MAX_WAYPOINTS = 50
MAX_DISTANCE_M = 500   # every waypoint must be this close to the drone

# Handshake timing, shared by upload and download.
RECV_TIMEOUT_S = 0.5   # how long each recv_match waits
RETRY_TIMEOUT_S = 2    # silence this long -> repeat our last message
MAX_RETRIES = 3        # give up after this many silent retries in a row
DEADLINE_S = 30        # give up after this long in total, whatever happens

# Messages that belong to mission transfers. Everything else is telemetry.
MISSION_MESSAGES = (
    "MISSION_COUNT", "MISSION_ITEM_INT", "MISSION_REQUEST_INT",
    "MISSION_REQUEST", "MISSION_ACK",
)


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in metres between two lat/lon points (haversine formula)."""
    earth_radius_m = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * earth_radius_m * math.asin(math.sqrt(a))


def check_mission(waypoints: list[dict], drone_lat: float, drone_lon: float) -> list[str]:
    """Problems that should stop an upload, as sentences for the user.

    The JSON shape, altitude range and count are checked by Pydantic in
    main.py; this covers what needs the drone's position.
    """
    problems = []
    for number, wp in enumerate(waypoints, start=1):
        d = distance_m(drone_lat, drone_lon, wp["lat"], wp["lon"])
        if d > MAX_DISTANCE_M:
            problems.append(f"Waypoint {number} is {d:.0f} m from the drone (max {MAX_DISTANCE_M} m)")
    return problems


def build_mission_items(waypoints: list[dict]) -> list[dict]:
    """Waypoints [{"lat", "lon", "alt_m"}, ...] -> MISSION_ITEM_INT fields.

    Pure function: no network, so it can be checked with a print.
    Item order: 0 = home placeholder, 1 = takeoff, one per waypoint, then RTL.
    """
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

    # Take off straight up to the first waypoint's altitude (at least
    # MIN_ALT_M, because main.py rejects anything lower).
    # ArduCopter ignores lat/lon on takeoff and climbs where it is.
    items.append(item(m.MAV_CMD_NAV_TAKEOFF, m.MAV_FRAME_GLOBAL_RELATIVE_ALT, 0, 0, first["alt_m"]))

    # RELATIVE_ALT frame: z is metres above home, same meaning as alt_m.
    for wp in waypoints:
        items.append(item(m.MAV_CMD_NAV_WAYPOINT, m.MAV_FRAME_GLOBAL_RELATIVE_ALT, wp["lat"], wp["lon"], wp["alt_m"]))

    # Fly home and land after the last waypoint, instead of hovering there
    # until the battery runs low.
    items.append(item(m.MAV_CMD_NAV_RETURN_TO_LAUNCH, m.MAV_FRAME_GLOBAL_RELATIVE_ALT, 0, 0, 0))

    # seq = position in the list; the drone asks for items by this number.
    for seq, it in enumerate(items):
        it["seq"] = seq
    return items


def is_for_us(conn, msg, target_system: int) -> bool:
    """True if msg is a mission message from our drone, addressed to us,
    about the main mission (not the geofence or rally points).

    MAVProxy forwards everything, so we also see the drone talking to
    MAVProxy or QGC; checking target_system/component filters that out.
    """
    return (
        msg.get_type() in MISSION_MESSAGES
        and msg.get_srcSystem() == target_system
        and msg.target_system == conn.mav.srcSystem
        and msg.target_component == conn.mav.srcComponent
        and getattr(msg, "mission_type", m.MAV_MISSION_TYPE_MISSION) == m.MAV_MISSION_TYPE_MISSION
    )


def recv_mission_msg(conn, target_system: int, handle_other):
    """Wait up to RECV_TIMEOUT_S for the next mission message meant for us.

    Returns it, or None. Every other message is passed to handle_other,
    so telemetry keeps updating during a transfer.
    """
    msg = conn.recv_match(blocking=True, timeout=RECV_TIMEOUT_S)
    if msg is None:
        return None
    if is_for_us(conn, msg, target_system):
        return msg
    handle_other(msg)
    return None


def ack_failure(msg) -> str:
    """Turn a rejecting MISSION_ACK into text, e.g. "failed: MAV_MISSION_INVALID"."""
    return f"failed: {m.enums['MAV_MISSION_RESULT'][msg.type].name}"


def upload_mission(conn, target_system: int, target_component: int, items: list[dict], handle_other) -> str:
    """Run the upload handshake. Returns "ok" or "failed: <reason>".

    The drone leads: we send MISSION_COUNT, it asks for each item by seq,
    and finishes with MISSION_ACK. If it goes quiet we repeat our last
    message; if it stays quiet, or the whole thing takes too long, we stop.
    """
    def send_item(seq):
        conn.mav.mission_item_int_send(
            target_system, target_component, mission_type=m.MAV_MISSION_TYPE_MISSION, **items[seq]
        )

    def resend():
        if last_seq is None:
            conn.mav.mission_count_send(target_system, target_component, len(items), m.MAV_MISSION_TYPE_MISSION)
        else:
            send_item(last_seq)

    last_seq = None  # last item the drone asked for (None = still waiting for the first request)
    resend()
    deadline = time.monotonic() + DEADLINE_S
    last_heard = time.monotonic()
    retries = 0

    while time.monotonic() < deadline:
        msg = recv_mission_msg(conn, target_system, handle_other)

        if msg is None:
            if time.monotonic() - last_heard > RETRY_TIMEOUT_S:
                retries += 1
                if retries > MAX_RETRIES:
                    return "failed: no reply from drone"
                resend()
                last_heard = time.monotonic()
            continue

        if msg.get_type() == "MISSION_ACK":
            return "ok" if msg.type == m.MAV_MISSION_ACCEPTED else ack_failure(msg)

        # MISSION_REQUEST_INT or MISSION_REQUEST: send exactly what it asked
        # for (it may ask for the same item again if one got lost).
        if msg.get_type() in ("MISSION_REQUEST_INT", "MISSION_REQUEST") and 0 <= msg.seq < len(items):
            last_seq = msg.seq
            send_item(last_seq)
            last_heard = time.monotonic()
            retries = 0

    return "failed: took too long"


def download_mission(conn, target_system: int, target_component: int, handle_other):
    """Read the whole mission from the drone.

    Returns a list of item dicts (same keys as build_mission_items uses),
    or a "failed: <reason>" string. This only reads, so it's safe at any
    time, even in flight.
    """
    count = None  # number of items, once the drone has told us
    items = []

    def resend():
        if count is None:
            conn.mav.mission_request_list_send(target_system, target_component, m.MAV_MISSION_TYPE_MISSION)
        else:
            # Ask for the next item we don't have yet.
            conn.mav.mission_request_int_send(target_system, target_component, len(items), m.MAV_MISSION_TYPE_MISSION)

    resend()
    deadline = time.monotonic() + DEADLINE_S
    last_heard = time.monotonic()
    retries = 0

    while time.monotonic() < deadline:
        msg = recv_mission_msg(conn, target_system, handle_other)

        if msg is None:
            if time.monotonic() - last_heard > RETRY_TIMEOUT_S:
                retries += 1
                if retries > MAX_RETRIES:
                    return "failed: no reply from drone"
                resend()
                last_heard = time.monotonic()
            continue

        msg_type = msg.get_type()
        if msg_type == "MISSION_ACK":
            return ack_failure(msg)  # the drone refused or aborted the transfer

        if msg_type == "MISSION_COUNT" and count is None:
            count = msg.count
        elif msg_type == "MISSION_ITEM_INT" and count is not None and msg.seq == len(items):
            items.append({
                "seq": msg.seq, "frame": msg.frame, "command": msg.command,
                "x": msg.x, "y": msg.y, "z": msg.z,
            })
        else:
            continue  # a duplicate or something we didn't ask for

        last_heard = time.monotonic()
        retries = 0
        if len(items) == count:
            # Tell the drone we're done, as the protocol requires.
            conn.mav.mission_ack_send(
                target_system, target_component, m.MAV_MISSION_ACCEPTED, m.MAV_MISSION_TYPE_MISSION
            )
            return items
        resend()

    return "failed: took too long"


def missions_match(sent: list[dict], received: list[dict]) -> str | None:
    """None if the drone holds the mission we sent, else what differs.

    Item 0 is skipped: ArduPilot replaces it with its real home.
    """
    if len(received) != len(sent):
        return f"drone has {len(received)} items, expected {len(sent)}"
    for s, r in zip(sent[1:], received[1:]):
        if r["command"] != s["command"]:
            return f"item {s['seq']} has the wrong command"
        if s["command"] == m.MAV_CMD_NAV_WAYPOINT and (r["x"], r["y"]) != (s["x"], s["y"]):
            return f"item {s['seq']} is in the wrong place"
        # ArduPilot stores altitude in whole centimetres, so allow 2 cm.
        if s["command"] in (m.MAV_CMD_NAV_WAYPOINT, m.MAV_CMD_NAV_TAKEOFF) and abs(r["z"] - s["z"]) > 0.02:
            return f"item {s['seq']} has the wrong altitude"
    return None


def summarize(items: list[dict]) -> dict:
    """What's on the drone, in the shape the frontend compares its map with.

    standard = True if it's shaped like ours: takeoff, waypoints, RTL.
    item_count includes home, like MISSION_CURRENT.total does.
    """
    body = items[1:]  # skip home
    commands = [it["command"] for it in body]
    standard = (
        len(body) >= 3
        and commands[0] == m.MAV_CMD_NAV_TAKEOFF
        and commands[-1] == m.MAV_CMD_NAV_RETURN_TO_LAUNCH
        and all(c == m.MAV_CMD_NAV_WAYPOINT for c in commands[1:-1])
    )
    waypoints = [
        {"lat": it["x"] / 1e7, "lon": it["y"] / 1e7, "alt_m": it["z"]}  # degE7 -> degrees
        for it in body
        if it["command"] == m.MAV_CMD_NAV_WAYPOINT
    ]
    return {"waypoints": waypoints, "standard": standard, "item_count": len(items)}
