"""
Bloque 2 (guía siguiente versión, 22/09/2026): conftest.py a nivel
raíz -- pytest lo carga para TODA la sesión, así que garantiza que
`app` sea importable desde cualquier test, sin depender de que
cada archivo tenga su propio `sys.path.insert(...)`.

La mayoría de los scripts de tools/probes/ ya se arreglan solos
con su propio sys.path.insert. Este conftest.py cubre el resto:
los archivos de tools/probes/ que se corrían con
`python -m tools.probes.<paquete>.test_algo` (sin hack propio,
confiando en que `-m` desde la raíz del proyecto ya deja `app`
importable) y tools/probes/badges/test_badges_storage.py en
particular, que no tiene ni lo uno ni lo otro (badges/ no tiene
__init__.py) -- sin este conftest.py, pytest lo intenta importar
desde tools/probes/badges/ directamente y `from app...` falla ahí.
No se tocó ninguno de esos archivos -- los probes no se modifican
ni se mueven (regla del proyecto).
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
