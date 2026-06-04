# ==============================================================================
# simulator.py
# Scopo: generare dati finti che imitano quelli che manderebbe la board.
# Così possiamo sviluppare e testare il resto del sistema senza hardware.
# ==============================================================================


# --- IMPORT -------------------------------------------------------------------
# In Python, "import" carica moduli: librerie di funzioni già pronte.
# Non devi scrivere tutto da zero, usi quello che esiste.

import time       # Modulo standard: funzioni legate al tempo (sleep, ecc.)
import math       # Modulo standard: funzioni matematiche (sin, cos, sqrt, ecc.)
import random     # Modulo standard: generazione di numeri casuali
import sys        # Modulo standard: interazione col sistema operativo
                  # (argv, stdin, stdout, stderr, exit...)

# Nota: questi quattro moduli sono "standard library" — vengono con Python,
# non devi installarli. Esistono anche moduli esterni (es. pyserial, numpy)
# che invece si installano con: pip install <nome_modulo>


# --- FUNZIONI -----------------------------------------------------------------
# In Python le funzioni si definiscono con "def nome(parametri):"
# Il corpo della funzione è INDENTATO (4 spazi). L'indentazione NON è
# solo stile: è sintassi. Se sbagli l'indentazione, il codice non funziona.
# Questo è diverso dal C++ dove si usano le parentesi graffe { }.

def generate_data(t: float) -> tuple[float, float, float]:
    # ↑ Questa è la "type annotation" (firma della funzione):
    #   - t: float   → il parametro t è un numero decimale
    #   - -> tuple[float, float, float]  → la funzione restituisce
    #     una tupla di 3 float (simile a una struct in C++)
    # Le type annotation in Python sono OPZIONALI — il codice funziona
    # anche senza, ma le aggiungiamo perché rendono il codice più leggibile
    # e gli editor come VS Code possono aiutarti meglio.

    """
    Genera un campione di dati simulati al tempo t.
    Questa è una "docstring": una stringa di documentazione della funzione.
    Appare quando chiami help(generate_data) nel terminale Python.
    """

    # Stessa formula del firmware C++ — così i dati simulati sono identici
    # a quelli reali. math.sin() lavora in radianti, come in C++.
    temperature = 23.0 + math.sin(t) * 2.0
    #             ↑ valore base (23°C) + oscillazione sinusoidale ±2°C

    vibration = random.randint(0, 100) / 100.0
    #           ↑ random.randint(a, b) genera un intero casuale tra a e b inclusi
    #             dividiamo per 100.0 per ottenere un float tra 0.0 e 1.0
    #             Nota: in Python "/" è sempre divisione float, "//" è intera

    load = 50.0 + math.sin(t * 0.5) * 20.0
    #     ↑ oscillazione più lenta (frequenza dimezzata rispetto a temperature)

    # "return" restituisce i valori al chiamante.
    # Restituire più valori separati da virgola crea automaticamente una TUPLA.
    # Una tupla è una sequenza immutabile: (22.4, 0.53, 67.2)
    # Immutabile = non puoi modificarla dopo averla creata (a differenza delle liste).
    return temperature, vibration, load


# --- FUNZIONE PRINCIPALE ------------------------------------------------------

def main():
    # Variabile locale: esiste solo dentro questa funzione.
    # In Python non devi dichiarare il tipo — Python lo capisce da solo
    # (questo si chiama tipizzazione dinamica).
    t = 0.0
    interval = 0.2  # secondi tra un campione e l'altro (= delay(200) del firmware)

    # sys.stderr è lo "standard error": un canale di output separato da stdout.
    # stdout  → i dati veri (temperature, vibrazione, carico)
    # stderr  → messaggi informativi, errori, log
    # Tenerli separati è importante: quando fai il pipe ( | ) tra due script,
    # solo stdout viene passato al secondo script. I messaggi su stderr
    # appaiono nel terminale senza interferire coi dati.
    print("# Desk Telemetry Simulator avviato", file=sys.stderr)
    print("# Formato: temperature,vibration,load", file=sys.stderr)
    print("# CTRL+C per fermare", file=sys.stderr)

    # try / except: gestione delle eccezioni (errori a runtime).
    # Equivalente concettuale del try/catch in C++.
    # KeyboardInterrupt è l'eccezione lanciata da Python quando premi CTRL+C.
    try:
        # "while True" è un loop infinito — va avanti finché non lo interrompi.
        # In C++ scriveresti: while(true) { ... }
        while True:
            # Chiamiamo generate_data e "spacchettamo" la tupla restituita
            # direttamente in tre variabili. Questo si chiama "unpacking".
            # Equivale a:
            #   result = generate_data(t)
            #   temp = result[0]
            #   vib  = result[1]
            #   load = result[2]
            temp, vib, load = generate_data(t)

            # f-string: modo moderno per formattare stringhe in Python.
            # Sintassi: f"testo {variabile:.2f} altro testo"
            # :.2f  → formato float con 2 decimali (come printf("%.2f") in C)
            line = f"{temp:.2f},{vib:.2f},{load:.2f}"

            # print() stampa su stdout di default.
            # flush=True forza Python a scrivere immediatamente senza bufferizzare.
            # Senza flush=True, Python potrebbe accumulare più righe in memoria
            # prima di scriverle — il reader non riceverebbe nulla per secondi.
            try:
                print(line, flush=True)
            except OSError:
                # Questo blocco viene eseguito se il reader chiude la pipe
                # (es. se il processo che legge i dati termina).
                print("\n# Pipe chiusa dal reader. Simulatore fermato.", file=sys.stderr)
                sys.exit(0)  # termina il programma senza errori
            t += 0.1        # avanziamo il tempo (come t += 0.1 nel firmware)
            time.sleep(interval)  # aspettiamo 200ms prima del prossimo campione

    except KeyboardInterrupt:
        # Questo blocco viene eseguito SOLO quando premi CTRL+C.
        # \n stampa una riga vuota (il cursore è sulla stessa riga del ^C).
        print("\n# Simulatore fermato.", file=sys.stderr)
        sys.exit(0)  # termina il programma. 0 = uscita senza errori (come in C)


# --- ENTRY POINT --------------------------------------------------------------
# Questo è un idioma fondamentale di Python che troverai in ogni script.
#
# Quando Python esegue un file imposta la variabile speciale __name__.
#   - Se lanci direttamente "python simulator.py"  → __name__ == "__main__"
#   - Se un altro script fa "import simulator"     → __name__ == "simulator"
#
# Il controllo qui sotto fa sì che main() venga chiamata solo nel primo caso.
# Questo permette ad altri script di importare generate_data() da questo file
# senza avviare il loop infinito del simulatore.
#
# È buona pratica metterlo sempre alla fine di ogni script Python.
if __name__ == "__main__":
    main()