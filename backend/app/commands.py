"""Commands that change what the drone is doing. This is the ONLY place
mode-sending code may live."""

import time
from app.config import COMMANDS_ENABLED
from app.connection import get_connection, send_lock
from app.mavlink_link import get_state_dict
from pymavlink import mavutil


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

	state = get_state_dict()

	# Get the current link
	if (state["link"] != "ok"):
		return (False, "No link to the drone")
	
	if not COMMANDS_ENABLED:
		return (False, "Commands are disabled")

	# Get the link object. get_connection() -> (connection, target_system, target_component)
	link = get_connection()

	# Make sure the link exists
	if (link is None):
		return (False, "Reconnecting to drone...")

	connection, target_system, target_component = link  # seperate the variables from link


	modes = connection.mode_mapping()  # get the dictionary of all the available modes

	if (modes is None):
		return (False, "Vehicle type not known")

	if (mode_name not in modes):
		return (False, f"{mode_name} is not in modes")

	mode_number = modes[mode_name]

	if (state["mode"] == mode_name):
		return (True, f"Already in {mode_name}")


	try:
		# Need to lock each command send because commands cannot be sent in parallel so they must send sequentially with a send_lock
		with send_lock:
			connection.mav.command_long_send(target_system,  # the drone's system id
											target_component,  # the drone's component id
											mavutil.mavlink.MAV_CMD_DO_SET_MODE, 
											0,  # confirmation: meaning this is the first attempt
											mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,  # means param2 is an Ardupilot mode number
											mode_number,  # param2
											0, 0, 0, 0 , 0)  # params 3-7
			
	except Exception as e:
		return (False, f"Failed to send: {e}")

	# Watch the mode in the vehicle state coming from the drone's heartbeat 
	deadline = time.monotonic() + 3  # create a deadline 3 seconds from the current time

	while (time.monotonic() < deadline):
		curr_state = get_state_dict()

		if (mode_name == curr_state["mode"]):
			return (True, f"Drone is now in {mode_name}")

		if (curr_state["link"] != "ok"):
			return (False, "Link lost while waiting")

		time.sleep(0.1)

	return (False, f"Drone did not switch to {mode_name} within 3s")

