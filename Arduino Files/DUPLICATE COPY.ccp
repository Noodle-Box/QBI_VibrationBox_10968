#include <Arduino.h>
/*
 * Serial Controlled Vibration Platform
 * Commands: "s:80" (80% strength), "n:200" (200ms ON), "f:500" (500ms OFF)
 */

int motorPin = 9;
int strength = 150;    // Default 50% (20-255 scale)
int onTime = 200;      // Default 200ms
int offTime = 500;     // Default 500ms

void setup() {
  pinMode(motorPin, OUTPUT);
  Serial.begin(9600);
  Serial.println("System Ready. Use s:[0-100], n:[ms], f:[ms]");
}

void loop() {
  // Check for Serial Instructions
  if (Serial.available() > 0) {
    char type = Serial.read();    // Read the prefix (s, n, or f)
    if (Serial.read() == ':') {   // Look for the colon separator
      int value = Serial.parseInt(); // Read the numerical value

      if (type == 's') {
        strength = map(value, 0, 100, 0, 255);
        Serial.print("Strength set to: "); Serial.print(value); Serial.println("%");
      } 
      else if (type == 'n') {
        onTime = value;
        Serial.print("On-Time set to: "); Serial.print(value); Serial.println("ms");
      } 
      else if (type == 'f') {
        offTime = value;
        Serial.print("Off-Time set to: "); Serial.print(value); Serial.println("ms");
      }
    }
  }

  // Execution Loop
  if (strength > 0) {
    analogWrite(motorPin, strength);
    delay(onTime);
    
    analogWrite(motorPin, 0);
    delay(offTime);
  } else {
    analogWrite(motorPin, 0);
  }
}