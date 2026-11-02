# Project Garv

## Running week 1

1. Start SITL (from your ArduPilot checkout):
   `Tools/autotest/sim_vehicle.py -v ArduCopter --console --out=udp:127.0.0.1:14552`
2. Backend: `cd backend && uvicorn app.main:app --reload`
3. Frontend: `cd frontend && npm install && npm run dev`
