# ==============================================================================
# dashboard.py
# Scopo: visualizzare in tempo reale i dati di telemetria ricevuti da reader.py
#
# Uso:
#   python simulator.py | python -u dashboard.py --stdin
#   python dashboard.py --port COM3
#
# Struttura:
#   - Finestra con 3 grafici sovrapposti (temperatura, vibrazione, carico)
#   - Ogni grafico aggiorna solo i nuovi punti (non ridisegna tutto)
#   - I dati arrivano in un thread separato per non bloccare la UI
# ==============================================================================
import sys
import argparse
import threading  # Modulo standard: permette di eseguire codice in parallelo.
                  # Useremo un thread separato per leggere i dati seriali,
                  # così la finestra grafica rimane sempre reattiva.

from collections import deque
# deque (double-ended queue): una lista con lunghezza massima fissa.
# Quando è piena e aggiungi un elemento, rimuove automaticamente il più vecchio.
# Perfetta per un grafico scorrevole: mantieni sempre gli ultimi N punti.
# In C++ dovresti gestire manualmente un buffer circolare — qui è già pronto.

import pyqtgraph as pg
# pyqtgraph: libreria per grafici in tempo reale ad alte prestazioni.
# Costruita sopra PyQt6 (il framework per finestre grafiche).
from pyqtgraph.Qt import QtWidgets, QtCore
# QtWidgets: classi per costruire la finestra e i widget (pulsanti, layout, ecc.)
# QtCore:    classi fondamentali di Qt (timer, segnali, tipi base)

# Importiamo parse_line e le funzioni di lettura direttamente da reader.py.
# Questo è il vantaggio della struttura a moduli: non riscriviamo nulla,
# riusiamo quello che esiste già. reader.py diventa una libreria.
from reader import parse_line, read_from_stdin, read_from_serial


# --- COSTANTI -----------------------------------------------------------------
MAX_POINTS = 200  # quanti campioni tenere visibili nel grafico
# Aumentando questo numero il grafico mostra più storia ma usa più memoria.


# --- CLASSE PRINCIPALE --------------------------------------------------------
# In Python le classi si definiscono con "class Nome(Genitore):"
# Ereditare da pg.GraphicsLayoutWidget significa che DeskDashboard È una
# finestra pyqtgraph, con tutte le sue funzionalità già incluse.
# È come derivare una classe in C++.

