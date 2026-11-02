"""Reads MAVLink in a background thread and keeps the shared vehicle state."""

import threading
import time
from dataclasses import asdict

from pymavlink import mavutil

from app.config import MAVLINK_CONNECTION
from app.vehicle_state import VehicleState, apply_message, is_autopilot_heartbeat

LINK_TIMEOUT_S = 3      # no autopilot heartbeat for this long -> "lost"
RECONNECT_DELAY_S = 2   # pause before reopening after an error
STREAM_RATE_HZ = 5      # how often we ask the autopilot to send telemetry
RECV_TIMEOUT_S = 1      # recv_match gives up after this, so it never blocks forever

# The one shared state object. The reader thread writes it and the web
# server reads it, so every access goes through state_lock.
state = VehicleState()
state_lock = threading.Lock()


def open_connection():
    """Open the link, wait for an autopilot heartbeat, then request streams."""
    print(f"Opening MAVLink connection: {MAVLINK_CONNECTION}")
    conn = mavutil.mavlink_connection(MAVLINK_CONNECTION)

    # Wait for the first autopilot heartbeat, checking once a second.
    while True:
        msg = conn.recv_match(type="HEARTBEAT", blocking=True, timeout=RECV_TIMEOUT_S)
        if msg is not None and is_autopilot_heartbeat(msg):
            break
    print(f"Heartbeat from system {msg.get_srcSystem()}")
    with state_lock:
        apply_message(state, msg)

    # Ask the autopilot to send all its telemetry streams at about 5 Hz.
    # SITL already does this; real hardware often needs to be asked.
    conn.mav.request_data_stream_send(
        msg.get_srcSystem(),
        msg.get_srcComponent(),
        mavutil.mavlink.MAV_DATA_STREAM_ALL,
        STREAM_RATE_HZ,
        1,  # 1 = start sending
    )
    return conn


def read_loop():
    """Runs forever: read messages, update state, reconnect on errors."""
    while True:
        conn = None
        try:
            conn = open_connection()
            while True:
                msg = conn.recv_match(blocking=True, timeout=RECV_TIMEOUT_S)
                if msg is None:
                    continue  # nothing arrived within the timeout; try again
                with state_lock:
                    apply_message(state, msg)
        except Exception as e:
            print(f"MAVLink error: {e!r}; reconnecting in {RECONNECT_DELAY_S} s")
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
