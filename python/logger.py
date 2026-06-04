# ==============================================================================
# logger.py
# Scopo: salvare i dati di telemetria su file CSV per analisi successive.
#
# Può essere usato in due modi:
#   1. Da solo — salva i dati su file senza mostrare nulla
#   2. Insieme al dashboard — i dati vengono sia visualizzati che salvati
#
# Il file CSV salvato può essere aperto con Excel, analizzato con pandas,
# o importato in qualsiasi strumento di analisi dati.
#
# Uso:
#   py -3.12 logger.py --port COM3 --output dati.csv
#   py -3.12 -u simulator.py | py -3.12 -u logger.py --stdin --output dati.csv
# ==============================================================================

import sys
import argparse
import csv
# ↑ csv: modulo standard Python per leggere e scrivere file CSV.
#   Gestisce automaticamente virgolette, caratteri speciali, separatori.
#   Molto più robusto che scrivere le virgole a mano con f-string.

from datetime import datetime
# ↑ datetime: modulo standard per lavorare con date e orari.
#   datetime.now() restituisce la data e l'ora corrente del PC.
#   Utile per dare nomi univoci ai file di log.

from pathlib import Path
# ↑ pathlib: modulo moderno per lavorare con i percorsi file.
#   Path è più comoda e leggibile di os.path (il vecchio modo).
#   Path("cartella") / "file.csv" costruisce un percorso in modo sicuro
#   su qualsiasi sistema operativo (Windows, Linux, macOS).

from reader import Sample, parse_line, read_from_stdin, read_from_serial


# --- INTESTAZIONE CSV ---------------------------------------------------------
# La prima riga del file CSV contiene i nomi delle colonne.
# Corrisponde esattamente ai campi della dataclass Sample.
CSV_HEADER = [
    "timestamp_ms",
    "temperature_c",
    "acc_x_g", "acc_y_g", "acc_z_g",
    "gyr_x_dps", "gyr_y_dps", "gyr_z_dps",
    "mag_x_ut", "mag_y_ut", "mag_z_ut",
    "mic_level",
    "bat_voltage_v", "bat_percent"
]
# Nota: i nomi includono le unità di misura (es. _g per g, _dps per °/s,
# _ut per µT). Quando riaprirai il file tra settimane non dovrai ricordare
# cosa significava ogni colonna.


def sample_to_row(sample: Sample) -> list:
    """
    Converte un oggetto Sample in una lista di valori per il CSV.
    L'ordine deve corrispondere esattamente a CSV_HEADER.

    Args:
        sample: oggetto Sample da convertire

    Returns:
        lista di valori pronti da scrivere nel CSV
    """
    # Restituiamo una lista — csv.writer scriverà ogni elemento come una cella
    return [
        sample.timestamp,
        round(sample.temperature, 2),
        round(sample.acc_x, 4),
        round(sample.acc_y, 4),
        round(sample.acc_z, 4),
        round(sample.gyr_x, 3),
        round(sample.gyr_y, 3),
        round(sample.gyr_z, 3),
        round(sample.mag_x, 2),
        round(sample.mag_y, 2),
        round(sample.mag_z, 2),
        round(sample.mic_level, 2),
        round(sample.bat_voltage, 3),
        sample.bat_percent,
    ]
    # round(valore, decimali) arrotonda al numero di decimali specificato.
    # Non è strettamente necessario — ma rende il CSV più leggibile
    # evitando valori come 0.023000000000000001 (errori floating point).


def generate_filename() -> str:
    """
    Genera un nome file con timestamp per evitare sovrascritture.
    Esempio: telemetry_20260604_143215.csv

    Returns:
        stringa con il nome del file
    """
    # datetime.now() restituisce un oggetto datetime con data e ora correnti
    # strftime() formatta la data come stringa secondo il pattern fornito:
    #   %Y = anno a 4 cifre (2026)
    #   %m = mese a 2 cifre (06)
    #   %d = giorno a 2 cifre (04)
    #   %H = ora in formato 24h (14)
    #   %M = minuti (32)
    #   %S = secondi (15)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"telemetry_{now}.csv"


def main():
    parser = argparse.ArgumentParser(description="Desk Telemetry Logger")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--port",  help="Porta seriale, es. COM3")
    group.add_argument("--stdin", action="store_true", help="Leggi da stdin")
    parser.add_argument("--baudrate", type=int, default=115200)

    # --output è opzionale: se non specificato, genera un nome automatico
    parser.add_argument(
        "--output",
        help="Nome file CSV di output (default: telemetry_DATA_ORA.csv)",
        default=None
    )

    # --max-samples: quanti campioni salvare prima di fermarsi
    # Se non specificato, registra finché non premi CTRL+C
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Numero massimo di campioni da salvare (default: illimitato)"
    )

    args = parser.parse_args()

    # Determiniamo il nome del file output
    # "if args.output is not None" — è None se l'utente non ha passato --output
    output_path = Path(args.output) if args.output else Path(generate_filename())

    # Scegliamo la sorgente dati
    if args.stdin:
        source = read_from_stdin()
    else:
        source = read_from_serial(args.port, args.baudrate)

    # Apriamo il file CSV per la scrittura
    # "with open(...) as f:" — context manager: chiude il file automaticamente
    # mode="w"      → scrittura (crea il file, sovrascrive se esiste)
    # newline=""    → necessario su Windows per evitare righe vuote nel CSV
    # encoding="utf-8" → standard moderno, compatibile con Excel e tutto il resto
    print(f"Registrazione su: {output_path}", file=sys.stderr)
    print("CTRL+C per fermare.", file=sys.stderr)

    samples_count = 0  # contatore campioni salvati

    try:
        with open(output_path, mode="w", newline="", encoding="utf-8") as f:

            # csv.writer gestisce la formattazione CSV automaticamente
            writer = csv.writer(f)

            # Scriviamo l'intestazione come prima riga
            writer.writerow(CSV_HEADER)

            # Loop principale di registrazione
            for sample in source:
                writer.writerow(sample_to_row(sample))

                # flush() forza la scrittura su disco ad ogni campione.
                # Senza flush, i dati resterebbero in memoria e andrebbero
                # persi se il programma venisse interrotto bruscamente.
                # È più lento, ma per la telemetria la sicurezza è prioritaria.
                f.flush()

                samples_count += 1

                # Stampiamo un aggiornamento ogni 100 campioni (ogni 10 secondi)
                # "%" è l'operatore modulo — resto della divisione intera
                # samples_count % 100 == 0 è True ogni 100 campioni
                if samples_count % 100 == 0:
                    print(
                        f"Campioni salvati: {samples_count} | "
                        f"t={sample.timestamp}ms",
                        file=sys.stderr
                    )

                # Se --max-samples è specificato, fermiamoci quando lo raggiungiamo
                if args.max_samples and samples_count >= args.max_samples:
                    print(f"\nRaggiunto il limite di {args.max_samples} campioni.",
                          file=sys.stderr)
                    break

    except KeyboardInterrupt:
        pass  # "pass" in Python significa "non fare nulla" — usciamo puliti

    # Questo blocco viene eseguito sempre, anche dopo CTRL+C
    print(f"\nRegistrazione completata.", file=sys.stderr)
    print(f"Campioni salvati: {samples_count}", file=sys.stderr)
    print(f"File: {output_path.resolve()}", file=sys.stderr)
    # Path.resolve() restituisce il percorso assoluto completo del file
    # così sai esattamente dove trovarlo


if __name__ == "__main__":
    main()