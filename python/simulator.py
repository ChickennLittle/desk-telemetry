# ==============================================================================
# simulator.py
# Scopo: simulare l'output seriale della board (M5Stack CoreS3).
# Genera dati CSV identici al firmware reale — tutti e 14 i campi.
#
# Formato output:
#   timestamp,temp,acc_x,acc_y,acc_z,gyr_x,gyr_y,gyr_z,mag_x,mag_y,mag_z,mic,bat_v,bat_pct
#
# Uso:
#   python simulator.py                              (stampa su stdout)
#   python -u simulator.py | python -u reader.py --stdin
#   python -u simulator.py | python -u dashboard.py --stdin
# ==============================================================================

import time
import math
import random
import sys


def generate_data(t: float) -> tuple:
    """
    Genera un campione simulato al tempo t.
    Ogni sensore ha un comportamento realistico:
      - Temperatura: valore stabile con piccolo rumore (chip si scalda lentamente)
      - Accelerometro: board ferma, gravità su Z con piccole vibrazioni
      - Giroscopio: vicino a zero con piccolo rumore (nessuna rotazione)
      - Magnetometro: campo costante con variazioni lente (come ambiente reale)
      - Microfono: rumore ambientale casuale con picchi occasionali
      - Batteria: stabile al 99% come se fosse collegata a USB

    Args:
        t: variabile temporale — incrementata ad ogni campione

    Returns:
        tupla con tutti i valori nel formato del firmware
    """

    # --- Timestamp ---
    # millis() in Arduino inizia da 0 all'accensione e incrementa.
    # Simuliamo lo stesso: convertiamo t (in secondi) in millisecondi.
    # int() tronca il float all'intero — come millis() che è un intero.
    timestamp = int(t * 1000)

    # --- Temperatura IMU ---
    # Il chip si scalda leggermente nel tempo, poi si stabilizza.
    # math.tanh() è una funzione che sale rapidamente e poi si appiattisce
    # — perfetta per simulare il riscaldamento del chip.
    # Partiamo da 35°C e saliamo a circa 41°C, con piccolo rumore casuale.
    temp = 35.0 + 6.0 * math.tanh(t / 60.0) + random.gauss(0, 0.05)
    # ↑ random.gauss(media, deviazione_standard): genera un numero casuale
    #   con distribuzione gaussiana (campana) — più realistico di random puro

    # --- Accelerometro ---
    # Board ferma sul tavolo: X≈0, Y≈0, Z≈1.0 (gravità)
    # Aggiungiamo piccole vibrazioni casuali (rumore sensore)
    acc_x = random.gauss(0.0,  0.003)
    acc_y = random.gauss(-0.01, 0.003)
    acc_z = random.gauss(1.010, 0.003)

    # --- Giroscopio ---
    # Board ferma: tutti vicini a zero, con piccolo drift tipico del sensore
    gyr_x = random.gauss(0.0, 0.2)
    gyr_y = random.gauss(0.0, 0.2)
    gyr_z = random.gauss(-0.3, 0.2)

    # --- Magnetometro ---
    # Campo magnetico con variazioni lente (interferenze ambientali)
    # Valori tipici osservati dalla board reale
    mag_x = -175.0 + math.sin(t * 0.1) * 20.0 + random.gauss(0, 5)
    mag_y =  330.0 + math.cos(t * 0.08) * 25.0 + random.gauss(0, 5)
    mag_z =   65.0 + math.sin(t * 0.05) * 15.0 + random.gauss(0, 3)

    # --- Microfono ---
    # Rumore ambientale basso con picchi occasionali (voci, rumori)
    # random.random() genera un float uniforme tra 0.0 e 1.0
    # Se il valore casuale è > 0.97 (3% di probabilità) simuliamo un picco
    if random.random() > 0.97:
        mic = random.gauss(30.0, 10.0)  # picco audio
    else:
        mic = random.gauss(0.3, 0.15)   # silenzio con piccolo rumore

    # max(0, ...) garantisce che il livello non scenda sotto 0
    mic = max(0, mic)

    # --- Batteria ---
    # Collegata a USB: tensione stabile, percentuale 99%
    bat_v   = 4.154 + random.gauss(0, 0.001)
    bat_pct = 99

    return (timestamp, temp,
            acc_x, acc_y, acc_z,
            gyr_x, gyr_y, gyr_z,
            mag_x, mag_y, mag_z,
            mic, bat_v, bat_pct)


def main():
    t = 0.0
    interval = 0.1  # 100ms tra un campione e l'altro (come il firmware)

    print("# Desk Telemetry Simulator avviato", file=sys.stderr)
    print("# Formato: timestamp,temp,acc_x,acc_y,acc_z,gyr_x,gyr_y,gyr_z,"
          "mag_x,mag_y,mag_z,mic,bat_v,bat_pct", file=sys.stderr)
    print("# CTRL+C per fermare", file=sys.stderr)

    try:
        while True:
            # Spacchettamento della tupla in variabili separate
            (timestamp, temp,
             acc_x, acc_y, acc_z,
             gyr_x, gyr_y, gyr_z,
             mag_x, mag_y, mag_z,
             mic, bat_v, bat_pct) = generate_data(t)

            # f-string con formattazione per ogni campo
            # Il formato coincide esattamente con l'output del firmware
            line = (
                f"{timestamp},"
                f"{temp:.2f},"
                f"{acc_x:.3f},{acc_y:.3f},{acc_z:.3f},"
                f"{gyr_x:.2f},{gyr_y:.2f},{gyr_z:.2f},"
                f"{mag_x:.2f},{mag_y:.2f},{mag_z:.2f},"
                f"{mic:.1f},"
                f"{bat_v:.3f},"
                f"{bat_pct}"
            )

            try:
                print(line, flush=True)
            except OSError:
                # Il pipe si è chiuso (es. dashboard chiuso) — usciamo puliti
                sys.exit(0)

            t += 0.1
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n# Simulatore fermato.", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()