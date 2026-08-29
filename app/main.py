from app.core.app import Application
from app.gui.main_window import MainWindow


def main():
    app = Application()
    window = MainWindow(app)

    try:
        # window.run() bloquea el hilo principal en el mainloop de
        # Tkinter -- el Runtime realtime y el HTTPServer se
        # inician/detienen desde los botones de la ventana, no acá
        # (ver app/gui/main_window.py).
        window.run()
    finally:
        app.stop()


if __name__ == "__main__":
    main()
