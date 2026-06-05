#include <Arduino.h>
#include <M5Unified.h>

// ==============================================================================
// main.cpp — Firmware M5Stack CoreS3
// Legge tutti i sensori e mostra i dati sul display integrato.
//
// Struttura del display (320x240):
//   - Header:  titolo + batteria
//   - Sezione valori: temperatura, accelerometro, giroscopio, magnetometro
//   - Sezione barre: accelerazione totale e microfono
//
// Tecnica anti-flickering: usiamo M5Canvas (sprite) come buffer off-screen.
// Disegniamo tutto sul canvas, poi lo copiamo sul display in un colpo solo.
// Senza sprite, ridisegnare ogni 100ms causerebbe uno schianto visibile.
// ==============================================================================

// --- Colori ---
// M5GFX usa colori in formato RGB565 (16 bit).
// TFT_BLACK, TFT_WHITE ecc. sono costanti predefinite della libreria.
#define COL_BG TFT_BLACK
#define COL_HEADER 0x2945 // blu scuro
#define COL_TEXT TFT_WHITE
#define COL_ACCENT 0x07FF // ciano
#define COL_BAR_FG 0x07E0 // verde
#define COL_BAR_BG 0x2104 // grigio scuro
#define COL_WARN 0xFD20   // arancione (batteria bassa)

// --- Dimensioni display ---
#define DISP_W 320
#define DISP_H 240

// --- Dati sensori (variabili globali) ---
float acc_x, acc_y, acc_z;
float gyr_x, gyr_y, gyr_z;
float mag_x, mag_y, mag_z;
float imu_temp;
float mic_level;
float bat_voltage;
int bat_percent;

// --- Canvas (sprite off-screen) ---
// M5Canvas è un buffer in RAM dove disegniamo prima di aggiornare il display.
// Dichiarato globale per non riallocarlo ad ogni loop (spreco di RAM).
M5Canvas canvas(&M5.Display);

// =============================================================================
// FUNZIONI DI DISEGNO
// =============================================================================

// -----------------------------------------------------------------------------
// Disegna una barra orizzontale
//
// Parametri:
//   x, y    = posizione angolo in alto a sinistra
//   w, h    = larghezza e altezza totale della barra
//   value   = valore corrente (0.0 - 1.0, già normalizzato)
//   color   = colore della parte piena
// -----------------------------------------------------------------------------
void drawBar(int x, int y, int w, int h, float value, uint32_t color)
{
  // Clamp: assicuriamo che value sia tra 0 e 1
  // Operatore ternario: condizione ? valore_se_true : valore_se_false
  value = value < 0.0f ? 0.0f : (value > 1.0f ? 1.0f : value);

  // Larghezza della parte piena
  int filled = (int)(value * w);

  // Sfondo grigio per tutta la barra
  canvas.fillRect(x, y, w, h, COL_BAR_BG);

  // Parte piena sovrapposta
  if (filled > 0)
  {
    canvas.fillRect(x, y, filled, h, color);
  }
}

// -----------------------------------------------------------------------------
// Disegna l'header (riga 1)
// Mostra titolo e stato batteria
// -----------------------------------------------------------------------------
void drawHeader()
{
  // Sfondo colorato per l'header
  canvas.fillRect(0, 0, DISP_W, 28, COL_HEADER);

  canvas.setTextColor(COL_ACCENT);
  canvas.setTextSize(1.8f); // dimensione testo — float per dimensioni intermedie
  canvas.setCursor(8, 6);
  canvas.print("DESK TELEMETRY");

  // Colore batteria: arancione se < 20%, bianco altrimenti
  // Operatore ternario — equivale a un if/else in una sola riga
  canvas.setTextColor(bat_percent < 20 ? COL_WARN : COL_TEXT);
  canvas.setCursor(210, 6);
  canvas.printf("BAT:%d%%", bat_percent);
  // ↑ printf su canvas funziona come Serial.printf — formatta e stampa
  //   %% stampa un % letterale (escape)
}

// -----------------------------------------------------------------------------
// Disegna la sezione valori numerici (righe 2-5)
// -----------------------------------------------------------------------------
void drawValues()
{
  canvas.setTextSize(1.5f);

  // --- Temperatura ---
  canvas.setTextColor(COL_ACCENT);
  canvas.setCursor(8, 38);
  canvas.print("TEMP ");
  canvas.setTextColor(COL_TEXT);
  canvas.printf("%.1f C", imu_temp);

  // --- Accelerometro ---
  canvas.setTextColor(COL_ACCENT);
  canvas.setCursor(8, 68);
  canvas.print("ACC  ");
  canvas.setTextColor(COL_TEXT);
  // %+.2f: + forza la stampa del segno, .2f = 2 decimali
  canvas.printf("X%+.2f Y%+.2f Z%+.2f", acc_x, acc_y, acc_z);

  // --- Giroscopio ---
  canvas.setTextColor(COL_ACCENT);
  canvas.setCursor(8, 98);
  canvas.print("GYR  ");
  canvas.setTextColor(COL_TEXT);
  canvas.printf("X%+.1f Y%+.1f Z%+.1f", gyr_x, gyr_y, gyr_z);

  // --- Magnetometro ---
  canvas.setTextColor(COL_ACCENT);
  canvas.setCursor(8, 128);
  canvas.print("MAG  ");
  canvas.setTextColor(COL_TEXT);
  // %.0f = nessun decimale (i valori magnetici sono grandi)
  canvas.printf("X%.0f Y%.0f Z%.0f", mag_x, mag_y, mag_z);
}

