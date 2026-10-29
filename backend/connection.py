from pymavlink import mavutil
from fastapi import FastAPI, WebSocket
import asyncio
import json
import time

app = FastAPI()
master = mavutil.mavlink_connection('udpin:127.0.0.1:14552')

master.wait_heartbeat()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Frontend connected!")

    try:
        while True:
            position = master.recv_match(type='GLOBAL_POSITION_INT', blocking=False)

            if position:
                data = {"message": position.relative_alt / 1000}
                await websocket.send_text(json.dumps(data))

            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"Connection closed: {e}")




# while True:
#     position = None
#     battery = None

#     while True:
#         position = master.recv_match(type='GLOBAL_POSITION_INT', blocking=False)
#         battery = master.recv_match(type='BATTERY_STATUS', blocking=False)

#         if position:
#             print(f"Position: {position.vx}, {position.vy}, {position.vz}")
#             print(f"Altitude: {position.relative_alt / 1000}")

#         if battery:
#             print(f"Battery Voltage: {battery.voltages}")

#         time.sleep(1)
