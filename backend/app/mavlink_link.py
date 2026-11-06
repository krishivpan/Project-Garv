"""Reads MAVLink in a background thread and keeps the shared vehicle state."""

import queue
import threading
import time
from dataclasses import asdict

from pymavlink import mavutil

from app.config import MAVLINK_CONNECTION
from app.mission import upload_mission
from app.vehicle_state import VehicleState, apply_message, is_autopilot_heartbeat

LINK_TIMEOUT_S = 3      # no autopilot heartbeat for this long -> "lost"
RECONNECT_DELAY_S = 2   # pause before reopening after an error
STREAM_RATE_HZ = 5      # how often we ask the autopilot to send telemetry
RECV_TIMEOUT_S = 1      # recv_match gives up after this, so it never blocks forever

# The one shared state object. The reader thread writes it and the web
# server reads it, so every access goes through state_lock.
state = VehicleState()
state_lock = threading.Lock()

# Missions waiting to be uploaded. The web server puts them here and the
# reader thread takes them off, so only the reader thread ever reads from
# the connection. queue.Queue is safe to use from several threads.
mission_queue = queue.Queue()


def handle_message(msg):
    """Apply one telemetry message to the shared state."""
    with state_lock:
        apply_message(state, msg)


def set_mission_status(status: str):
    with state_lock:
        state.mission_status = status


def submit_mission(items: list[dict]) -> bool:
    """Queue a mission for upload. False if one is already uploading."""
    with state_lock:
        if state.mission_status == "uploading":
            return False
        state.mission_status = "uploading"
    mission_queue.put(items)
    return True


def run_pending_upload(conn, target_system, target_component):
    """If a mission is waiting, upload it now (called from the read loop)."""
    try:
        items = mission_queue.get_nowait()  # don't wait if the queue is empty
    except queue.Empty:
        return
    print(f"Uploading mission with {len(items)} items")
    result = upload_mission(conn, target_system, target_component, items, handle_message)
    print(f"Mission upload: {result}")
    set_mission_status(result)


def open_connection():
    """Open the link, wait for an autopilot heartbeat, then request streams.

    Returns the connection plus the drone's system and component ids,
    which mission messages need to address the drone.
    """
    print(f"Opening MAVLink connection: {MAVLINK_CONNECTION}")
    conn = mavutil.mavlink_connection(MAVLINK_CONNECTION)

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
            while True:
                run_pending_upload(conn, target_system, target_component)
                msg = conn.recv_match(blocking=True, timeout=RECV_TIMEOUT_S)
                if msg is None:
                    continue  # nothing arrived within the timeout; try again
                handle_message(msg)
        except Exception as e:
            print(f"MAVLink error: {e!r}; reconnecting in {RECONNECT_DELAY_S} s")
            # If the error happened mid-upload, don't leave it "uploading" forever.
            with state_lock:
                if state.mission_status == "uploading":
                    state.mission_status = "failed: connection error"
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
