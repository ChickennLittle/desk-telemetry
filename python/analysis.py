# ==============================================================================
# analysis.py
# Scopo: analizzare i dati di telemetria salvati dal logger.
#
# Produce tre sezioni di analisi:
#   1. Statistiche descrittive per ogni sensore
#   2. Matrice di correlazione tra sensori
#   3. Rilevamento anomalie con regola 3-sigma
#
# Uso:
#   py -3.12 analysis.py --input sessione1.csv
#   py -3.12 analysis.py --input sessione1.csv --plot
# ==============================================================================

import argparse
import sys

import pandas as pd
# ↑ pandas: la libreria principale per analisi dati in Python.
#   Introduce il DataFrame — una tabella di dati con righe e colonne nominate.
#   Simile concettualmente a un foglio Excel, ma programmabile.
#   Ogni colonna è una Serie (array con indice), ogni riga è un campione.

import matplotlib.pyplot as plt
# ↑ matplotlib: libreria per grafici statici.
#   Qui la usiamo per visualizzare i risultati dell'analisi.
#   Diverso da pyqtgraph (tempo reale) — matplotlib è pensato per
#   grafici da salvare o esaminare offline.

import numpy as np
# ↑ numpy: libreria per calcolo numerico veloce.
#   pandas usa numpy internamente — noi lo usiamo per alcune operazioni
#   matematiche (es. np.abs per il valore assoluto di un array intero).


# --- COSTANTI -----------------------------------------------------------------

# Colonne che rappresentano sensori fisici — escludiamo timestamp e batteria
# dall'analisi delle correlazioni perché non sono grandezze fisiche continue
SENSOR_COLUMNS = [
    "temperature_c",
    "acc_x_g", "acc_y_g", "acc_z_g",
    "gyr_x_dps", "gyr_y_dps", "gyr_z_dps",
    "mag_x_ut", "mag_y_ut", "mag_z_ut",
    "mic_level",
]

# Soglia per le anomalie: quante deviazioni standard dalla media
# 3 è il valore standard industriale — copre il 99.7% dei valori normali
ANOMALY_THRESHOLD = 3.0


# --- FUNZIONI DI ANALISI ------------------------------------------------------

def load_data(filepath: str) -> pd.DataFrame:
    """
    Carica il file CSV in un DataFrame pandas.

    pd.read_csv() legge il file e crea automaticamente le colonne
    dai nomi nell'intestazione (prima riga del CSV).

    Args:
        filepath: percorso del file CSV

    Returns:
        DataFrame con i dati del file
    """
    print(f"Caricamento: {filepath}")

    # pd.read_csv() è l'equivalente di aprire un file CSV e leggerlo riga per riga,
    # ma in una sola istruzione e molto più veloce (usa C internamente).
    df = pd.read_csv(filepath)

    # Informazioni di base sul dataset
    # df.shape restituisce una tupla (righe, colonne) — come size() in C++
    print(f"Campioni caricati: {df.shape[0]}")
    print(f"Colonne:           {df.shape[1]}")

    # Durata della sessione in secondi
    # df["timestamp_ms"] accede alla colonna "timestamp_ms" come una Serie.
    # .max() e .min() sono metodi della Serie — trovano il massimo e minimo.
    duration_s = (df["timestamp_ms"].max() - df["timestamp_ms"].min()) / 1000
    print(f"Durata sessione:   {duration_s:.1f} secondi")
    print()

    return df


def print_statistics(df: pd.DataFrame):
    """
    Stampa le statistiche descrittive per ogni sensore.

    Per ogni colonna calcoliamo:
    - mean:  media aritmetica
    - std:   deviazione standard — quanto i valori si discostano dalla media
    - min:   valore minimo
    - max:   valore massimo
    - range: differenza tra max e min

    La deviazione standard è la statistica più informativa per i sensori:
    - std bassa = sensore stabile (es. accelerometro su board ferma)
    - std alta  = sensore con molte variazioni (es. microfono in ambiente rumoroso)
    """
    print("=" * 70)
    print("STATISTICHE DESCRITTIVE")
    print("=" * 70)

    # df[SENSOR_COLUMNS] seleziona solo le colonne dei sensori
    # .describe() calcola automaticamente count, mean, std, min, max, quartili
    stats = df[SENSOR_COLUMNS].describe()

    # Selezioniamo solo le righe che ci interessano da describe()
    # .loc["riga"] accede a una riga per nome — come una mappa in C++
    selected = stats.loc[["mean", "std", "min", "max"]]

    # Arrotondiamo a 4 decimali per leggibilità
    # .round() funziona su tutto il DataFrame in una sola operazione —
    # questo è il "vectorized operation" tipico di pandas: niente for loop
    print(selected.round(4).to_string())

    print()
    print("--- Range di variazione (max - min) ---")
    # Accediamo alle righe di stats per nome e facciamo la differenza
    variation = stats.loc["max"] - stats.loc["min"]
    print(variation.round(4).to_string())
    print()


