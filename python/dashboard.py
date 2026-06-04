# ==============================================================================
# dashboard.py
# Scopo: visualizzare in tempo reale tutti i sensori della board.
#
# Layout della finestra (4 grafici):
#   Riga 1: Temperatura (°C) | Microfono (livello RMS)
#   Riga 2: Accelerometro X/Y/Z (g) | Giroscopio X/Y/Z (°/s)
#   Riga 3: Magnetometro X/Y/Z (µT) — a tutta larghezza
#
# Batteria: mostrata come testo nella barra del titolo della finestra.
# Non serve un grafico per un valore che cambia lentamente.
#
# Uso:
#   py -3.12 dashboard.py --port COM3
#   py -3.12 -u simulator.py | py -3.12 -u dashboard.py --stdin
# ==============================================================================

import sys
import argparse
import threading
from collections import deque

import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets, QtCore

from reader import parse_line, read_from_stdin, read_from_serial


MAX_POINTS = 200  # campioni visibili — a 10Hz = 20 secondi di storia


class DeskDashboard(pg.GraphicsLayoutWidget):
    """
    Finestra principale del dashboard con 5 grafici in tempo reale.
    Eredita da pg.GraphicsLayoutWidget — è una finestra pyqtgraph pronta,
    aggiungiamo solo quello che ci serve sopra.
    """

    def __init__(self, source):
        # super().__init__() chiama il costruttore della classe genitore
        super().__init__(show=True, title="Desk Telemetry")
        self.source = source

        # "self." rende le variabili attributi dell'oggetto — accessibili
        # da tutti i metodi della classe (equivale a this-> in C++)

        # Buffer tempo (asse X) — un solo buffer condiviso da tutti i grafici
        # così tutti mostrano lo stesso intervallo temporale
        self.time_data = deque(maxlen=MAX_POINTS)

        # Buffer valori (asse Y) — uno per ogni grandezza
        self.temp_data  = deque(maxlen=MAX_POINTS)
        self.mic_data   = deque(maxlen=MAX_POINTS)
        self.acc_x_data = deque(maxlen=MAX_POINTS)
        self.acc_y_data = deque(maxlen=MAX_POINTS)
        self.acc_z_data = deque(maxlen=MAX_POINTS)
        self.gyr_x_data = deque(maxlen=MAX_POINTS)
        self.gyr_y_data = deque(maxlen=MAX_POINTS)
        self.gyr_z_data = deque(maxlen=MAX_POINTS)
        self.mag_x_data = deque(maxlen=MAX_POINTS)
        self.mag_y_data = deque(maxlen=MAX_POINTS)
        self.mag_z_data = deque(maxlen=MAX_POINTS)

        # Ultimo campione batteria — aggiorniamo solo il titolo, non un grafico
        self.last_bat_voltage = 0.0
        self.last_bat_percent = 0

        self._setup_ui()
        self._start_reader_thread()
        self._start_update_timer()

    def _make_plot(self, title, left_label, left_units):
        """
        Metodo helper: crea un grafico con impostazioni comuni.

        Invece di ripetere le stesse 4 righe per ogni grafico, le mettiamo
        in una funzione. Questo si chiama DRY: Don't Repeat Yourself —
        principio fondamentale della programmazione.

        Args:
            title:       titolo del grafico
            left_label:  etichetta asse Y
            left_units:  unità di misura asse Y

        Returns:
            p: oggetto grafico pyqtgraph pronto da usare
        """
        p = self.addPlot(title=title)
        p.setLabel("left",   left_label, units=left_units)
        p.setLabel("bottom", "tempo",    units="ms")
        p.showGrid(x=True, y=True, alpha=0.3)
        p.enableAutoRange(axis='y')
        return p

    def _setup_ui(self):
        """Costruisce il layout con 5 grafici."""
        pg.setConfigOption("background", "#1e1e1e")
        pg.setConfigOption("foreground", "#cccccc")
        self.setWindowTitle("Desk Telemetry Dashboard")
        self.resize(1100, 700)

        # --- Riga 1: Temperatura | Microfono ---
        # Due grafici affiancati — addPlot() li mette sulla stessa riga
        p1 = self._make_plot("Temperatura IMU", "°C", "")
        self.curve_temp = p1.plot(
            pen=pg.mkPen(color="#e06c75", width=2))

        p2 = self._make_plot("Microfono", "livello", "")
        p2.setYRange(0, 100)  # il livello mic è sempre 0-100, range fisso
        self.curve_mic = p2.plot(
            pen=pg.mkPen(color="#c678dd", width=2))

        self.nextRow()  # passiamo alla riga successiva del layout

        # --- Riga 2: Accelerometro | Giroscopio ---
        p3 = self._make_plot("Accelerometro", "g", "")
        p3.addLegend()  # legenda per distinguere X/Y/Z
        # Tre curve sullo stesso grafico — una per asse
        self.curve_acc_x = p3.plot(pen=pg.mkPen("#e06c75", width=2), name="X")
        self.curve_acc_y = p3.plot(pen=pg.mkPen("#61afef", width=2), name="Y")
        self.curve_acc_z = p3.plot(pen=pg.mkPen("#98c379", width=2), name="Z")

        p4 = self._make_plot("Giroscopio", "°/s", "")
        p4.addLegend()
        self.curve_gyr_x = p4.plot(pen=pg.mkPen("#e06c75", width=2), name="X")
        self.curve_gyr_y = p4.plot(pen=pg.mkPen("#61afef", width=2), name="Y")
        self.curve_gyr_z = p4.plot(pen=pg.mkPen("#98c379", width=2), name="Z")

        self.nextRow()

        # --- Riga 3: Magnetometro (a tutta larghezza) ---
        # colspan=2 fa estendere il grafico su entrambe le colonne
        p5 = self.addPlot(title="Magnetometro", colspan=2)
        p5.setLabel("left",   "µT",    units="")
        p5.setLabel("bottom", "tempo", units="ms")
        p5.showGrid(x=True, y=True, alpha=0.3)
        p5.enableAutoRange(axis='y')
        p5.addLegend()
        self.curve_mag_x = p5.plot(pen=pg.mkPen("#e06c75", width=2), name="X")
        self.curve_mag_y = p5.plot(pen=pg.mkPen("#61afef", width=2), name="Y")
        self.curve_mag_z = p5.plot(pen=pg.mkPen("#98c379", width=2), name="Z")

    def _start_reader_thread(self):
        """
        Avvia il thread di lettura in background.
        Necessario perché readline() dalla seriale è bloccante —
        se lo facessimo nel thread principale, la UI si congelerebbe.
        I due thread comunicano solo attraverso i deque (thread-safe).
        """
        thread = threading.Thread(target=self._read_loop, daemon=True)
        thread.start()

    def _read_loop(self):
        """Loop nel thread separato — aggiunge ogni campione ai buffer."""
        for sample in self.source:
            self.time_data.append(sample.timestamp)
            self.temp_data.append(sample.temperature)
            self.mic_data.append(sample.mic_level)
            self.acc_x_data.append(sample.acc_x)
            self.acc_y_data.append(sample.acc_y)
            self.acc_z_data.append(sample.acc_z)
            self.gyr_x_data.append(sample.gyr_x)
            self.gyr_y_data.append(sample.gyr_y)
            self.gyr_z_data.append(sample.gyr_z)
            self.mag_x_data.append(sample.mag_x)
            self.mag_y_data.append(sample.mag_y)
            self.mag_z_data.append(sample.mag_z)
            # Batteria: salviamo solo l'ultimo valore
            self.last_bat_voltage = sample.bat_voltage
            self.last_bat_percent = sample.bat_percent

    def _start_update_timer(self):
        """
        Timer Qt che chiama _update_plots ogni 100ms.
        Il QTimer è il modo corretto di eseguire codice periodicamente
        in una UI senza bloccare la gestione degli eventi.
        timeout.connect() collega il segnale "timer scattato" alla funzione.
        """
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._update_plots)
        self.timer.start(100)

    def _update_plots(self):
        """
        Aggiorna tutti i grafici con i dati attuali.
        Chiamata ogni 100ms dal timer.

        setData(x=t, y=...) aggiorna la curva con asse X temporale reale.
        list(deque) crea una snapshot del buffer in quel momento.
        """
        if not self.time_data:
            return

        # Snapshot del buffer tempo — usato come asse X per tutti i grafici
        t = list(self.time_data)

        self.curve_temp.setData(x=t,  y=list(self.temp_data))
        self.curve_mic.setData(x=t,   y=list(self.mic_data))
        self.curve_acc_x.setData(x=t, y=list(self.acc_x_data))
        self.curve_acc_y.setData(x=t, y=list(self.acc_y_data))
        self.curve_acc_z.setData(x=t, y=list(self.acc_z_data))
        self.curve_gyr_x.setData(x=t, y=list(self.gyr_x_data))
        self.curve_gyr_y.setData(x=t, y=list(self.gyr_y_data))
        self.curve_gyr_z.setData(x=t, y=list(self.gyr_z_data))
        self.curve_mag_x.setData(x=t, y=list(self.mag_x_data))
        self.curve_mag_y.setData(x=t, y=list(self.mag_y_data))
        self.curve_mag_z.setData(x=t, y=list(self.mag_z_data))

        # Aggiorniamo il titolo della finestra con i dati batteria
        # setWindowTitle() cambia il testo nella barra del titolo
        self.setWindowTitle(
            f"Desk Telemetry  |  "
            f"Batteria: {self.last_bat_voltage:.2f}V  {self.last_bat_percent}%"
        )


# --- FUNZIONE PRINCIPALE ------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Desk Telemetry Dashboard")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--port",  help="Porta seriale, es. COM3")
    group.add_argument("--stdin", action="store_true", help="Leggi da stdin")
    parser.add_argument("--baudrate", type=int, default=115200)
    args = parser.parse_args()

    if args.stdin:
        source = read_from_stdin()
    else:
        source = read_from_serial(args.port, args.baudrate)

    # QApplication è il motore Qt — deve esistere prima di qualsiasi widget
    app = QtWidgets.QApplication(sys.argv)
    dashboard = DeskDashboard(source)
    # app.exec() avvia il loop degli eventi — si ferma qui fino alla chiusura
    sys.exit(app.exec())


if __name__ == "__main__":
    main()