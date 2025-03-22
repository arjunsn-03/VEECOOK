#include <Servo.h>

// Servo Setup (Carrot, Green Peas, Corn Flour, Salt, Pepper)
Servo servos[5];  
const int servoPins[5] = {3,4 , 6, 9, 10};  

// Stepper Motor Setup (Water, Stirring)
const int waterStep = 7, waterDir = 13;
const int stirStep = 8, stirDir = 2;

const int stepDelay = 500;  // Adjust speed

// Recipe Structure
struct Ingredient {
    String name;
    int servoIndex;  
    unsigned long dispenseTime;
};

// Updated Veg Soup Recipe
Ingredient recipe[] = {
    {"Water", -1, 5000},       // Step 1: Dispense Water
    {"Carrot", 0, 10000},      // Step 2: Add Carrot
    {"Green Peas", 1, 15000},  // Step 3: Add Green Peas
    {"Corn Flour", 2, 20000},  // Step 4: Add Corn Flour
    {"Salt", 3, 25000},        // Step 5: Add Salt
    {"Pepper", 4, 30000},      // Step 6: Add Pepper
    {"Stir", -2, 35000}        // Step 7: Stir the Soup
};

const int recipeSize = sizeof(recipe) / sizeof(recipe[0]);

unsigned long startTime;
int currentStep = 0;

void setup() {
    Serial.begin(9600);
    
    // Attach Servos
    for (int i = 0; i < 5; i++) {
        servos[i].attach(servoPins[i]);
        servos[i].write(0);
    }

    // Stepper Pins as Output
    pinMode(waterStep, OUTPUT);
    pinMode(waterDir, OUTPUT);
    pinMode(stirStep, OUTPUT);
    pinMode(stirDir, OUTPUT);

    Serial.println("Veg Soup Maker Ready...");
    startTime = millis();
}

// Function to Run Stepper Motors
void runStepper(int stepPin, int dirPin, int steps, bool direction) {
    digitalWrite(dirPin, direction);
    for (int i = 0; i < steps; i++) {
        digitalWrite(stepPin, HIGH);
        delayMicroseconds(stepDelay);
        digitalWrite(stepPin, LOW);
        delayMicroseconds(stepDelay);
    }
}

// Dispense Ingredient
void dispenseIngredient(int index) {
    Serial.print("Dispensing: ");
    Serial.println(recipe[currentStep].name);

    if (index >= 0 && index < 5) {  // Ensure valid servo index
        servos[index].write(100);
        delay(1000);
        servos[index].write(0);
    } else if (index == -1) {
        Serial.println("Pumping Water...");
        runStepper(waterStep, waterDir, 800, true);  
    } else if (index == -2) {
        Serial.println("Stirring Soup...");
        runStepper(stirStep, stirDir, 800, true);  
    }

    Serial.println("Step Complete.\n");
}

// Main Loop
void loop() {
    unsigned long elapsedTime = millis() - startTime;

    if (currentStep < recipeSize && elapsedTime >= recipe[currentStep].dispenseTime) {
        dispenseIngredient(recipe[currentStep].servoIndex);
        currentStep++;
    }
}