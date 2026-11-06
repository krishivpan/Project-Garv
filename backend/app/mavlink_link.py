"""Reads MAVLink in a background thread and keeps the shared vehicle state."""

import queue
import threading
import time
from dataclasses import asdict

from pymavlink import mavutil

from app.config import MAVLINK_CONNECTION
from app.mission import download_mission, missions_match, summarize, upload_mission
from app.vehicle_state import VehicleState, apply_message, is_autopilot_heartbeat

LINK_TIMEOUT_S = 3      # no autopilot heartbeat for this long -> "lost"
RECONNECT_DELAY_S = 2   # pause before reopening after an error
STREAM_RATE_HZ = 5      # how often we ask the autopilot to send telemetry
RECV_TIMEOUT_S = 1      # recv_match gives up after this, so it never blocks forever
JOB_EXPIRY_S = 10       # a queued mission older than this is dropped, not sent
MISSION_REFRESH_S = 10  # re-read the drone's mission at most this often

# Our MAVLink component id (MAV_COMP_ID_USER1). pymavlink's default is 0,
# which means "everyone"; a unique id keeps the drone's replies to us apart
# from its replies to MAVProxy (230) or QGroundControl (190).
GCS_COMPONENT_ID = 25

BUSY_STATUSES = ("uploading", "verifying")

# The one shared state object. The reader thread writes it and the web
# server reads it, so every access goes through state_lock.
state = VehicleState()
state_lock = threading.Lock()

# Missions waiting to be uploaded, as (items, time submitted). The web
# server puts them here and the reader thread takes them off, so only the
# reader thread ever reads from the connection. queue.Queue is thread-safe.
mission_queue = queue.Queue()


def handle_message(msg):
    """Apply one telemetry message to the shared state."""
    with state_lock:
        apply_message(state, msg)


def set_mission_status(status: str):
    with state_lock:
        state.mission_status = status


def set_drone_mission(drone_mission: dict | None):
    with state_lock:
        state.drone_mission = drone_mission


def submit_mission(items: list[dict]) -> bool:
    """Queue a mission for upload. False if one is already in progress."""
    with state_lock:
        if state.mission_status in BUSY_STATUSES:
            return False
        state.mission_status = "uploading"
    mission_queue.put((items, time.monotonic()))
    return True


def refresh_drone_mission(conn, target_system, target_component):
    """Read the drone's mission so the app knows what it would fly."""
    result = download_mission(conn, target_system, target_component, handle_message)
    if isinstance(result, str):
        print(f"Mission download {result}")
        set_drone_mission(None)  # unknown
    else:
        set_drone_mission(summarize(result))


def run_pending_upload(conn, target_system, target_component):
    """If a mission is waiting, upload it, then read it back to verify."""
    try:
        items, submitted_at = mission_queue.get_nowait()  # don't wait if empty
    except queue.Empty:
        return

    # Re-check right before sending: things may have changed since the
    # web request was accepted (e.g. a long reconnect, or someone armed).
    if time.monotonic() - submitted_at > JOB_EXPIRY_S:
        set_mission_status("failed: expired before sending (nothing was sent)")
        return
    with state_lock:
        armed = state.armed
    if armed is not False:
        set_mission_status("failed: drone armed or state unknown (nothing was sent)")
        return

    print(f"Uploading mission with {len(items)} items")
    result = upload_mission(conn, target_system, target_component, items, handle_message)
    print(f"Mission upload: {result}")

    # Always read back, even after a failure: a failed upload can leave a
    # partial mission on the drone, and the user needs to know that.
    set_mission_status("verifying")
    received = download_mission(conn, target_system, target_component, handle_message)

    if isinstance(received, str):
        set_drone_mission(None)
        if result == "ok":
            result = f"failed: could not read the mission back ({received})"
    else:
        set_drone_mission(summarize(received))
        if result == "ok":
            difference = missions_match(items, received)
            if difference is not None:
                result = f"failed: verification: {difference}"
    print(f"Mission status: {result}")
    set_mission_status(result)


