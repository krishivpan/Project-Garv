"""Commands that change what the drone is doing. This is the ONLY place
mode-sending code may live."""


def set_mode(mode_name: str) -> tuple[bool, str]:
    """Ask the drone to switch to mode_name (e.g. "RTL" or "LAND").

    Must, in this order:
    1. Refuse unless the link is "ok" and commands are enabled
       (COMMANDS_ENABLED in .env), returning (False, <reason>).
    2. Look up the mode number with the connection's mode_mapping()
       (e.g. {"RTL": 6, "LAND": 9, ...}); refuse if the name isn't in it.
    3. Send the mode change while holding the send lock, so it can't
       interleave with anything else being sent on the connection.
       Get the connection and the drone's ids from
       connection.get_connection() (None while reconnecting), and hold
       connection.send_lock only around the send itself. The reader thread
       can close the connection at any moment, so a failed send must become
       (False, <reason>), not an exception. See connection.py.
    4. Confirm the change by polling the shared vehicle state (the mode
       from the autopilot's HEARTBEAT) for up to 3 seconds.

    Returns (ok, reason): (True, <what happened>) once the drone reports the
    new mode, or (False, <why not>) if refused, unknown, or not confirmed
    in time.
    """
    return (False, "set_mode not implemented yet")
