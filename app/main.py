from app.core.app import Application
from app.gui.app_window import AppWindow


def main():
    app = Application()
    window = AppWindow(app)

    try:
        # window.run() bloquea el hilo principal en el mainloop de
        # Tkinter -- el flujo Bienvenida -> Espera -> Principal
        # decide cuándo arrancar/detener el Runtime realtime y el
        # HTTPServer (ver app/gui/app_window.py), no acá.
        window.run()
    finally:
        app.stop()


if __name__ == "__main__":
    main()
