from pymavlink import mavutil
import time

master = mavutil.mavlink_connection('udpin:127.0.0.1:14552')

master.wait_heartbeat()



while True:
    position = None
    battery = None

    while True:
        position = master.recv_match(type='GLOBAL_POSITION_INT', blocking=False)
        battery = master.recv_match(type='BATTERY_STATUS', blocking=False)

        if position:
            print(f"Position: {position.vx}, {position.vy}, {position.vz}")
            print(f"Altitude: {position.relative_alt / 1000}")

        if battery:
            print(f"Battery Voltage: {battery.voltages}")

        time.sleep(1)
        



