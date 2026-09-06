import os
import sys

# En un build de PyInstaller con --windowed (sin consola), Windows
# deja sys.stdout/sys.stderr en None -- cualquier print() antes de
# que exista la ventana principal (que recién ahí instala el
# redirect de verdad hacia el panel de LOGS, ver
# app/gui/main_window.py) reventaría con AttributeError. Pasa en
# la práctica: Application.start() hace varios print() y se llama
# desde la pantalla de Espera, antes de que la ventana principal
# exista. Acá los reemplazamos por un sumidero inofensivo -- no
# hace nada distinto corriendo desde el código fuente (sys.stdout
# nunca es None ahí).
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")

if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# Página Logs de la GUI v2 (Bloque 5, 06/09/2026): instala la
# captura de stdout/stderr a un buffer en memoria (ver
# app/core/log_capture.py) ANTES de importar Application -- así
# queda ningún `print()` real afuera del buffer, ni siquiera los
# que puedan disparar módulos importados más abajo durante su
# propia inicialización. Reemplaza, para la GUI v2, al mismo rol
# que cumplía `_StreamToLogWidget` en la GUI Tkinter vieja
# (app/gui/main_window.py) -- ahí se instalaba recién al construir
# la ventana principal porque el destino era un widget Tkinter que
# todavía no existía; acá el destino es un buffer en memoria que sí
# puede existir desde el arranque mismo del proceso.
from app.core import log_capture

log_capture.install()

from app.core.app import Application

# GUI v2 (pywebview), reemplaza a la Tkinter/ttkbootstrap
# (app/gui/) como punto de entrada por defecto -- ver
# Documento Maestro, plan del 30/08/2026. La GUI vieja no se
# borró, queda en el proyecto sin usarse (mismo criterio que
# con los probes: documenta lo que ya se probó, no estorba). Si
# hiciera falta volver atrás temporalmente, alcanza con volver a
# importar `from app.gui.app_window import AppWindow` acá.
from app.gui_web.window import AppWindow


def main():
    app = Application()
    window = AppWindow(app)

    try:
        # window.run() bloquea el hilo principal en el mainloop de
        # pywebview -- el flujo Bienvenida -> Espera -> Conectado ->
        # Principal decide cuándo arrancar/detener el Runtime
        # realtime y el HTTPServer (ver app/gui_web/web/js/app.js y
        # app/gui_web/api.py), no acá.
        window.run()
    finally:
        app.stop()


if __name__ == "__main__":
    main()
