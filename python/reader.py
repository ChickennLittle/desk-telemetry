# ==============================================================================
# reader.py
# Scopo: ricevere i dati CSV dalla board o dal simulatore e renderli
# utilizzabili dal resto del sistema.
#
# Formato CSV atteso: timestamp,temperatura,acc_x,acc_y,acc_z
# Esempio:            58182,39.84,0.023,-0.085,1.007
#
# Uso:
#   python reader.py --port COM3                          (board reale)
#   python simulator.py | python -u reader.py --stdin     (simulatore)
# ==============================================================================

import sys
import argparse
from dataclasses import dataclass
# ↑ Ricorda: dataclass genera automaticamente __init__ e altri metodi
#   per una classe che contiene solo dati — come una struct in C++.


# --- STRUTTURA DATI -----------------------------------------------------------

@dataclass
class Sample:
    """
    Rappresenta un singolo campione di telemetria ricevuto dalla board.

    Ogni campo corrisponde a un valore nel CSV:
        timestamp,temperatura,acc_x,acc_y,acc_z
        58182,    39.84,      0.023,-0.085,1.007

    Usare una dataclass invece di una tupla (58182, 39.84, 0.023, ...)
    rende il codice molto più leggibile: sample.acc_z invece di sample[4].
    """
    timestamp:   int    # millisecondi dall'accensione della board (millis())
                        # int perché millis() restituisce un intero, non un float
    temperature: float  # °C — temperatura interna del chip IMU (non ambientale)
    acc_x:       float  # accelerazione asse X in unità g (g = 9.81 m/s²)
    acc_y:       float  # accelerazione asse Y in unità g
    acc_z:       float  # accelerazione asse Z in unità g
                        # a board ferma e piatta: x≈0, y≈0, z≈1.0 (gravità)


# --- PARSING ------------------------------------------------------------------

def parse_line(line: str) -> Sample | None:
    """
    Converte una riga di testo CSV in un oggetto Sample.
    Restituisce None se la riga non è valida (commento, vuota, formato errato).

    Questa funzione è separata dalla logica di lettura per un motivo preciso:
    se domani cambiamo il protocollo (es. da CSV a JSON), modifichiamo solo
    questa funzione — tutto il resto del codice rimane invariato.
    """

    # strip() rimuove spazi e newline all'inizio e alla fine.
    # Necessario perché readline() dalla seriale include '\n' o '\r\n'.
    line = line.strip()

    # Righe vuote e commenti (iniziano con #) vengono ignorati.
    # "not line" è True se la stringa è vuota — in Python le stringhe vuote
    # sono "falsy": si comportano come False in un contesto booleano.
    if not line or line.startswith("#"):
        return None

    # split(",") divide la stringa su ogni virgola e restituisce una lista.
    # "58182,39.84,0.023,-0.085,1.007".split(",")
    # → ["58182", "39.84", "0.023", "-0.085", "1.007"]
    parts = line.split(",")

    # Controlliamo di avere esattamente 5 campi.
    # Il firmware precedente ne mandava 3, ora ne manda 5.
    # Se arriva ancora una riga vecchia a 3 campi, la ignoriamo.
    if len(parts) != 5:
        return None

    # try/except per gestire errori di conversione numerica.
    # int("abc") o float("xyz") lancerebbero un ValueError.
    # Lo intercettiamo e restituiamo None invece di far crashare il programma.
    try:
        return Sample(
            timestamp=int(parts[0]),      # int() converte stringa in intero
            temperature=float(parts[1]),  # float() converte stringa in decimale
            acc_x=float(parts[2]),
            acc_y=float(parts[3]),
            acc_z=float(parts[4]),
        )
    except ValueError:
        # La riga conteneva qualcosa che non è un numero — ignoriamo silenziosamente.
        return None


# --- SORGENTI DATI ------------------------------------------------------------
# Le due funzioni qui sotto sono GENERATORI — usano yield invece di return.
#
# Un generatore produce valori uno alla volta su richiesta, senza costruire
# una lista intera in memoria. Per la lettura seriale (potenzialmente infinita)
# è la scelta naturale: non puoi mai costruire una lista infinita, ma puoi
# produrre un elemento alla volta per sempre.
#
# Entrambe le funzioni hanno la stessa "interfaccia" — producono oggetti Sample
# uno alla volta. Il codice che le usa (main, dashboard) non sa né gli importa
# quale delle due sta usando. Questo è il principio dei tre strati separati.

