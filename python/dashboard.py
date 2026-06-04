# ==============================================================================
# dashboard.py
# Scopo: visualizzare in tempo reale i dati di telemetria dalla board.
#
# Struttura della finestra:
#   - Grafico 1: Temperatura (°C) vs tempo (ms)
#   - Grafico 2: Accelerometro X, Y, Z (g) vs tempo (ms) — tre curve sovrapposte
#
# L'asse X è il timestamp in millisecondi dalla board — dati reali nel tempo,
# non semplici indici di campione come nella versione precedente.
#
# Uso:
#   py -3.12 dashboard.py --port COM3
#   py -3.12 -u simulator.py | py -3.12 -u dashboard.py --stdin
# ==============================================================================

import sys
import argparse
import threading
# ↑ threading: permette di eseguire codice in parallelo.
#   Usiamo un thread separato per leggere i dati seriali così la finestra
#   grafica rimane sempre reattiva e non si congela ad aspettare i dati.

from collections import deque
# ↑ deque (double-ended queue): lista con lunghezza massima fissa.
#   Quando è piena e aggiungi un elemento, rimuove automaticamente il più vecchio.
#   Perfetta per un grafico scorrevole: mantieni sempre gli ultimi N punti.

import pyqtgraph as pg
# ↑ pyqtgraph: libreria per grafici in tempo reale ad alte prestazioni.
#   Aggiorna solo i punti che cambiano — molto più veloce di matplotlib live.

from pyqtgraph.Qt import QtWidgets, QtCore
# ↑ QtWidgets: classi per costruire la finestra (QApplication, QWidget, ecc.)
#   QtCore:    classi fondamentali Qt — usiamo QTimer per l'aggiornamento periodico

# Importiamo da reader.py — non riscriviamo nulla, riusiamo quello che esiste.
# reader.py diventa una libreria. Questo è il vantaggio dei moduli separati.
from reader import parse_line, read_from_stdin, read_from_serial


# --- COSTANTI -----------------------------------------------------------------
MAX_POINTS = 200  # quanti campioni tenere visibili nel grafico
                  # a 10 campioni/secondo (delay 100ms) = 20 secondi di storia


# --- CLASSE PRINCIPALE --------------------------------------------------------
# DeskDashboard eredita da pg.GraphicsLayoutWidget.
# Ereditare significa che DeskDashboard È una finestra pyqtgraph, con tutte
# le sue funzionalità già incluse — aggiungiamo solo quello che ci serve.
# È lo stesso principio dell'ereditarietà in C++: class Figlia : public Genitore

