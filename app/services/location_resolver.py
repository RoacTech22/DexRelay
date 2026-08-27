from app.services.hoenn_locations_es import translate_location_name
from app.services.pkhex.bridge import PKHeXBridge


class LocationResolver:
    """
    Resuelve el lugar de encuentro (y el estado shiny) de un
    Pokémon a partir de sus datos ya descifrados, usando PKHeX
    (acción 'met_location' del bridge -- ver
    dotnet/DexRelay.PKHeX/Program.cs).

    Se cachea por nickname, no por especie: el lugar de encuentro
    de un Pokémon puntual no cambia nunca una vez resuelto, así que
    solo hace falta resolverlo una vez, no en cada ciclo realtime de
    200ms. Sin esta caché, cada lectura de party dispararía hasta 6
    llamadas al bridge por ciclo. Solo se cachean resultados
    EXITOSOS (metLocation ya resuelto) -- ver el docstring de
    resolve() para el bug real que causaba esto y por qué importa.
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

        BUG REAL corregido (26/08/2026): antes se cacheaba
        CUALQUIER resultado, incluso uno "vacío". Un Pokémon recién
        atrapado se lee por primera vez mientras el cuadro de
        diálogo de nombre sigue abierto -- en ese momento el juego
        todavía no terminó de escribir el lugar de encuentro, así
        que la primera resolución con ese nickname da vacío. Si el
        nickname no cambia después (el jugador tarda mucho en
        decidir, o elige no ponerle nombre y se queda con el de la
        especie), ese resultado vacío quedaba cacheado PARA SIEMPRE
        bajo esa clave -- ninguna lectura futura volvía a
        preguntarle al bridge, aunque el juego ya hubiera terminado
        de escribir la ruta real. Ahora solo se cachea un resultado
        exitoso (metLocation resuelto, no vacío); un resultado vacío
        se reintenta en la próxima lectura, hasta que el juego
        termine de escribir el dato y el bridge lo resuelva bien.
        """

        empty_result = {
            "metLocation": "",
            "metLocationId": 0,
            "eggLocationId": 0,
            "shiny": False,
        }

        if not nickname:
            return empty_result

        cached = self.cache.get(nickname)

        if cached is not None:
            return cached

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

        if met_location_name:
            # Solo se cachea un resultado ya resuelto -- uno vacío
            # se reintenta en la próxima lectura (ver docstring).
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
