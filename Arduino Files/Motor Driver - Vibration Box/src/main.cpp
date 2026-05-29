#include <Arduino.h>

/*
 * Serial Controlled Vibration Platform
 * Commands: "s:150" (PWM strength), "n:200" (200ms ON), "m:500" (500ms OFF)
 */

int motorPin = 9;
int strength = 0; // PWM value, updated from Python with s:[0 or 30-250].
int onTime = 0;   // Milliseconds, updated from Python with n:[ms].
int offTime = 0;  // Milliseconds, updated from Python with m:[ms].

bool hasStrength = false;
bool hasOnTime = false;
bool hasOffTime = false;
String serialBuffer = "";

void handleCommand(String command) {
  command.trim();

  int separatorIndex = command.indexOf(':');
  if (separatorIndex <= 0) {
    Serial.print("Invalid command: ");
    Serial.println(command);
    return;
  }

  char type = command.charAt(0);
  int value = command.substring(separatorIndex + 1).toInt();

  if (type == 's') {
    value = constrain(value, 0, 250);
    strength = value;
    hasStrength = true;
    Serial.print("Strength set to: "); Serial.println(value);
  } 
  else if (type == 'n') {
    onTime = max(value, 0);
    hasOnTime = true;
    Serial.print("On-Time set to: "); Serial.print(onTime); Serial.println("ms");
  } 
  else if (type == 'm' || type == 'f') {
    offTime = max(value, 0);
    hasOffTime = true;
    Serial.print("Off-Time set to: "); Serial.print(offTime); Serial.println("ms");
  }
  else {
    Serial.print("Unknown command type: ");
    Serial.println(type);
  }
}

void setup() {
  pinMode(motorPin, OUTPUT);
  analogWrite(motorPin, 0);
  Serial.begin(9600);
  Serial.println("System Ready. Waiting for Python: s:[0 or 30-250], n:[ms], m:[ms]");
}

void loop() {
  // Check for Serial Instructions
  while (Serial.available() > 0) {
    char incomingChar = Serial.read();

    if (incomingChar == '\n') {
      handleCommand(serialBuffer);
      serialBuffer = "";
    }
    else if (incomingChar != '\r') {
      serialBuffer += incomingChar;
    }
  }

  if (!hasStrength || !hasOnTime || !hasOffTime) {
    analogWrite(motorPin, 0);
    return;
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
