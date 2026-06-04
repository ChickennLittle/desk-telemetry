# Desk Telemetry

Progetto per acquisire e visualizzare i dati dei sensori di una dev board (M5Stack CoreS3).
Usato anche per riprendere familiarità con lo sviluppo embedded + Python.

## Architettura

```
[Firmware C++]  →  [Seriale USB]  →  [Python host]
  Legge sensori     Protocollo CSV    Riceve e visualizza
```

I tre strati sono indipendenti: si possono sviluppare e testare separatamente.

## Struttura del progetto

```
desk-telemetry/
├── firmware/          # Codice C++ per la board (PlatformIO)
│   └── src/
│       └── main.cpp
├── python/
│   ├── simulator.py   # Simula la board via porta seriale virtuale
│   ├── reader.py      # Legge i dati (reali o dal simulatore)
│   └── dashboard.py   # Visualizza i dati
└── README.md
```

## Sensori acquisiti

| Campo       | Unità | Descrizione                        |
|-------------|-------|------------------------------------|
| temperature | °C    | Temperatura ambiente               |
| vibration   | 0–1   | Intensità vibrazione (normalizzata)|
| load        | %     | Carico generico (es. CPU, peso)    |

## Protocollo seriale

I dati vengono inviati in formato CSV su una riga:

```
22.4,0.53,67.2\n
```

Baud rate: `115200`

## Setup

### Firmware (PlatformIO)
```bash
cd firmware
pio run --target upload
```

### Python
```bash
cd python
pip install pyserial
python reader.py        # con board collegata
python simulator.py     # senza board
```

## Stato del progetto

- [x] Setup ambiente (VS Code, PlatformIO, Git)
- [x] Firmware base con simulazione sensori
- [x] Script Python di lettura seriale
- [ ] Simulatore seriale virtuale
- [ ] Dashboard stabile
- [ ] Test con hardware reale (M5Stack CoreS3)

## Hardware target

- **M5Stack CoreS3** — board principale
- Connessione via USB seriale al PC