def mission_changed(msg, target_system) -> bool:
    """True if a MISSION_CURRENT message says the drone's mission isn't the
    one we last read (for example, someone uploaded from MAVProxy or QGC).

    Uses MISSION_CURRENT.total, the drone's item count. 0 or 65535 means
    the autopilot doesn't report it. A change that keeps the same number of
    items can't be noticed this way.
    """
    if msg.get_type() != "MISSION_CURRENT" or msg.get_srcSystem() != target_system:
        return False
    total = getattr(msg, "total", 0)
    if total in (0, 65535):
        return False
    with state_lock:
        known = state.drone_mission
    return known is None or known["item_count"] != total


def open_connection():
    """Open the link, wait for an autopilot heartbeat, then request streams.

    Returns the connection plus the drone's system and component ids,
    which mission messages need to address the drone.
    """
    print(f"Opening MAVLink connection: {MAVLINK_CONNECTION}")
    conn = mavutil.mavlink_connection(MAVLINK_CONNECTION, source_component=GCS_COMPONENT_ID)

    # Wait for the first autopilot heartbeat, checking once a second.
    while True:
        msg = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=RECV_TIMEOUT_S)
        if msg is not None and is_autopilot_heartbeat(msg):
            break
    print(f"Heartbeat from system {msg.get_srcSystem()}")
    handle_message(msg)

    # Ask the autopilot to send all its telemetry streams at about 5 Hz.
    # SITL already does this; real hardware often needs to be asked.
    conn.mav.request_data_stream_send(
        msg.get_srcSystem(),
        msg.get_srcComponent(),
        mavutil.mavlink.MAV_DATA_STREAM_ALL,
        STREAM_RATE_HZ,
        1,  # 1 = start sending
    )
    return conn, msg.get_srcSystem(), msg.get_srcComponent()


def read_loop():
    """Runs forever: read messages, update state, reconnect on errors."""
    while True:
        conn = None
        try:
            conn, target_system, target_component = open_connection()
            # Find out what's on the drone before anything else.
            refresh_drone_mission(conn, target_system, target_component)
            last_refresh = time.monotonic()
            while True:
                run_pending_upload(conn, target_system, target_component)
                msg = conn.recv_match(blocking=True, timeout=RECV_TIMEOUT_S)
                if msg is None:
                    continue  # nothing arrived within the timeout; try again
                handle_message(msg)
                if mission_changed(msg, target_system) and time.monotonic() - last_refresh > MISSION_REFRESH_S:
                    refresh_drone_mission(conn, target_system, target_component)
                    last_refresh = time.monotonic()
        except Exception as e:
            print(f"MAVLink error: {e!r}; reconnecting in {RECONNECT_DELAY_S} s")
            # Drop queued missions: they'd be stale by the time we're back.
            while not mission_queue.empty():
                mission_queue.get_nowait()
            with state_lock:
                # Don't leave it "uploading" forever, and forget what we
                # knew about the drone's mission until we've read it again.
                if state.mission_status in BUSY_STATUSES:
                    state.mission_status = "failed: connection error"
                state.drone_mission = None
            if conn is not None:
                conn.close()  # free the UDP port so we can reopen it
            time.sleep(RECONNECT_DELAY_S)


def start_reader():
    """Start read_loop in a background thread.

    daemon=True means the thread won't keep the program alive when the
    server shuts down.
    """
    threading.Thread(target=read_loop, daemon=True, name="mavlink-reader").start()


def get_state_dict() -> dict:
    """A snapshot of the state in the JSON shape the frontend expects."""
    with state_lock:
        data = asdict(state)  # copy while holding the lock

    last_heartbeat = data.pop("last_heartbeat")
    if last_heartbeat is None:
        data["link"] = "waiting"
    elif time.monotonic() - last_heartbeat < LINK_TIMEOUT_S:
        data["link"] = "ok"
    else:
        data["link"] = "lost"
    return data
