/***************************************************************************************/
// File: Arduino Driver
// Project: Time Locked Box Simulator
//Research Group: Suarez Lab, Queensland Brain Institute, UQ
//
// Author: Simon / Tevyn

#include <Arduino.h>

int motorPin = 9;
int strength = 0; // PWM value, updated from Python with s:[0 or 30-250].
unsigned int onTime = 0;   // Milliseconds, updated from Python with n:[ms].
unsigned int offTime = 0;  // Milliseconds, updated from Python with m:[ms].

bool hasStrength = false;
bool hasOnTime = false;
bool hasOffTime = false;
bool motorWasOn = false;
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
  long int value = command.substring(separatorIndex + 1).toInt();

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
  // Continuously check for serial commands 
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

  unsigned long now = millis();

  // Execution Loop
  if (strength > 0) {
    unsigned long cycleTime = onTime + offTime;
    unsigned long phase = now % cycleTime;
    bool motorIsOn = (phase < onTime);

    if (motorIsOn && !motorWasOn) {
      Serial.println("P:ON");
    } else if (!motorIsOn && motorWasOn) {
      Serial.println("P:OFF");
    }
    motorWasOn = motorIsOn;
    analogWrite(motorPin, motorIsOn ? strength : 0);
  } else {
    if (motorWasOn) {
      Serial.println("P:OFF");
    }
    motorWasOn = false;
    analogWrite(motorPin, 0);
  }
}
