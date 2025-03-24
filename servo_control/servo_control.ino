#include <Servo.h>

// Servo Setup (Carrot, Green Peas, Corn Flour, Salt, Pepper)
Servo servos[5];  
const int servoPins[5] = {3, 4, 6, 9, 10};  // Pins for the 5 servos

// Command Processing
const int BUFFER_SIZE = 32;
char cmdBuffer[BUFFER_SIZE];
int cmdIndex = 0;

// Status LED
const int statusLed = LED_BUILTIN;

void setup() {
    Serial.begin(9600);  // Match Raspberry Pi's baud rate
    delay(2000);  // Wait for serial connection to stabilize
    
    // Initialize status LED
    pinMode(statusLed, OUTPUT);
    digitalWrite(statusLed, LOW);
    
    // Initialize all servos
    for (int i = 0; i < 5; i++) {
        if (servos[i].attach(servoPins[i])) {
            Serial.println("STATUS:Servo " + String(i + 1) + " attached to pin " + String(servoPins[i]));
        } else {
            Serial.println("ERROR:Failed to attach servo " + String(i + 1) + " to pin " + String(servoPins[i]));
        }
        servos[i].write(0);  // Initialize to closed position
        delay(100);
    }
    
    digitalWrite(statusLed, HIGH);
    Serial.println("Ready");
}

void loop() {
    // Process incoming commands
    while (Serial.available() > 0) {
        char c = Serial.read();
        
        if (c == '\n') {
            // Null terminate the buffer
            cmdBuffer[cmdIndex] = '\0';
            // Process the complete command
            processCommand(String(cmdBuffer));
            // Reset buffer
            cmdIndex = 0;
        } else if (cmdIndex < BUFFER_SIZE - 1) {
            cmdBuffer[cmdIndex++] = c;
        }
    }
    
    // Small delay to prevent busy-waiting
    delay(10);
}

void processCommand(String command) {
    command.trim();
    Serial.println("Received command: " + command);  // Debug log
    
    // Handle servo commands
    if (command.startsWith("SERVO:")) {
        // Format: SERVO:number:amount
        int servoIndex = command.substring(6, 7).toInt() - 1;
        String amountStr = command.substring(8);
        
        if (amountStr == "STOP") {
            stopServo(servoIndex + 1);
            Serial.println("STATUS:Servo stopped");
        } else {
            int amount = amountStr.toInt();
            if (amount >= 0 && amount <= 180) {
                Serial.println("STATUS:Moving servo " + String(servoIndex + 1) + " to " + String(amount) + " degrees");
                controlServo(servoIndex + 1, amount);
                Serial.println("STATUS:Dispensed ingredient for servo " + String(servoIndex + 1));
            } else {
                Serial.println("ERROR:Invalid amount");
            }
        }
        return;
    }
    
    // Handle ABORT command
    if (command == "ABORT") {
        stopAllServos();
        Serial.println("STATUS:All servos stopped");
        return;
    }
    
    // Unknown command
    Serial.println("ERROR:Unknown command");
}

void controlServo(int servoNumber, int amount) {
    int index = servoNumber - 1;
    if (index >= 0 && index < 5) {
        if (amount >= 0 && amount <= 180) {
            servos[index].write(amount);
            delay(1000);  // Allow servo to move
            Serial.println("STATUS:Servo " + String(servoNumber) + " moved to " + String(amount) + " degrees");
        } else {
            Serial.println("ERROR:Invalid amount for servo " + String(servoNumber));
        }
    } else {
        Serial.println("ERROR:Invalid servo number " + String(servoNumber));
    }
}

void stopServo(int servoNumber) {
    int index = servoNumber - 1;
    if (index >= 0 && index < 5) {
        servos[index].write(0);  // Return to initial position
    }
}

void stopAllServos() {
    // Stop all servos
    for (int i = 0; i < 5; i++) {
        stopServo(i + 1);
    }
}