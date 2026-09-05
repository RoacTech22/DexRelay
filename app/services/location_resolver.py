from app.services.hoenn_locations_es import translate_location_name
from app.services.egg_locations_es import translate_egg_location_name
from app.services.pkhex.bridge import PKHeXBridge


# Placeholders que PKHeX devuelve como texto en vez de un string
# vacío cuando el ID de ubicación todavía no es válido (28/08/2026,
# bug real reportado: capturas sin nombre quedaban registradas con
# la ruta literal "(None)" en vez de caer a pending_encounters
# para reintentar -- el chequeo `if met_location:` de
# nuzlocke_service.py trataba ese texto como una ruta real, porque
# no está vacío). Se filtran acá, ANTES de que lleguen a
# nuzlocke_service.py, para que ese código pueda seguir asumiendo
# "vacío == sin resolver todavía" sin tener que conocer estos
# casos puntuales de PKHeX.
_PLACEHOLDER_LOCATION_TEXTS = {
    "(none)",
    "none",
}


def _is_valid_location_text(text: str | None) -> bool:
    if not text:
        return False

    return (
        text.strip().lower()
        not in _PLACEHOLDER_LOCATION_TEXTS
    )


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
        'eggLocation', 'shiny', 'isEgg'}. Si no se pudo resolver
        (bridge no disponible, error, datos insuficientes),
        devuelve un dict "vacío" con metLocation="" y
        shiny=isEgg=False -- nunca lanza, para no romper la
        lectura de party por esto.

        `eggLocation` (28/08/2026, a pedido del usuario): el texto
        de "Entregado por" del Pokémon (ej. "Anciana del
        Balneario" para un huevo) -- un campo del PK6 DISTINTO de
        metLocation, pensado para el origen de huevos/regalos en
        vez de una ruta salvaje real. Ya viene resuelto en español
        desde el bridge (mismo GameInfo.CurrentLanguage="es" que
        metLocationName), así que no hace falta traducirlo acá.

        `isEgg` (29/08/2026, a pedido del usuario): a diferencia
        del nickname (que el juego SÍ oculta como "Huevo" mientras
        no nace), `speciesId` de un huevo ya resuelve la especie
        real -- el dato vive en el PK6 aunque todavía no se
        muestre. Sin este flag, el Team Overlay terminaba
        mostrando el sprite de la especie real de un huevo sin
        nacer (spoiler). `pk.IsEgg` es la misma propiedad que usa
        PKHeX para esto -- no se deriva de nada acá, se toma tal
        cual del bridge.

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
            "eggLocation": "",
            "shiny": False,
            "isEgg": False,
            # Bug real corregido (05/09/2026) -- ver
            # build_pokemon_data() en azahar_reader.py: se usa
            # como respaldo cuando la lectura directa de memoria
            # da nivel 0 (capturas que van directo a la Caja PC).
            "level": 0,
            # Ícono de género en el Nuzlocke Tracker (05/09/2026,
            # a pedido del usuario) -- None = no se pudo resolver
            # (bridge caído), 0 = macho, 1 = hembra, 2 = sin
            # género. Mismo valor que ya expone
            # PokemonDetailResolver para la página Pokémon.
            "genderId": None,
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

        raw_met_location_name = result.get(
            "metLocationName",
            "",
        )

        # Misma traducción que usa LocationCatalog, por ID -- si
        # esto no fuera idéntico, el nombre de una captura real no
        # coincidiría con la fila precargada en el panel y
        # volveríamos a tener el bug de rutas duplicadas. Antes de
        # traducir, se filtra el placeholder "(None)"/"None" (ver
        # arriba) -- si el texto crudo de PKHeX no es válido
        # todavía, se trata como vacío, no como una ruta real.
        met_location_name = (
            translate_location_name(
                met_location_id,
                raw_met_location_name,
            )
            if _is_valid_location_text(raw_met_location_name)
            else ""
        )

        raw_egg_location_name = result.get(
            "eggLocationName",
            "",
        )

        egg_location_name = (
            translate_egg_location_name(
                raw_egg_location_name
            )
            if _is_valid_location_text(raw_egg_location_name)
            else ""
        )

        info = {
            "metLocation": met_location_name,
            "metLocationId": met_location_id,
            "eggLocationId": result.get(
                "eggLocationId",
                0,
            ),
            "eggLocation": egg_location_name,
            "shiny": bool(
                result.get(
                    "shiny",
                    False,
                )
            ),
            "isEgg": bool(
                result.get(
                    "isEgg",
                    False,
                )
            ),
            # Bug real corregido (05/09/2026) -- ver
            # build_pokemon_data() en azahar_reader.py.
            "level": result.get("level", 0),
            # Ícono de género en el Nuzlocke Tracker (05/09/2026).
            "genderId": result.get("genderId"),
        }

        # Se cachea si CUALQUIERA de los dos lugares quedó resuelto
        # -- metLocation (ruta real) o eggLocation ("Entregado
        # por", 28/08/2026) -- o si ya sabemos que es un huevo
        # (29/08/2026): a diferencia de metLocation/eggLocation,
        # `isEgg` no depende de ningún cuadro de diálogo ni de una
        # escritura progresiva del juego -- es un flag fijo del
        # PK6, confiable desde la primera lectura. Cachearlo
        # también evita golpear el bridge en cada ciclo de 200ms
        # mientras el huevo sigue sin nacer (puede ser por miles de
        # pasos). Un Pokémon nunca va a tener metLocation (nunca
        # fue "encontrado" en una ruta), así que sin este OR nunca
        # se cachearía nada para huevos y se golpearía al bridge en
        # cada ciclo de 200ms para siempre. Igual que metLocation,
        # una vez que el juego termina de escribir el dato, no
        # vuelve a cambiar.
        if (
            met_location_name
            or info["eggLocation"]
            or info["isEgg"]
        ):
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