class DeskDashboard(pg.GraphicsLayoutWidget):
    """
    Finestra principale del dashboard di telemetria.
    Gestisce la UI, il thread di lettura dati e il timer di aggiornamento.
    """

    def __init__(self, source):
        # __init__ è il costruttore — chiamato quando scrivi DeskDashboard(source).
        # super().__init__() chiama il costruttore della classe genitore
        # (pg.GraphicsLayoutWidget). In C++: GraphicsLayoutWidget::GraphicsLayoutWidget()
        # show=True apre la finestra immediatamente alla creazione.
        super().__init__(show=True, title="Desk Telemetry")

        # "self" è il riferimento all'oggetto corrente — equivale a "this" in C++.
        # Tutti gli attributi dell'oggetto si dichiarano e accedono con self.
        self.source = source

        # Buffer per il tempo (asse X) — condiviso da entrambi i grafici.
        # Tutti i buffer hanno la stessa lunghezza massima così rimangono sincronizzati.
        self.time_data = deque(maxlen=MAX_POINTS)

        # Buffer per i valori (asse Y) — uno per ogni grandezza da visualizzare
        self.temp_data  = deque(maxlen=MAX_POINTS)
        self.acc_x_data = deque(maxlen=MAX_POINTS)
        self.acc_y_data = deque(maxlen=MAX_POINTS)
        self.acc_z_data = deque(maxlen=MAX_POINTS)

        # Chiamiamo i tre metodi di inizializzazione in ordine:
        # 1. costruiamo la UI
        # 2. avviamo il thread che legge i dati
        # 3. avviamo il timer che aggiorna i grafici
        self._setup_ui()
        self._start_reader_thread()
        self._start_update_timer()

    def _setup_ui(self):
        """
        Crea e configura i grafici nella finestra.
        Il prefisso _ per convenzione indica un metodo "privato" —
        da usare solo internamente alla classe, non dall'esterno.
        In Python non esiste il vero private come in C++, è solo una convenzione.
        """
        # Tema scuro per tutti i grafici pyqtgraph — impostazione globale
        pg.setConfigOption("background", "#1e1e1e")
        pg.setConfigOption("foreground", "#cccccc")

        self.setWindowTitle("Desk Telemetry Dashboard")
        self.resize(900, 600)

        # --- Grafico 1: Temperatura ---
        # addPlot() aggiunge un grafico alla finestra e lo restituisce.
        p1 = self.addPlot(title="Temperatura IMU")
        p1.setLabel("left",   "°C")
        p1.setLabel("bottom", "tempo", units="ms")
        p1.showGrid(x=True, y=True, alpha=0.3)
        # enableAutoRange: il grafico scala automaticamente l'asse Y in base ai dati.
        # Con dati reali non sappiamo i range esatti in anticipo, meglio lasciare
        # che pyqtgraph si adatti da solo.
        p1.enableAutoRange(axis='y')

        # plot() crea la curva e la restituisce.
        # Salviamo il riferimento in self.curve_temp per aggiornarla dopo.
        # pen=pg.mkPen(...) definisce colore e spessore della linea.
        self.curve_temp = p1.plot(pen=pg.mkPen(color="#e06c75", width=2))

        # nextRow() sposta il layout alla riga successiva per il prossimo grafico
        self.nextRow()

        # --- Grafico 2: Accelerometro ---
        p2 = self.addPlot(title="Accelerometro")
        p2.setLabel("left",   "g")
        p2.setLabel("bottom", "tempo", units="ms")
        p2.showGrid(x=True, y=True, alpha=0.3)
        p2.enableAutoRange(axis='y')

        # addLegend() aggiunge una legenda al grafico.
        # Ogni curva con name= apparirà nella legenda con il suo colore.
        p2.addLegend()

        # Tre curve sullo stesso grafico — una per asse.
        # name= appare nella legenda per distinguerle.
        # Colori: rosso=X, blu=Y, verde=Z
        self.curve_acc_x = p2.plot(pen=pg.mkPen(color="#e06c75", width=2), name="X")
        self.curve_acc_y = p2.plot(pen=pg.mkPen(color="#61afef", width=2), name="Y")
        self.curve_acc_z = p2.plot(pen=pg.mkPen(color="#98c379", width=2), name="Z")

    def _start_reader_thread(self):
        """
        Avvia un thread separato che legge i dati in background.

        Perché un thread separato?
        La lettura seriale è bloccante: il codice si ferma ad aspettare
        il prossimo dato dalla board. Se lo facessimo nel thread principale
        (quello della UI), la finestra si bloccherebbe e non risponderebbe
        a click, ridimensionamento, ecc.

        Con due thread:
          Thread 1 (principale): gestisce la finestra e gli eventi Qt
          Thread 2 (reader):     legge i dati e li mette nei buffer deque

        I due thread comunicano solo attraverso i deque — zone di memoria
        condivisa. Python garantisce che append() e lettura su deque siano
        thread-safe (non si pestano i piedi anche se avvengono simultaneamente).
        """
        # target= è la funzione che il thread eseguirà
        # daemon=True: quando la finestra si chiude, termina anche questo thread
        thread = threading.Thread(target=self._read_loop, daemon=True)
        thread.start()  # da qui il thread gira in parallelo al resto

    def _read_loop(self):
        """
        Loop di lettura dati — gira nel thread separato.
        Legge campioni dalla sorgente e li aggiunge ai buffer.
        Questo metodo non termina mai da solo — gira finché
        il thread viene fermato (quando la finestra si chiude).
        """
        for sample in self.source:
            # append() aggiunge in fondo al deque.
            # Se il deque è pieno (MAX_POINTS elementi), rimuove automaticamente
            # il più vecchio — effetto "finestra scorrevole" nel grafico.
            self.time_data.append(sample.timestamp)
            self.temp_data.append(sample.temperature)
            self.acc_x_data.append(sample.acc_x)
            self.acc_y_data.append(sample.acc_y)
            self.acc_z_data.append(sample.acc_z)

    def _start_update_timer(self):
        """
        Avvia un timer Qt che aggiorna i grafici ogni 100ms.

        Perché un timer e non un while True nel thread principale?
        In una UI non puoi fare while True nel thread principale — blocchi
        la gestione degli eventi (click, resize, chiusura finestra...).
        Il QTimer è il modo Qt di dire "esegui questa funzione periodicamente
        senza bloccare nulla".

        timeout è un "segnale" Qt — un meccanismo publish/subscribe.
        connect() collega il segnale a una funzione: quando il timer scatta,
        Qt chiama automaticamente _update_plots().
        """
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._update_plots)
        self.timer.start(100)  # millisecondi tra un aggiornamento e l'altro

    def _update_plots(self):
        """
        Aggiorna le curve dei grafici con i dati attuali nei buffer.
        Chiamata ogni 100ms dal timer.

        setData(x=..., y=...) aggiorna la curva con i nuovi dati.
        Passiamo sia x che y — l'asse X è il timestamp reale in ms,
        non più un semplice indice del campione.
        pyqtgraph ridisegna solo i punti che cambiano — per questo
        è molto più veloce di matplotlib in modalità live.
        """
        # Se non ci sono ancora dati non facciamo nulla
        if not self.time_data:
            return

        # Convertiamo il deque in lista una sola volta e la riusiamo
        # come asse X per tutti i grafici — efficiente e coerente.
        # list(deque) crea una copia snapshot del deque in quel momento.
        t = list(self.time_data)

        self.curve_temp.setData(x=t,  y=list(self.temp_data))
        self.curve_acc_x.setData(x=t, y=list(self.acc_x_data))
        self.curve_acc_y.setData(x=t, y=list(self.acc_y_data))
        self.curve_acc_z.setData(x=t, y=list(self.acc_z_data))


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

    # QApplication è il "motore" di Qt — gestisce la finestra, gli eventi,
    # il rendering. Deve esistere prima di qualsiasi widget.
    # sys.argv passa gli argomenti della riga di comando a Qt
    # (Qt ne usa alcuni internamente, es. per il display su Linux).
    app = QtWidgets.QApplication(sys.argv)

    # Creiamo la finestra — questo avvia anche il thread di lettura e il timer
    dashboard = DeskDashboard(source)

    # app.exec() avvia il loop degli eventi Qt.
    # Il programma si ferma qui finché la finestra non viene chiusa.
    # sys.exit() restituisce il codice di uscita al sistema operativo.
    sys.exit(app.exec())


# Entry point — main() viene chiamata solo se il file è eseguito direttamente.
# Se dashboard.py viene importato da un altro script, main() non parte.
if __name__ == "__main__":
    main()