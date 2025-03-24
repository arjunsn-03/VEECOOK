#include <Servo.h>

Servo servos[5];  
const int servoPins[5] = {3, 4, 6, 9, 10};

void setup() {
    Serial.begin(9600);
    Serial.println("Starting...");
    
    // Initialize servos
    for (int i = 0; i < 5; i++) {
        if (servos[i].attach(servoPins[i])) {
            Serial.println("Servo " + String(i + 1) + " ready");
            servos[i].write(0);
        } else {
            Serial.println("Failed to attach servo " + String(i + 1));
        }
    }
    Serial.println("Ready for commands");
}

void loop() {
    if (Serial.available() > 0) {
        String command = Serial.readStringUntil('\n');
        command.trim();
        
        Serial.println("Received: " + command);  // Echo back what we received
        
        if (command.startsWith("SERVO:")) {
            int firstColon = command.indexOf(':');
            int secondColon = command.indexOf(':', firstColon + 1);
            
            if (secondColon != -1) {
                int servoNum = command.substring(firstColon + 1, secondColon).toInt();
                int angle = command.substring(secondColon + 1).toInt();
                
                Serial.println("Moving servo " + String(servoNum) + " to " + String(angle));
                
                if (servoNum >= 1 && servoNum <= 5 && angle >= 0 && angle <= 180) {
                    servos[servoNum - 1].write(angle);
                    delay(1000);
                    Serial.println("Movement complete");
                }
            }
        }
    }
}
