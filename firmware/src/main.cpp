#include <Arduino.h>

float t = 0;

void setup() {
  Serial.begin(115200);
}

void loop() {
  // Simulazione sensori
  float temperature = 22.0 + sin(t) * 2.0;
  float vibration   = random(0, 100) / 100.0;
  float load        = 50 + sin(t * 0.5) * 20;

  // formato semplice CSV
  Serial.print(temperature);
  Serial.print(",");
  Serial.print(vibration);
  Serial.print(",");
  Serial.println(load);

  t += 0.1;
  delay(200);
}