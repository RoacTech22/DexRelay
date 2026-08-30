"""
Punto de entrada para PyInstaller (FASE 6).

`app/main.py` usa imports absolutos tipo `from app.core.app import
Application` -- para que PyInstaller los resuelva bien necesita
analizar un script que viva en la RAÍZ del proyecto (para que
`app` se vea como paquete), no un script que esté adentro de la
propia carpeta `app/`. Por eso este archivo existe acá y no alcanza
con apuntar `pyinstaller` directo a `app/main.py`.

Correr desde el código fuente sigue siendo `python -m app.main`
como siempre -- este archivo es solo para el build empaquetado.
"""

from app.main import main

if __name__ == "__main__":
    main()
