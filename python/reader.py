# ==============================================================================
# reader.py
# Scopo: ricevere i dati CSV dalla board (o dal simulatore) e renderli
# utilizzabili dal resto del sistema (dashboard, log, analisi...).
#
# Supporta due sorgenti intercambiabili:
#   --port COM3      → porta seriale reale (board collegata via USB)
#   --stdin          → stdin (output del simulatore via pipe)
#
# Uso:
#   python simulator.py | python -u reader.py --stdin     (simulatore)
#   python reader.py --port COM3                          (board reale)
# ==============================================================================

import sys
import argparse
# ↑ argparse: modulo standard per gestire gli argomenti da riga di comando.
#   Permette di scrivere: python reader.py --port COM3 --baudrate 115200
#   e di accedere ai valori comodamente nel codice.

from dataclasses import dataclass
# ↑ dataclass: un decoratore che genera automaticamente metodi comuni
#   (__init__, __repr__, ecc.) per una classe che contiene solo dati.
#   È simile a una struct in C++: raggruppa dati correlati con un nome.


# --- STRUTTURA DATI -----------------------------------------------------------
# @dataclass è un "decoratore": una funzione che modifica il comportamento
# della classe che segue. Il @ è la sintassi dei decoratori in Python.
#
# Senza @dataclass dovresti scrivere manualmente:
#   def __init__(self, temperature, vibration, load):
#       self.temperature = temperature
#       self.vibration = vibration
#       self.load = load
# @dataclass lo genera automaticamente per te.

@dataclass
class Sample:
    """
    Rappresenta un singolo campione di telemetria.
    Usare una classe con nomi espliciti invece di una tupla (22.4, 0.53, 67.2)
    rende il codice molto più leggibile: scrivi sample.temperature invece di sample[0].
    """
    temperature: float  # °C  — type annotation del campo
    vibration:   float  # 0.0 – 1.0
    load:        float  # %


# --- PARSING ------------------------------------------------------------------

def parse_line(line: str) -> Sample | None:
    # ↑ "Sample | None" significa: la funzione restituisce un Sample oppure None.
    #   None in Python è l'equivalente di nullptr/null: assenza di valore.
    #   Questo tipo si chiama "Optional" ed è molto comune in Python moderno.
    """
    Converte una riga di testo CSV in un oggetto Sample.
    Restituisce None se la riga non è un dato valido (commento, riga vuota, errore).
    """

    # str.strip() rimuove spazi e newline all'inizio e alla fine della stringa.
    # Serve perché readline() dalla seriale include spesso '\n' o '\r\n' alla fine.
    line = line.strip()

    # Righe vuote o commenti (iniziano con #) vengono ignorati.
    # "not line" è True se la stringa è vuota — in Python le stringhe vuote
    # sono "falsy" (si comportano come False in un contesto booleano).
    if not line or line.startswith("#"):
        return None

    # str.split(",") divide la stringa su ogni virgola e restituisce una LISTA.
    # Esempio: "22.40,0.53,67.20".split(",") → ["22.40", "0.53", "67.20"]
    # Una lista in Python è come un array dinamico: [elem0, elem1, elem2]
    # Si accede agli elementi con l'indice: parts[0], parts[1], parts[2]
    parts = line.split(",")

    # Controlliamo di avere esattamente 3 campi. Se no, la riga è malformata.
    if len(parts) != 3:
        # len() restituisce la lunghezza di una sequenza (lista, stringa, tupla...)
        return None

    # try/except per gestire errori di conversione.
    # float("abc") lancerebbe un ValueError — lo intercettiamo invece di crashare.
    try:
        # Creiamo un'istanza di Sample con i tre valori convertiti in float.
        # float("22.40") → 22.4
        # Stiamo usando i "keyword arguments": passiamo i valori per nome,
        # non per posizione. Rende il codice più chiaro e meno soggetto a errori.
        return Sample(
            temperature=float(parts[0]),
            vibration=float(parts[1]),
            load=float(parts[2]),
        )
    except ValueError:
        # La riga conteneva qualcosa che non è un numero — ignoriamo.
        return None


# --- SORGENTI DATI ------------------------------------------------------------
# Queste due funzioni sono GENERATORI — usano "yield" invece di "return".
#
# Un generatore è una funzione che produce valori uno alla volta, su richiesta,
# invece di calcolarne una lista intera e restituirla tutta.
#
# Esempio con return (lista): calcola tutti i valori, li mette in memoria, li restituisce.
# Esempio con yield (generatore): produce un valore, si ferma, aspetta che
#   qualcuno lo consumi, poi riprende dal punto in cui si era fermato.
#
# Per un loop infinito come la lettura seriale, il generatore è perfetto:
# non potresti mai costruire una lista infinita, ma puoi produrre un elemento
# alla volta per sempre.
#
# Come si usa: "for sample in read_from_stdin(): ..."
# Ogni iterazione del for ottiene il prossimo valore yielded.

