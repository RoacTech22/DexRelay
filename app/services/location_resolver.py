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

    El NIVEL es la excepción a todo esto (07/09/2026) -- no vive en
    el dict que cachea resolve(), tiene su propio método sin caché
    (resolve_current_level()), justamente porque a diferencia del
    lugar de encuentro, el nivel sí cambia mientras el Pokémon sigue
    vivo. Ver el docstring de resolve_current_level() para el bug
    real que esto corrige.
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
            # "level" SACADO de acá (07/09/2026, ver
            # resolve_current_level() más abajo y el bug que
            # corrige) -- a diferencia de todo lo demás en este
            # dict, el nivel NO es inmutable, así que no puede
            # vivir en algo que se cachea para siempre.
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
            # "level" SACADO de acá (07/09/2026) -- ver
            # resolve_current_level(). No pertenece a este dict
            # cacheado, ver el comentario de empty_result arriba.
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

    def resolve_current_level(self, decrypted_box_data):
        """
        Nivel real de un Pokémon en formato de Caja PC (232 bytes
        ya descifrados), vía PKHeX (acción 'met_location',
        propiedad CurrentLevel -- ver HandleMetLocation() en
        Program.cs). Devuelve 0 si el bridge no está disponible o
        falla, nunca lanza.

        Bug real corregido (07/09/2026, reportado por el usuario:
        la tabla de "Encuentros por Ruta" mostraba mal el nivel de
        un Pokémon guardado en la Caja PC): antes este dato viajaba
        adentro del dict que cachea resolve() por nickname junto
        con metLocation/eggLocation/shiny/isEgg. Esos campos sí son
        inmutables una vez resueltos (el lugar de encuentro de un
        Pokémon puntual no cambia nunca), pero el NIVEL no lo es --
        si el Pokémon entrenó en la party antes de guardarse en la
        Caja, la primera resolución exitosa (típicamente apenas se
        atrapa, nivel bajo) quedaba cacheada para siempre, y como
        `pokemon.level()` siempre da 0 para una lectura de Caja
        (ver build_pokemon_data()), TODA lectura futura de ese
        Pokémon en caja mostraba ese nivel viejo congelado, sin
        importar cuánto hubiera entrenado después en la party.

        Por eso este método es deliberadamente SIN CACHÉ -- se
        llama al bridge de nuevo cada vez que hace falta (solo
        cuando build_pokemon_data() detecta nivel 0 en la lectura
        directa, o sea, solo para slots de Caja PC realmente
        ocupados -- nunca para party, que ya trae el nivel real).
        El volumen es acotado: como mucho la cantidad de slots
        ocupados entre las cajas leídas por ciclo (07/09/2026,
        ver AzaharReader.read_boxes_range() -- las 7 cajas de
        fábrica, antes solo la Caja 1), no toda la party.
        """

        try:
            result = self.bridge.met_location(
                decrypted_box_data
            )
        except Exception:
            return 0

        return result.get("level", 0)

    def forget(self, nickname):
        """
        Olvida la caché de un nickname. No se usa en el flujo
        normal (una vez resuelto, el dato es estable para
        siempre), pero queda disponible por si se necesita forzar
        una re-resolución (ej. herramientas de diagnóstico).
        """

        self.cache.pop(nickname, None)