class DeskDashboard(pg.GraphicsLayoutWidget):
    """
    Finestra principale del dashboard di telemetria.
    Contiene 3 grafici in tempo reale: temperatura, vibrazione, carico.
    """

    def __init__(self, source):
        # __init__ è il costruttore — viene chiamato quando crei un'istanza.
        # Equivale a DeskDashboard() in C++.

        # super().__init__() chiama il costruttore della classe genitore
        # (pg.GraphicsLayoutWidget). Obbligatorio quando si eredita in Python.
        # show=True apre la finestra immediatamente.
        super().__init__(show=True, title="Desk Telemetry")

        # source è il generatore di dati (read_from_stdin o read_from_serial).
        # Lo salviamo come attributo dell'istanza con self.
        # "self" in Python equivale a "this" in C++ — è il riferimento
        # all'oggetto corrente. Tutti gli attributi e metodi si accedono con self.
        self.source = source

        # Inizializziamo i tre buffer circolari, uno per ogni sensore.
        # deque(maxlen=MAX_POINTS) crea una coda con al massimo 200 elementi.
        self.temp_data = deque(maxlen=MAX_POINTS)
        self.vib_data  = deque(maxlen=MAX_POINTS)
        self.load_data = deque(maxlen=MAX_POINTS)

        # Costruiamo la UI (grafici, colori, etichette)
        self._setup_ui()

        # Avviamo il thread di lettura dati in background
        self._start_reader_thread()

        # Avviamo il timer che aggiorna i grafici ogni 100ms
        self._start_update_timer()

    def _setup_ui(self):
        """Crea e configura i tre grafici nella finestra."""

        # Impostiamo il tema scuro per tutti i grafici pyqtgraph
        pg.setConfigOption("background", "#1e1e1e")
        pg.setConfigOption("foreground", "#cccccc")

        self.setWindowTitle("Desk Telemetry Dashboard")
        self.resize(900, 600)

        # --- Grafico 1: Temperatura ---
        # addPlot() aggiunge un grafico alla finestra e lo restituisce.
        # title, labels, units appaiono sull'asse del grafico.
        p1 = self.addPlot(title="Temperatura")
        p1.setLabel("left",   "°C")
        p1.setLabel("bottom", "campioni")
        p1.showGrid(x=True, y=True, alpha=0.3)
        p1.setYRange(18, 28)  # range atteso per la temperatura simulata

        # plot() crea la curva sul grafico e la restituisce.
        # pen=pg.mkPen(...) definisce colore e spessore della linea.
        # Salviamo la curva in self.curve_temp per aggiornarla dopo.
        self.curve_temp = p1.plot(pen=pg.mkPen(color="#e06c75", width=2))

        # nextRow() sposta il layout al prossimo grafico sotto
        self.nextRow()

        # --- Grafico 2: Vibrazione ---
        p2 = self.addPlot(title="Vibrazione")
        p2.setLabel("left",   "intensità")
        p2.setLabel("bottom", "campioni")
        p2.showGrid(x=True, y=True, alpha=0.3)
        p2.setYRange(0, 1)
        self.curve_vib = p2.plot(pen=pg.mkPen(color="#61afef", width=2))

        self.nextRow()

        # --- Grafico 3: Carico ---
        p3 = self.addPlot(title="Carico")
        p3.setLabel("left",   "%")
        p3.setLabel("bottom", "campioni")
        p3.showGrid(x=True, y=True, alpha=0.3)
        p3.setYRange(25, 75)
        self.curve_load = p3.plot(pen=pg.mkPen(color="#98c379", width=2))

    def _start_reader_thread(self):
        """
        Avvia un thread separato che legge i dati in background.

        Perché un thread separato?
        La lettura da seriale/stdin è un'operazione bloccante: il codice
        si ferma ad aspettare il prossimo dato. Se lo facessimo nel thread
        principale (quello della UI), la finestra si bloccherebbe e non
        risponderebbe ai click o al ridimensionamento.

        Con un thread separato:
          - Thread 1 (principale): gestisce la finestra, i grafici, gli eventi
          - Thread 2 (reader):     legge i dati e li mette nei buffer

        I due thread comunicano solo attraverso i deque (self.temp_data, ecc.)
        che sono thread-safe per append e lettura in Python.
        """

        # target= è la funzione che il thread eseguirà
        # daemon=True significa: quando la finestra si chiude, termina anche
        # questo thread automaticamente (non aspettare che finisca da solo)
        thread = threading.Thread(target=self._read_loop, daemon=True)
        thread.start()  # avvia il thread — da qui in poi gira in parallelo

    def _read_loop(self):
        """
        Loop di lettura dati — gira nel thread separato.
        Legge campioni dalla sorgente e li aggiunge ai buffer.
        """
        for sample in self.source:
            # append() aggiunge un elemento in fondo al deque.
            # Se il deque è pieno (200 elementi), rimuove automaticamente
            # il più vecchio dall'altro lato — effetto "finestra scorrevole".
            self.temp_data.append(sample.temperature)
            self.vib_data.append(sample.vibration)
            self.load_data.append(sample.load)

    def _start_update_timer(self):
        """
        Avvia un timer Qt che chiama _update_plots() ogni 100ms.

        Perché un timer invece di un loop?
        In una UI, non puoi fare while True nel thread principale —
        blockeresti la gestione degli eventi (click, resize, ecc.).
        Il timer è il modo Qt di dire "esegui questa funzione periodicamente
        senza bloccare nulla".
        """
        self.timer = QtCore.QTimer()
        # timeout è un "segnale" Qt — si collega a una funzione da chiamare.
        # connect() è l'equivalente di "quando scatta il timer, chiama questo"
        self.timer.timeout.connect(self._update_plots)
        self.timer.start(100)  # millisecondi tra un aggiornamento e l'altro

    def _update_plots(self):
        """
        Aggiorna i tre grafici con i dati attuali nei buffer.
        Chiamata ogni 100ms dal timer.
        """
        # list() converte il deque in una lista — necessario per pyqtgraph.
        # setData() aggiorna la curva con i nuovi dati senza ridisegnare
        # l'intero grafico — solo i punti che cambiano vengono ridisegnati.
        # Questo è perché pyqtgraph è molto più veloce di matplotlib live.
        if self.temp_data:  # aggiorna solo se ci sono dati
            self.curve_temp.setData(list(self.temp_data))
            self.curve_vib.setData(list(self.vib_data))
            self.curve_load.setData(list(self.load_data))


# --- FUNZIONE PRINCIPALE ------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Desk Telemetry Dashboard")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--port",  help="Porta seriale, es. COM3")
    group.add_argument("--stdin", action="store_true", help="Leggi da stdin")
    parser.add_argument("--baudrate", type=int, default=115200)
    args = parser.parse_args()

    # Scegliamo la sorgente dati — stessa logica di reader.py
    if args.stdin:
        source = read_from_stdin()
    else:
        source = read_from_serial(args.port, args.baudrate)

    # Ogni applicazione Qt ha bisogno di un QApplication — è il "motore"
    # che gestisce la finestra, gli eventi, il rendering.
    # sys.argv passa gli argomenti della riga di comando a Qt
    # (Qt ne usa alcuni internamente, es. per il display su Linux).
    app = QtWidgets.QApplication(sys.argv)

    # Creiamo la finestra del dashboard passando la sorgente dati
    dashboard = DeskDashboard(source)

    # exec() avvia il loop degli eventi Qt — da qui in poi Qt gestisce tutto.
    # Il programma si ferma qui finché la finestra non viene chiusa.
    # sys.exit() restituisce il codice di uscita di Qt al sistema operativo.
    sys.exit(app.exec())


if __name__ == "__main__":
    main()