def print_correlations(df: pd.DataFrame):
    """
    Calcola e stampa la matrice di correlazione tra sensori.

    La correlazione di Pearson misura la relazione lineare tra due variabili:
      +1.0 = correlazione perfetta positiva (crescono insieme)
       0.0 = nessuna correlazione
      -1.0 = correlazione perfetta negativa (uno cresce, l'altro decresce)

    Esempi attesi:
    - acc_x e acc_y: bassa correlazione (movimenti indipendenti)
    - gyr_x e gyr_y: possibile correlazione se la board ruota su più assi
    - temperatura e timestamp: correlazione positiva (chip si scalda nel tempo)
    """
    print("=" * 70)
    print("MATRICE DI CORRELAZIONE")
    print("(valori vicini a +1/-1 = forte correlazione, vicini a 0 = nessuna)")
    print("=" * 70)

    # .corr() calcola la matrice di correlazione di Pearson tra tutte le colonne
    corr_matrix = df[SENSOR_COLUMNS].corr()

    print(corr_matrix.round(2).to_string())
    print()

    # Troviamo le coppie con correlazione più alta (escludendo la diagonale)
    # La diagonale è sempre 1.0 (ogni variabile è perfettamente correlata con sé stessa)
    print("--- Coppie con correlazione più alta (|r| > 0.5) ---")

    found = False
    # .iterrows() itera sulle righe del DataFrame — restituisce (indice, Serie)
    for col1 in SENSOR_COLUMNS:
        for col2 in SENSOR_COLUMNS:
            # Evitiamo di stampare la stessa coppia due volte e la diagonale
            if col1 >= col2:
                continue
            r = corr_matrix.loc[col1, col2]
            # abs() valore assoluto — ci interessa la forza della correlazione,
            # non solo la direzione
            if abs(r) > 0.5:
                direzione = "positiva" if r > 0 else "negativa"
                print(f"  {col1:20s} ↔ {col2:20s}  r={r:+.3f}  ({direzione})")
                found = True

    if not found:
        print("  Nessuna coppia con correlazione forte trovata.")
    print()


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rileva anomalie usando la regola 3-sigma.

    Un campione è anomalo se il suo valore è oltre ANOMALY_THRESHOLD
    deviazioni standard dalla media della sua colonna.

    La regola 3-sigma dice che in una distribuzione normale:
    - 68% dei valori è entro 1 sigma dalla media
    - 95% dei valori è entro 2 sigma dalla media
    - 99.7% dei valori è entro 3 sigma dalla media
    Quindi un valore oltre 3 sigma è statisticamente molto insolito.

    Args:
        df: DataFrame con i dati

    Returns:
        DataFrame con solo le righe anomale, con colonna aggiuntiva "anomaly_in"
    """
    print("=" * 70)
    print(f"RILEVAMENTO ANOMALIE (soglia: {ANOMALY_THRESHOLD} sigma)")
    print("=" * 70)

    # Per ogni colonna calcoliamo media e deviazione standard
    means = df[SENSOR_COLUMNS].mean()
    stds  = df[SENSOR_COLUMNS].std()

    # Calcoliamo il "z-score" per ogni valore:
    # z = (valore - media) / deviazione_standard
    # Un z-score alto significa che il valore è lontano dalla media.
    # (df[SENSOR_COLUMNS] - means) / stds funziona su tutto il DataFrame
    # in una sola operazione — pandas sottrae e divide colonna per colonna.
    z_scores = (df[SENSOR_COLUMNS] - means) / stds

    # np.abs() calcola il valore assoluto di ogni elemento
    # > ANOMALY_THRESHOLD crea una maschera booleana (True/False per ogni cella)
    anomaly_mask = np.abs(z_scores) > ANOMALY_THRESHOLD

    # .any(axis=1) è True per le righe dove ALMENO UNA colonna è anomala
    # axis=1 significa "opera lungo le colonne" (per ogni riga)
    anomalous_rows = anomaly_mask.any(axis=1)

    # Usiamo la maschera per filtrare il DataFrame originale
    # df[maschera_booleana] restituisce solo le righe dove la maschera è True
    anomalies = df[anomalous_rows].copy()

    print(f"Campioni totali:  {len(df)}")
    print(f"Anomalie trovate: {len(anomalies)} "
          f"({100 * len(anomalies) / len(df):.1f}%)")
    print()

    if len(anomalies) > 0:
        # Per ogni anomalia, troviamo quale sensore ha triggato
        print("--- Dettaglio anomalie ---")
        for idx, row in anomalies.head(20).iterrows():
            # Troviamo i sensori anomali in questa riga
            # z_scores.loc[idx] è la riga dei z-score per questo campione
            anomalous_sensors = z_scores.loc[idx][
                np.abs(z_scores.loc[idx]) > ANOMALY_THRESHOLD
            ]
            sensors_str = ", ".join([
                f"{col}={row[col]:.3f} (z={z:.1f})"
                for col, z in anomalous_sensors.items()
            ])
            print(f"  t={row['timestamp_ms']:7.0f}ms → {sensors_str}")

        if len(anomalies) > 20:
            print(f"  ... e altre {len(anomalies) - 20} anomalie")

    print()
    return anomalies


def plot_analysis(df: pd.DataFrame, anomalies: pd.DataFrame):
    """
    Genera grafici statici per visualizzare i dati e le anomalie.

    matplotlib.pyplot è diverso da pyqtgraph:
    - pyqtgraph: aggiornamento in tempo reale, interattivo
    - matplotlib: grafici statici da analizzare o salvare

    fig, axes = plt.subplots(righe, colonne) crea una griglia di grafici.
    """
    print("Generazione grafici...")

    # Asse X in secondi (più leggibile di millisecondi)
    # Creiamo una nuova colonna "time_s" dividendo timestamp per 1000
    df = df.copy()
    df["time_s"] = df["timestamp_ms"] / 1000.0

    # Creiamo una figura con 4 grafici in una colonna
    # figsize=(larghezza, altezza) in pollici
    fig, axes = plt.subplots(4, 1, figsize=(14, 12))
    fig.suptitle("Desk Telemetry — Analisi sessione", fontsize=14)

    # Stile scuro per coerenza con il dashboard
    plt.style.use("dark_background")

    # --- Grafico 1: Temperatura ---
    ax1 = axes[0]
    ax1.plot(df["time_s"], df["temperature_c"],
             color="#e06c75", linewidth=1, label="Temperatura")
    ax1.set_ylabel("°C")
    ax1.set_title("Temperatura IMU")
    ax1.legend()
    ax1.grid(alpha=0.3)

    # --- Grafico 2: Accelerometro ---
    ax2 = axes[1]
    ax2.plot(df["time_s"], df["acc_x_g"], color="#e06c75", linewidth=1, label="X")
    ax2.plot(df["time_s"], df["acc_y_g"], color="#61afef", linewidth=1, label="Y")
    ax2.plot(df["time_s"], df["acc_z_g"], color="#98c379", linewidth=1, label="Z")
    ax2.set_ylabel("g")
    ax2.set_title("Accelerometro")
    ax2.legend()
    ax2.grid(alpha=0.3)

    # --- Grafico 3: Giroscopio ---
    ax3 = axes[2]
    ax3.plot(df["time_s"], df["gyr_x_dps"], color="#e06c75", linewidth=1, label="X")
    ax3.plot(df["time_s"], df["gyr_y_dps"], color="#61afef", linewidth=1, label="Y")
    ax3.plot(df["time_s"], df["gyr_z_dps"], color="#98c379", linewidth=1, label="Z")
    ax3.set_ylabel("°/s")
    ax3.set_title("Giroscopio")
    ax3.legend()
    ax3.grid(alpha=0.3)

    # --- Grafico 4: Microfono con anomalie evidenziate ---
    ax4 = axes[3]
    ax4.plot(df["time_s"], df["mic_level"],
             color="#c678dd", linewidth=1, label="Microfono")

    # Evidenziamo i punti anomali sul grafico del microfono
    if len(anomalies) > 0:
        anomalies_plot = anomalies.copy()
        anomalies_plot["time_s"] = anomalies_plot["timestamp_ms"] / 1000.0
        # scatter plot per i punti anomali — cerchi rossi sopra la linea
        ax4.scatter(anomalies_plot["time_s"], anomalies_plot["mic_level"],
                    color="red", s=50, zorder=5, label="Anomalie")

    ax4.set_ylabel("livello")
    ax4.set_xlabel("tempo (s)")
    ax4.set_title("Microfono")
    ax4.legend()
    ax4.grid(alpha=0.3)

    # tight_layout() aggiusta automaticamente i margini per evitare sovrapposizioni
    plt.tight_layout()
    plt.show()


# --- FUNZIONE PRINCIPALE ------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Desk Telemetry Analysis")
    parser.add_argument("--input",  required=True, help="File CSV da analizzare")
    parser.add_argument("--plot",   action="store_true",
                        help="Mostra grafici dopo l'analisi")
    args = parser.parse_args()

    # Carichiamo i dati
    df = load_data(args.input)

    # Eseguiamo le tre analisi in sequenza
    print_statistics(df)
    print_correlations(df)
    anomalies = detect_anomalies(df)

    # Grafici opzionali
    if args.plot:
        plot_analysis(df, anomalies)


if __name__ == "__main__":
    main()