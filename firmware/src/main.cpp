#include <Arduino.h>
#include <M5Unified.h>

// ==============================================================================
// main.cpp — Firmware reale per M5Stack CoreS3
// Legge tutti i sensori disponibili e manda i dati via seriale in formato CSV.
//
// Formato output (una riga ogni 100ms):
//   timestamp,temp,acc_x,acc_y,acc_z,gyr_x,gyr_y,gyr_z,mag_x,mag_y,mag_z,mic,bat_v,bat_pct
//
// Sensori:
//   IMU BMI270:  accelerometro (g), giroscopio (°/s)
//   IMU BMM150:  magnetometro (µT) — bussola
//   Microfono:   livello audio (0-100, valore RMS normalizzato)
//   Batteria:    tensione (V) e percentuale (%)
// ==============================================================================

// Variabili globali per i dati dell'IMU
// Inizializziamo a 0 — in C++ le variabili locali non inizializzate
// contengono valori casuali (garbage), meglio essere espliciti.
float acc_x = 0, acc_y = 0, acc_z = 0;  // accelerometro (g)
float gyr_x = 0, gyr_y = 0, gyr_z = 0;  // giroscopio (gradi/secondo)
float mag_x = 0, mag_y = 0, mag_z = 0;  // magnetometro (microtesla)
float imu_temp = 0;                       // temperatura chip IMU (°C)

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);
  Serial.begin(115200);

  // Inizializziamo il microfono — M5Unified gestisce l'hardware interno
  M5.Mic.begin();

  delay(500);  // pausa per stabilizzazione hardware
}

void loop() {
  M5.update();  // aggiorna stato interno board (obbligatorio in ogni loop)

  // --- Lettura IMU ---
  // getAccelData, getGyroData, getMagData riempiono le variabili passate
  // per riferimento (come i puntatori in C, ma con sintassi più pulita in C++)
  M5.Imu.getAccelData(&acc_x, &acc_y, &acc_z);
  M5.Imu.getGyroData(&gyr_x, &gyr_y, &gyr_z);
  M5.Imu.getMag(&mag_x, &mag_y, &mag_z);
  M5.Imu.getTemp(&imu_temp);

  // --- Lettura microfono ---
  // Il microfono del CoreS3 richiede un buffer per campionare l'audio.
  // Leggiamo un breve buffer e calcoliamo il valore RMS (Root Mean Square)
  // che rappresenta il "volume" medio — più utile del valore istantaneo.
  int16_t mic_buffer[256];  // buffer audio — int16_t = intero a 16 bit con segno
  float mic_level = 0;

  // record() riempie il buffer con campioni audio
  // 256 = numero di campioni, 8000 = frequenza di campionamento (Hz)
  if (M5.Mic.record(mic_buffer, 256, 8000)) {
    // Calcoliamo RMS manualmente:
    // 1. somma dei quadrati
    // 2. dividi per il numero di campioni (media)
    // 3. radice quadrata
    float sum = 0;
    for (int i = 0; i < 256; i++) {
      sum += (float)mic_buffer[i] * mic_buffer[i];
      // (float) è un cast esplicito — convertiamo int16_t in float
      // prima di moltiplicare per evitare overflow dell'intero
    }
    // sqrt() è la radice quadrata — da <math.h>, già incluso da Arduino.h
    // Normalizziamo dividendo per 32768 (valore massimo di int16_t)
    // e per 100 per avere un range 0-100
    mic_level = (sqrt(sum / 256) / 32768.0) * 100.0;
  }

  // --- Lettura batteria ---
  // getBatteryVoltage() restituisce la tensione in millivolt (mV)
  // dividiamo per 1000.0 per avere Volt
  float bat_voltage = M5.Power.getBatteryVoltage() / 1000.0;

  // getBatteryLevel() restituisce la percentuale 0-100
  // Restituisce -1 se non c'è batteria o non è rilevabile
  int bat_percent = M5.Power.getBatteryLevel();

  // --- Output CSV ---
  // Stampiamo tutti i valori su una riga separati da virgola.
  // Formato: timestamp,temp,ax,ay,az,gx,gy,gz,mx,my,mz,mic,bat_v,bat_pct
  Serial.print(millis());        Serial.print(",");
  Serial.print(imu_temp, 2);     Serial.print(",");
  Serial.print(acc_x, 3);        Serial.print(",");
  Serial.print(acc_y, 3);        Serial.print(",");
  Serial.print(acc_z, 3);        Serial.print(",");
  Serial.print(gyr_x, 2);        Serial.print(",");
  Serial.print(gyr_y, 2);        Serial.print(",");
  Serial.print(gyr_z, 2);        Serial.print(",");
  Serial.print(mag_x, 2);        Serial.print(",");
  Serial.print(mag_y, 2);        Serial.print(",");
  Serial.print(mag_z, 2);        Serial.print(",");
  Serial.print(mic_level, 1);    Serial.print(",");
  Serial.print(bat_voltage, 3);  Serial.print(",");
  Serial.println(bat_percent);   // println aggiunge \n alla fine della riga

  delay(100);  // 10 campioni al secondo
}