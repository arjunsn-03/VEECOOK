import serial
import time

# Setup connection
print("Opening serial connection...")
arduino = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
time.sleep(2)  # Wait for Arduino to reset

print("Sending command...")
command = "SERVO:1:90\n"
print(f"Sending: {command.strip()}")
arduino.write(command.encode())
arduino.flush()

# Wait for movement
time.sleep(3)

print("Closing connection...")
arduino.close()

print("Test complete")