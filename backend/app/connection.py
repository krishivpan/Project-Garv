"""The MAVLink connection shared between threads, and the lock for sending on it.

Threading model
---------------
- The reader thread (mavlink_link.read_loop) OWNS the connection: it opens it,
  closes it, and is the ONLY thread that ever reads from it (recv_match).
  Mission uploads/downloads also run in the reader thread for that reason.
- Other threads (FastAPI request handlers, e.g. commands.set_mode) may SEND on
  it, but must get it with get_connection() and hold send_lock while sending.
- EVERY send in the backend holds send_lock, the reader thread's included.
  pymavlink is not safe to send from two threads at once: every packet takes
  the next number from one shared sequence counter, so two threads sending at
  the same moment could produce duplicate or garbled packets.
- Hold send_lock only around the send call itself, never while waiting for a
  reply, so the reader thread and request handlers never block each other
  for long.
- The connection can be closed by the reader thread at any moment (link
  error -> reconnect). Code in other threads must expect a send to fail.
"""

import threading

send_lock = threading.Lock()

# (conn, target_system, target_component) while connected, else None.
# Only the reader thread changes it. Replacing a variable is a single step in
# Python, so other threads always see either the old value or the new one.
_current = None


def set_connection(conn, target_system: int, target_component: int):
    """Called by the reader thread once the drone's heartbeat has been seen."""
    global _current
    _current = (conn, target_system, target_component)


def clear_connection():
    """Called by the reader thread before it closes the connection."""
    global _current
    _current = None


def get_connection():
    """The current (conn, target_system, target_component), or None while
    (re)connecting. The target ids are the drone's, needed to address it."""
    return _current
