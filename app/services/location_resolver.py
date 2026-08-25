from app.services.hoenn_locations_es import translate_location_name
from app.services.pkhex.bridge import PKHeXBridge


class LocationResolver:
    """
    Resuelve el lugar de encuentro (y el estado shiny) de un
    Pokémon a partir de sus datos ya descifrados, usando PKHeX
    (acción 'met_location' del bridge -- ver
    dotnet/DexRelay.PKHeX/Program.cs).

    Se cachea por nickname, no por especie: el lugar de encuentro
    de un Pokémon puntual no cambia nunca una vez capturado, así
    que solo hace falta resolverlo la primera vez que se lo ve, no
    en cada ciclo realtime de 200ms. Sin esta caché, cada lectura
    de party dispararía hasta 6 llamadas al bridge por ciclo.
    """

    def __init__(self, bridge=None):
        self.bridge = (
            bridge
            if bridge is not None
            else PKHeXBridge()
        )

        self.cache = {}

    def resolve(self, nickname, decrypted_box_data):
        """
        Devuelve {'metLocation', 'metLocationId', 'eggLocationId',
        'shiny'}. Si no se pudo resolver (bridge no disponible,
        error, datos insuficientes), devuelve un dict "vacío" con
        metLocation="" y shiny=False -- nunca lanza, para no
        romper la lectura de party por esto.
        """

        empty_result = {
            "metLocation": "",
            "metLocationId": 0,
            "eggLocationId": 0,
            "shiny": False,
        }

        if not nickname:
            return empty_result

        if nickname in self.cache:
            return self.cache[nickname]

        try:
            result = self.bridge.met_location(
                decrypted_box_data
            )

        except Exception:
            return empty_result

        met_location_id = result.get(
            "metLocationId",
            0,
        )

        # Misma traducción que usa LocationCatalog, por ID -- si
        # esto no fuera idéntico, el nombre de una captura real no
        # coincidiría con la fila precargada en el panel y
        # volveríamos a tener el bug de rutas duplicadas.
        met_location_name = translate_location_name(
            met_location_id,
            result.get(
                "metLocationName",
                "",
            ),
        )

        info = {
            "metLocation": met_location_name,
            "metLocationId": met_location_id,
            "eggLocationId": result.get(
                "eggLocationId",
                0,
            ),
            "shiny": bool(
                result.get(
                    "shiny",
                    False,
                )
            ),
        }

        self.cache[nickname] = info

        return info

    def forget(self, nickname):
        """
        Olvida la caché de un nickname. No se usa en el flujo
        normal (una vez resuelto, el dato es estable para
        siempre), pero queda disponible por si se necesita forzar
        una re-resolución (ej. herramientas de diagnóstico).
        """

        self.cache.pop(nickname, None)
