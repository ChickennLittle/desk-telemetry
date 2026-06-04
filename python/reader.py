# ==============================================================================
# reader.py
# Scopo: ricevere i dati CSV dalla board e convertirli in oggetti Sample.
#
# Formato CSV atteso (14 campi):
#   timestamp,temp,acc_x,acc_y,acc_z,gyr_x,gyr_y,gyr_z,mag_x,mag_y,mag_z,mic,bat_v,bat_pct
#
# Uso:
#   python reader.py --port COM3
#   python -u simulator.py | python -u reader.py --stdin
# ==============================================================================

import sys
import argparse
from dataclasses import dataclass


# --- STRUTTURA DATI -----------------------------------------------------------

@dataclass
class Sample:
    """
    Rappresenta un singolo campione di telemetria completo.
    Ogni campo corrisponde a un valore nel CSV.

    Usare una dataclass invece di una tupla rende il codice leggibile:
    sample.gyr_z invece di sample[7].
    """
    timestamp:   int    # ms dall'accensione della board (millis())

    # IMU — accelerometro
    temperature: float  # °C — temperatura interna chip IMU
    acc_x:       float  # accelerazione asse X (g)
    acc_y:       float  # accelerazione asse Y (g)
    acc_z:       float  # accelerazione asse Z (g) — ≈1.0 a board ferma

    # IMU — giroscopio
    # Misura la velocità di rotazione in gradi al secondo.
    # A board ferma: tutti e tre vicini a 0.
    # Se ruoti la board: il valore sull'asse corrispondente cambia.
    gyr_x:       float  # velocità angolare asse X (°/s)
    gyr_y:       float  # velocità angolare asse Y (°/s)
    gyr_z:       float  # velocità angolare asse Z (°/s)

    # IMU — magnetometro
    # Misura il campo magnetico in microtesla (µT).
    # Utile come bussola — sensibile a magneti e metalli vicini.
    mag_x:       float  # campo magnetico asse X (µT)
    mag_y:       float  # campo magnetico asse Y (µT)
    mag_z:       float  # campo magnetico asse Z (µT)

    # Microfono
    mic_level:   float  # livello audio RMS normalizzato (0-100)

    # Batteria
    bat_voltage: float  # tensione batteria (V) — tipicamente 3.3-4.2V
    bat_percent: int    # percentuale carica (0-100), -1 se non rilevabile


# --- PARSING ------------------------------------------------------------------

def parse_line(line: str) -> Sample | None:
    """
    Converte una riga CSV in un oggetto Sample.
    Restituisce None se la riga non è valida.
    """
    line = line.strip()

    if not line or line.startswith("#"):
        return None

    parts = line.split(",")

    # 14 campi: timestamp + 13 valori sensori
    if len(parts) != 14:
        return None

    try:
        return Sample(
            timestamp=int(parts[0]),
            temperature=float(parts[1]),
            acc_x=float(parts[2]),
            acc_y=float(parts[3]),
            acc_z=float(parts[4]),
            gyr_x=float(parts[5]),
            gyr_y=float(parts[6]),
            gyr_z=float(parts[7]),
            mag_x=float(parts[8]),
            mag_y=float(parts[9]),
            mag_z=float(parts[10]),
            mic_level=float(parts[11]),
            bat_voltage=float(parts[12]),
            bat_percent=int(parts[13]),
        )
    except ValueError:
        return None


# --- SORGENTI DATI ------------------------------------------------------------
# Entrambe le funzioni sono generatori (yield) — producono un Sample alla volta.
# Il codice chiamante (main, dashboard) non sa quale delle due sta usando.

def read_from_stdin():
    """Generatore: legge campioni da stdin (simulatore via pipe)."""
    print("Lettura da stdin...", file=sys.stderr)
    for line in sys.stdin:
        sample = parse_line(line)
        if sample:
            yield sample


def read_from_serial(port: str, baudrate: int = 115200):
    """
    Generatore: legge campioni dalla porta seriale reale.
    Richiede: pip install pyserial
    """
    try:
        import serial
    except ImportError:
        print("Errore: pyserial non installato.", file=sys.stderr)
        print("Esegui: py -3.12 -m pip install pyserial", file=sys.stderr)
        sys.exit(1)

    print(f"Connessione a {port} @ {baudrate} baud...", file=sys.stderr)

    # "with ... as ser:" — context manager: garantisce che la porta
    # venga chiusa anche in caso di eccezione (equivale a try/finally in C++)
    with serial.Serial(port, baudrate, timeout=1) as ser:
        print("Connesso. In ascolto...", file=sys.stderr)
        while True:
            try:
                raw = ser.readline().decode("utf-8", errors="replace")
                sample = parse_line(raw)
                if sample:
                    yield sample
            except serial.SerialException as e:
                print(f"Errore seriale: {e}", file=sys.stderr)
                break


# --- FUNZIONE PRINCIPALE ------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Desk Telemetry Reader")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--port",  help="Porta seriale, es. COM3")
    group.add_argument("--stdin", action="store_true", help="Leggi da stdin")
    parser.add_argument("--baudrate", type=int, default=115200)
    args = parser.parse_args()

    if args.stdin:
        source = read_from_stdin()
    else:
        source = read_from_serial(args.port, args.baudrate)

    for sample in source:
        print(
            f"t={sample.timestamp:7d}ms | "
            f"T={sample.temperature:5.2f}°C | "
            f"Acc X={sample.acc_x:+.3f} Y={sample.acc_y:+.3f} Z={sample.acc_z:+.3f}g | "
            f"Gyr X={sample.gyr_x:+6.1f} Y={sample.gyr_y:+6.1f} Z={sample.gyr_z:+6.1f}°/s | "
            f"Mag X={sample.mag_x:+7.2f} Y={sample.mag_y:+7.2f} Z={sample.mag_z:+7.2f}µT | "
            f"Mic={sample.mic_level:4.1f} | "
            f"Bat={sample.bat_voltage:.3f}V {sample.bat_percent}%"
        )


if __name__ == "__main__":
    main()