def read_from_stdin():
    """
    Generatore: legge campioni da stdin.
    Usato quando il simulatore viene collegato via pipe:
        python simulator.py | python -u reader.py --stdin
    """
    print("Lettura da stdin (simulatore)...", file=sys.stderr)

    # sys.stdin è l'input standard — in un pipe riceve quello che
    # il processo precedente ha scritto su stdout.
    # Iterare su sys.stdin con "for line in sys.stdin" legge una riga alla volta,
    # bloccandosi ad aspettare se non ci sono righe disponibili.
    for line in sys.stdin:
        sample = parse_line(line)

        # Yieldiamo solo se parse_line ha restituito un Sample valido (non None).
        # "if sample" è True per qualsiasi oggetto non-None, non-vuoto.
        if sample:
            yield sample
            # ↑ yield: restituisce sample al chiamante e SOSPENDE la funzione qui.
            #   Al prossimo "next()" del for esterno, riprende dalla riga dopo yield.


def read_from_serial(port: str, baudrate: int = 115200):
    # ↑ baudrate: int = 115200 → parametro con VALORE DEFAULT.
    #   Se non lo passi, usa 115200. Equivale a un parametro opzionale in C++.
    """
    Generatore: legge campioni dalla porta seriale reale.
    Richiede: pip install pyserial
    """

    # Import locale: importiamo pyserial solo se questa funzione viene chiamata.
    # Se l'utente usa --stdin, non ha bisogno di pyserial installato.
    # Questo pattern è utile per dipendenze opzionali.
    try:
        import serial
    except ImportError:
        # ImportError viene lanciato se il modulo non è installato.
        print("Errore: pyserial non installato.", file=sys.stderr)
        print("Esegui: pip install pyserial", file=sys.stderr)
        sys.exit(1)  # 1 = uscita con errore

    print(f"Connessione a {port} @ {baudrate} baud...", file=sys.stderr)

    # "with ... as ser:" è il context manager di Python.
    # Garantisce che ser.close() venga chiamato automaticamente alla fine,
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
                print(f"Errore seriale: {e}", file=sys.stderr)
                break  # esce dal while, termina il generatore

# --- FUNZIONE PRINCIPALE ------------------------------------------------------

def main():
    # Creiamo il parser degli argomenti da riga di comando.
    parser = argparse.ArgumentParser(description="Desk Telemetry Reader")

    # add_mutually_exclusive_group: solo uno dei due argomenti può essere usato.
    # Impedisce di passare sia --port che --stdin contemporaneamente.
    group = parser.add_mutually_exclusive_group(required=True)
    # required=True → almeno uno dei due è obbligatorio.

    group.add_argument("--port",
                       help="Porta seriale, es. COM3 o /dev/ttyUSB0")

    group.add_argument("--stdin",
                       action="store_true",
                       help="Leggi da stdin (output del simulatore)")
    # action="store_true" → se --stdin è presente, args.stdin vale True.
    # Non richiede un valore dopo il flag: scrivi solo --stdin, non --stdin True.

    parser.add_argument("--baudrate",
                        type=int,           # converte l'argomento stringa in int
                        default=115200,     # valore di default se non specificato
                        help="Baud rate seriale (default: 115200)")

    # parse_args() legge sys.argv (gli argomenti passati al comando),
    # li valida e restituisce un oggetto con attributi per ogni argomento.
    args = parser.parse_args()
    # Ora puoi usare: args.port, args.stdin, args.baudrate

    # Scegliamo la sorgente dati in base all'argomento.
    # Entrambe le funzioni sono generatori con la stessa interfaccia:
    # producono oggetti Sample uno alla volta. Il for sotto non sa né gli importa
    # quale delle due sta usando — questo è il principio degli strati separati.
    if args.stdin:
        source = read_from_stdin()
    else:
        source = read_from_serial(args.port, args.baudrate)

    # Loop principale: itera sul generatore e stampa ogni campione.
    # Questo for non terminerà mai da solo (i generatori sono infiniti)
    # — si ferma solo con CTRL+C (KeyboardInterrupt) o se la sorgente si chiude.
    for sample in source:
        # f-string con formattazione:
        # :6.2f → campo largo 6 caratteri, 2 decimali (allinea le colonne)
        # :.2f  → solo 2 decimali, senza larghezza fissa
        print(
            f"T={sample.temperature:6.2f}°C  "
            f"V={sample.vibration:.2f}  "
            f"L={sample.load:5.1f}%"
        )


# Entry point — vedi commento dettagliato in simulator.py
if __name__ == "__main__":
    main()