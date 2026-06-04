# Desk Telemetry

Progetto per acquisire, visualizzare e registrare i dati dei sensori di una dev board (M5Stack CoreS3).
Usato anche per riprendere familiarità con lo sviluppo embedded + Python.

## Architettura

```
[Firmware C++]  →  [Seriale USB]  →  [Python host]
  Legge sensori     Protocollo CSV    Riceve, visualizza, salva
```

I tre strati sono indipendenti: si possono sviluppare e testare separatamente.
Il simulatore permette di lavorare senza hardware collegato.

## Struttura del progetto

```
desk-telemetry/
├── firmware/
│   └── src/
│       ├── main.cpp               # Firmware attivo — sensori reali
│       └── main_simulated.cpp.bak # Firmware simulato (archiviato)
├── python/
│   ├── simulator.py   # Simula la board — genera dati CSV realistici
│   ├── reader.py      # Legge e parsea i dati (seriale o stdin)
│   ├── dashboard.py   # Visualizzazione in tempo reale (pyqtgraph)
│   └── logger.py      # Salvataggio dati su file CSV
└── README.md
```

## Sensori acquisiti

| Campo         | Unità  | Descrizione                              |
|---------------|--------|------------------------------------------|
| timestamp     | ms     | Millisecondi dall'accensione (millis())  |
| temperature   | °C     | Temperatura interna chip IMU             |
| acc_x/y/z     | g      | Accelerometro (g = 9.81 m/s²)            |
| gyr_x/y/z     | °/s    | Giroscopio — velocità angolare           |
| mag_x/y/z     | µT     | Magnetometro — campo magnetico           |
| mic_level     | 0–100  | Livello audio RMS normalizzato           |
| bat_voltage   | V      | Tensione batteria                        |
| bat_percent   | %      | Percentuale carica batteria              |

## Protocollo seriale

I dati vengono inviati in formato CSV su una riga ogni 100ms:

```
timestamp,temp,acc_x,acc_y,acc_z,gyr_x,gyr_y,gyr_z,mag_x,mag_y,mag_z,mic,bat_v,bat_pct
25316,41.33,-0.003,-0.009,1.010,-0.24,0.24,-0.37,-181.14,335.21,93.12,0.1,4.154,99
```

Baud rate: `115200`

## Setup

### Requisiti

- Python 3.12
- PlatformIO (estensione VS Code)

```bash
py -3.12 -m pip install pyserial pyqtgraph PyQt6
```

### Firmware (PlatformIO)

```bash
cd firmware
pio run --target upload
```

### Python — con board collegata

```cmd
py -3.12 dashboard.py --port COM3
py -3.12 logger.py --port COM3 --output sessione1.csv
```

### Python — senza board (simulatore)

```cmd
# Visualizzazione
py -3.12 -u simulator.py | py -3.12 -u dashboard.py --stdin

# Registrazione
py -3.12 -u simulator.py | py -3.12 -u logger.py --stdin --max-samples 500

# Solo lettura testuale
py -3.12 -u simulator.py | py -3.12 -u reader.py --stdin
```

> **Nota Windows**: usare sempre Command Prompt (cmd), non PowerShell.
> Aprire il terminale con tasto destro sulla cartella `python/` in VS Code → "Open in Integrated Terminal".

## Note tecniche

**Toolchain**: `espressif32@6.9.0` — versione necessaria per compatibilità con il toolchain xtensa su Windows.

**M5Unified**: versione `^0.2.4` — versioni più recenti hanno incompatibilità con il framework corrente.

**Magnetometro**: i valori assoluti variano in base all'ambiente (metalli, cavi vicini). Utile per rilevare variazioni relative, non come bussola assoluta senza calibrazione.

**Microfono**: i primi campioni dopo l'accensione possono essere 0 — normale durante l'inizializzazione hardware.

## Stato del progetto

- [x] Setup ambiente (VS Code, PlatformIO, Git, Python 3.12)
- [x] Firmware con sensori reali (IMU, giroscopio, magnetometro, microfono, batteria)
- [x] Simulatore Python con dati realistici
- [x] Reader con parsing robusto
- [x] Dashboard in tempo reale (pyqtgraph)
- [x] Logger CSV con timestamp automatico
- [ ] Analisi dati con pandas
- [ ] Display integrato CoreS3
- [ ] Calibrazione magnetometro

## Hardware

- **M5Stack CoreS3** — ESP32-S3, 240MHz, 16MB Flash
- Connessione via USB-C seriale al PC (driver CH9102)