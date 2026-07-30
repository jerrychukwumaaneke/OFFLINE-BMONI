import serial
import time
import requests
import json

# Change COM3 to match your ESP32 COM port in Device Manager
SERIAL_PORT = "COM5"  
BAUD_RATE = 115200
FASTAPI_ENDPOINT = "https://offline-bmoni.onrender.com/transaction/offline-receive"

def listen_to_esp32():
    print(f"Connecting to ESP32 on {SERIAL_PORT} at {BAUD_RATE} baud...")
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)  # Give serial connection time to initialize
        print("Connected to ESP32! Listening for button presses...")

        while True:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                
                # Check for payload prefix from ESP32
                if line.startswith("PAYLOAD:"):
                    json_data = line.replace("PAYLOAD:", "").strip()
                    print(f"\n[HARDWARE EVENT] Received payload: {json_data}")

                    try:
                        payload = json.loads(json_data)
                        response = requests.post(FASTAPI_ENDPOINT, json=payload)
                        print(f"[BRIDGE SUCCESS] Server Response: {response.json()}")
                    except Exception as e:
                        print(f"[BRIDGE ERROR] Failed to send to local server: {e}")

    except serial.SerialException:
        print(f"Could not open port {SERIAL_PORT}. Check Device Manager to confirm your COM port number!")
    except KeyboardInterrupt:
        print("\nStopping serial listener.")

if __name__ == "__main__":
    listen_to_esp32()