def read_from_stdin():
    """
    Generatore: legge campioni da stdin.
    Usato quando il simulatore è collegato via pipe:
        python -u simulator.py | python -u reader.py --stdin
    """
    print("Lettura da stdin...", file=sys.stderr)
    # sys.stdin in un pipe riceve quello che il processo precedente
    # ha scritto su stdout. "for line in sys.stdin" legge una riga
    # alla volta, bloccandosi ad aspettare se non ci sono righe disponibili.
    for line in sys.stdin:
        sample = parse_line(line)
        # Yieldiamo solo se parse_line ha restituito un Sample valido (non None).
        # "if sample" è True per qualsiasi oggetto non-None.
        if sample:
            yield sample
            # ↑ yield sospende la funzione qui e restituisce sample al chiamante.
            #   Al prossimo giro del for esterno, riprende dalla riga dopo yield.


def read_from_serial(port: str, baudrate: int = 115200):
    """
    Generatore: legge campioni dalla porta seriale reale (board collegata).
    Richiede: pip install pyserial

    Args:
        port:     nome porta, es. 'COM3' su Windows, '/dev/ttyUSB0' su Linux
        baudrate: velocità di comunicazione — deve coincidere col firmware (115200)
    """
    # Import locale: importiamo pyserial solo se questa funzione viene chiamata.
    # Se l'utente usa --stdin, non ha bisogno di pyserial installato.
    try:
        import serial
    except ImportError:
        print("Errore: pyserial non installato.", file=sys.stderr)
        print("Esegui: py -3.12 -m pip install pyserial", file=sys.stderr)
        sys.exit(1)

    print(f"Connessione a {port} @ {baudrate} baud...", file=sys.stderr)

    # "with serial.Serial(...) as ser:" è il context manager di Python.
    # Garantisce che la porta seriale venga chiusa automaticamente alla fine,
    # anche se si verifica un'eccezione. Equivale a try/finally in C++.
    with serial.Serial(port, baudrate, timeout=1) as ser:
        print("Connesso. In ascolto...", file=sys.stderr)
        while True:
            try:
                # readline() legge fino al prossimo '\n' dalla seriale.
                # decode("utf-8") converte i bytes ricevuti in stringa Python.
                # errors="replace" sostituisce caratteri non validi invece di crashare.
                raw = ser.readline().decode("utf-8", errors="replace")
                sample = parse_line(raw)
                if sample:
                    yield sample
            except serial.SerialException as e:
                # SerialException viene lanciata se la board viene scollegata.
                print(f"Errore seriale: {e}", file=sys.stderr)
                break  # esce dal while, il generatore termina


# --- FUNZIONE PRINCIPALE ------------------------------------------------------

def main():
    # argparse gestisce gli argomenti da riga di comando.
    # Permette di scrivere: python reader.py --port COM3
    # e di accedere ai valori con args.port, args.stdin, args.baudrate.
    parser = argparse.ArgumentParser(description="Desk Telemetry Reader")

    # add_mutually_exclusive_group: solo uno dei due argomenti può essere usato.
    # required=True: almeno uno è obbligatorio.
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--port",  help="Porta seriale, es. COM3")
    group.add_argument("--stdin", action="store_true",
                       help="Leggi da stdin (simulatore via pipe)")
    # action="store_true": --stdin non richiede un valore, è un flag on/off.
    # Se presente → args.stdin == True. Se assente → args.stdin == False.

    parser.add_argument("--baudrate", type=int, default=115200,
                        help="Baud rate (default: 115200)")

    args = parser.parse_args()

    # Scegliamo la sorgente in base all'argomento.
    # Entrambe producono oggetti Sample — il for sotto è identico in entrambi i casi.
    if args.stdin:
        source = read_from_stdin()
    else:
        source = read_from_serial(args.port, args.baudrate)

    # Loop principale: stampa ogni campione formattato.
    # Il segno + in {:+.3f} forza la stampa del segno anche per i positivi
    # (es. +0.023 invece di 0.023) — utile per l'accelerometro dove il segno
    # indica la direzione.
    for sample in source:
        print(
            f"t={sample.timestamp:7d}ms  "
            f"T={sample.temperature:5.2f}°C  "
            f"X={sample.acc_x:+.3f}g  "
            f"Y={sample.acc_y:+.3f}g  "
            f"Z={sample.acc_z:+.3f}g"
        )


# Entry point — il programma parte da qui solo se eseguito direttamente.
# Se importato da dashboard.py, main() non viene chiamata automaticamente.
if __name__ == "__main__":
    main()