// -----------------------------------------------------------------------------
// Disegna la sezione barre grafiche (righe 6-7)
// -----------------------------------------------------------------------------
void drawBars()
{
  // Linea separatrice
  canvas.drawFastHLine(0, 158, DISP_W, COL_HEADER);

  // --- Barra accelerazione totale ---
  // Calcoliamo la magnitudine del vettore accelerazione:
  // |a| = sqrt(ax² + ay² + az²)
  // A board ferma vale circa 1.0g (solo gravità su Z)
  // Sottraiamo 1.0 per avere 0 a riposo, normalizziamo su range 0-2g
  float acc_mag = sqrt(acc_x * acc_x + acc_y * acc_y + acc_z * acc_z);
  float acc_normalized = (acc_mag - 1.0f) / 2.0f;
  // acc_normalized ≈ 0 a riposo, sale se la board viene mossa

  canvas.setTextColor(COL_ACCENT);
  canvas.setTextSize(1.5f);
  canvas.setCursor(8, 166);
  canvas.print("ACC");
  drawBar(52, 168, 210, 14, acc_normalized, COL_BAR_FG);
  canvas.setTextColor(COL_TEXT);
  canvas.setCursor(268, 166);
  canvas.printf("%.2f", acc_mag);

  // --- Barra microfono ---
  float mic_normalized = mic_level / 100.0f;

  canvas.setTextColor(COL_ACCENT);
  canvas.setCursor(8, 196);
  canvas.print("MIC");
  drawBar(52, 198, 210, 14, mic_normalized, COL_BAR_FG);
  canvas.setTextColor(COL_TEXT);
  canvas.setCursor(268, 196);
  canvas.printf("%.0f", mic_level);

  // --- Tensione batteria in fondo ---
  canvas.setTextColor(COL_BAR_BG + 0x2000); // grigio chiaro
  canvas.setTextSize(1.2f);
  canvas.setCursor(8, 222);
  canvas.printf("%.3fV", bat_voltage);
}

// =============================================================================
// SETUP E LOOP
// =============================================================================

void setup()
{
  auto cfg = M5.config();
  M5.begin(cfg);
  Serial.begin(115200);
  M5.Mic.begin();

  // Inizializziamo il canvas con le stesse dimensioni del display
  // createSprite(larghezza, altezza) alloca il buffer in RAM
  canvas.createSprite(DISP_W, DISP_H);

  // Orientamento display orizzontale
  M5.Display.setRotation(1);

  delay(500);
}

void loop()
{
  M5.update();

  // --- Lettura sensori ---
  M5.Imu.getAccelData(&acc_x, &acc_y, &acc_z);
  M5.Imu.getGyroData(&gyr_x, &gyr_y, &gyr_z);
  M5.Imu.getMag(&mag_x, &mag_y, &mag_z);
  M5.Imu.getTemp(&imu_temp);

  int16_t mic_buffer[256];
  mic_level = 0;
  if (M5.Mic.record(mic_buffer, 256, 8000))
  {
    float sum = 0;
    for (int i = 0; i < 256; i++)
    {
      sum += (float)mic_buffer[i] * mic_buffer[i];
    }
    mic_level = (sqrt(sum / 256) / 32768.0f) * 100.0f;
  }

  bat_voltage = M5.Power.getBatteryVoltage() / 1000.0f;
  bat_percent = M5.Power.getBatteryLevel();

  // --- Output seriale (invariato rispetto a prima) ---
  Serial.print(millis());
  Serial.print(",");
  Serial.print(imu_temp, 2);
  Serial.print(",");
  Serial.print(acc_x, 3);
  Serial.print(",");
  Serial.print(acc_y, 3);
  Serial.print(",");
  Serial.print(acc_z, 3);
  Serial.print(",");
  Serial.print(gyr_x, 2);
  Serial.print(",");
  Serial.print(gyr_y, 2);
  Serial.print(",");
  Serial.print(gyr_z, 2);
  Serial.print(",");
  Serial.print(mag_x, 2);
  Serial.print(",");
  Serial.print(mag_y, 2);
  Serial.print(",");
  Serial.print(mag_z, 2);
  Serial.print(",");
  Serial.print(mic_level, 1);
  Serial.print(",");
  Serial.print(bat_voltage, 3);
  Serial.print(",");
  Serial.println(bat_percent);

  // --- Disegno display ---
  // Puliamo il canvas con il colore di sfondo
  canvas.fillSprite(COL_BG);

  // Disegniamo le tre sezioni sul canvas (buffer in RAM)
  drawHeader();
  drawValues();
  drawBars();

  // pushSprite(x, y) copia il canvas sul display in un colpo solo
  // Questo è il momento in cui il display si aggiorna — una sola scrittura
  // invece di tante piccole scritture che causerebbero flickering
  canvas.pushSprite(0, 0);

  delay(100);
}