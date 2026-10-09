from __future__ import annotations

import time

from app.core.state import ApplicationState
from app.readers.azahar_reader import AzaharReader
from app.services.badges_service import BadgesService
from app.services.badges_storage import BadgesStorage
from app.services.combat_service import (
    LECTURA_DESCARTADA,
    CombatService,
)
from app.services.nuzlocke_service import NuzlockeService
from app.services.nuzlocke_storage import NuzlockeStorage


class Runtime:
    def __init__(
        self,
        reader: AzaharReader,
        state: ApplicationState,
        nuzlocke_service: NuzlockeService | None = None,
        time_source=None,
        storage_resolver=None,
    ):
        self.reader = reader
        self.state = state

        # Bloque 1.1 (22/09/2026) / fix del mismo bloque
        # (22/09/2026, bug real de regresión reportado corriendo
        # tools/probes/memory/test_box_scan_capture.py bajo pytest:
        # dos llamadas a update() seguidas, sin que pase tiempo de
        # reloj real entre medio, esperaban ver reflejado un cambio
        # en boxed_party de inmediato -- con BOX_SCAN_INTERVAL_
        # SECONDS de por medio, la segunda lectura quedaba
        # cacheada). Inyectable para que los tests puedan simular
        # el paso del tiempo con un reloj falso en vez de depender
        # de time.sleep() real; en producción (time_source=None)
        # se usa time.monotonic() como siempre.
        self._time_source = time_source or time.monotonic

        self.badges_service = BadgesService(
            self.reader
        )

        self.combat_service = CombatService(
            self.reader.memory,
            profile_provider=lambda: getattr(self.reader, "profile", None),
        )

        self.badges_storage = BadgesStorage()

        # Se puede compartir la misma instancia con HTTPServer
        # (ver app.py) para que el panel de encuentros escriba
        # sobre los mismos datos que el resto del sistema lee.
        # Si no se pasa ninguna, crea la suya propia (compatibilidad
        # con código/tests existentes que construyen Runtime solo).
        self.nuzlocke_service = (
            nuzlocke_service
            or NuzlockeService(
                NuzlockeStorage(),
                profile_provider=lambda: getattr(
                    self.reader, "profile", None
                ),
            )
        )

        self._last_badges = None

        # Detección automática del estado "perdido" (27/08/2026,
        # ver DexRelay_Contexto_Deteccion_Perdido.md). Estado de
        # tracking entre ciclos -- ver
        # _update_lost_encounter_tracking().
        self._lost_encounter_snapshot = None
        self._lost_tracking_resolved = False
        self._combat_was_active = False

        # BUG REAL corregido (10/09/2026, reportado por el usuario
        # jugando un Nuzlocke real: "me marca como perdido aunque lo
        # haya atrapado, y cuando le escribo el nombre me lo guarda
        # como duplicado"). Causa: al terminar el combate se leía
        # TOTAL_CAUGHT_ADDRESS UNA SOLA VEZ, en el mismo ciclo exacto
        # en que el puntero de combate vuelve a inactivo, y se
        # comparaba contra el snapshot ahí mismo -- sin margen. El
        # juego puede tardar uno o más ciclos de 200ms en terminar de
        # escribir ese contador después de que el puntero de combate
        # ya se limpió (la captura recién se termina de resolver
        # durante la transición de vuelta al mapa) -- mismo tipo de
        # escritura progresiva que ya obligó al "Intento 3" del
        # nickname/ruta y al reintento del flag salvaje más abajo.
        # Leer una sola vez en el instante exacto podía agarrar el
        # contador todavía viejo y registrar "perdido" para una
        # captura real -- que después SÍ se detectaba por el camino
        # normal de party/Caja PC, generando el duplicado reportado
        # (un encuentro "perdido" fantasma + la captura real pidiendo
        # nombre/ruta).
        #
        # Fix: en vez de decidir en el mismo ciclo, se guarda la
        # resolución como PENDIENTE (`_pending_lost_resolution`) y se
        # reintenta cada ciclo (ver _resolve_pending_lost_encounter())
        # hasta LOST_ENCOUNTER_MAX_RETRIES veces antes de recién ahí
        # concluir "perdido" -- si el contador sube en cualquiera de
        # esos reintentos, se descarta el snapshot sin registrar nada
        # (la captura real ya se encarga sola).
        self._pending_lost_resolution = None

        # Diagnóstico de la detección de "perdido" (18/09/2026,
        # reportado por el usuario: el registro de perdidos no
        # funcionaba jugando una partida larga y desde el código
        # solo no se puede saber qué eslabón de la cadena falla --
        # combate/flag salvaje, zona, contador de capturas o
        # especie del rival). Cada eslabón deja UNA línea por
        # combate en el buffer de la página Logs (ver _log_lost()),
        # sin spamear cada ciclo de 200ms.
        self._lost_log_seen = set()
        self._combat_wild_seen = False
        self._empty_party_cycles = 0

        # Bloque 1.1 (22/09/2026, guía siguiente versión -- ver
        # DexRelay_Guia_Siguiente_Version): read_boxes_range() lee
        # 7×30×232 = 48.720 bytes por UDP y competía por el mismo
        # lock de citra.py que party/badges/combate en CADA ciclo de
        # 200ms, sin ninguna necesidad real de esa frecuencia (una
        # captura a Caja PC no aparece más rápido por escanear más
        # seguido). Se desacopla a un intervalo propio en segundos
        # de reloj (no en cantidad de ciclos, para no depender de
        # `refresh_ms`) -- entre escaneos se sigue usando el último
        # resultado cacheado, así que NuzlockeService.update() nunca
        # se queda sin `boxed_party` y la detección de capturas a
        # Caja PC no se pierde, solo se vuelve un poco menos
        # inmediata (hasta BOX_SCAN_INTERVAL_SECONDS de demora).
        self._last_box_scan_time = 0.0
        self._last_fossil_scan_time = 0.0
        self._cached_boxed_party = []

        # Bloque 5 (24/09/2026, guía siguiente versión): identificación
        # de la PARTIDA por Trainer ID. `storage_resolver(process_name,
        # identity_o_None, nicknames_fn)` devuelve el NuzlockeStorage
        # que corresponde (ver Application._resolve_nuzlocke_storage()).
        # Sin resolver (None, el default) todo se comporta como antes
        # de este bloque: el storage lo elige quien construyó el
        # servicio y no se lee ninguna identidad.
        self._storage_resolver = storage_resolver
        # Inyectable para que los tests no escriban en data/ real.
        self._badges_storage_factory = BadgesStorage.for_identity
        self._trainer = None
        self._trainer_process = None
        self._pending_trainer = None
        self._pending_trainer_cycles = 0
        self._trainer_unreadable_cycles = 0
        self._trainer_fallback = False

    # Ciclos seguidos con party vacía estando "conectado" antes de
    # forzar una reconexión (25 ciclos de 200ms ≈ 5s).
    EMPTY_PARTY_RECONNECT_CYCLES = 25

    # Intervalo mínimo, en segundos de reloj, entre dos escaneos de
    # las 7 Cajas PC (Bloque 1.1) -- 1.5s es un punto intermedio
    # dentro del rango 1-2s sugerido en la guía: suficientemente
    # espaciado para dejar de competir por el lock de citra.py en
    # cada ciclo de 200ms, sin demorar de más la detección de una
    # captura depositada directo en caja.
    BOX_SCAN_INTERVAL_SECONDS = 1.5
    BOX_SCAN_INTERVAL_SECONDS = 1.5

    # Cada cuánto se relee la cantidad de fósiles de la bolsa (P3; solo
    # juegos cuyo perfil declara objetos de fósil).
    FOSSIL_SCAN_INTERVAL_SECONDS = 1.0

    # Bloque 5: lecturas seguidas IGUALES de una identidad nueva antes
    # de confirmarla (evita que una lectura basura durante una carga
    # cambie de partida), y ciclos de 200ms (~5s) con party visible
    # sin poder leer la identidad antes de caer al archivo por juego.
    TRAINER_CONFIRM_CYCLES = 2
    TRAINER_FALLBACK_CYCLES = 25

    def _reset_connection_dependent_state(self):
        """
        Al perder la conexión con Azahar se descarta todo lo que
        depende de una lectura continua del combate: si se cerró
        Azahar en medio de un combate salvaje, al reconectar NO debe
        interpretarse como "fin de combate" y registrar un perdido
        falso con el snapshot viejo.
        """

        self._empty_party_cycles = 0
        self._combat_was_active = False
        self._combat_wild_seen = False
        self._lost_encounter_snapshot = None
        self._lost_tracking_resolved = False
        self._pending_lost_resolution = None
        self._lost_log_seen = set()

        # Bloque 1.1: forzar un escaneo de cajas fresco en el
        # próximo ciclo tras reconectar, en vez de esperar hasta
        # BOX_SCAN_INTERVAL_SECONDS con el último resultado cacheado
        # de la conexión anterior (podría corresponder a otro juego
        # si Azahar cambió de proceso).
        self._last_box_scan_time = 0.0
        self._last_fossil_scan_time = 0.0

        self._reset_trainer_state()

    def _reset_trainer_state(self):
        self._trainer = None
        self._trainer_process = None
        self._pending_trainer = None
        self._pending_trainer_cycles = 0
        self._trainer_unreadable_cycles = 0
        self._trainer_fallback = False
        self.state.trainer = None

    def reset_trainer_identity(self):
        """
        Olvida la identidad de partida actual para que se vuelva a
        leer y confirmar desde cero. Application.restart_reader() lo
        llama al cambiar de juego (ese camino no pasa por una
        desconexión, así que nada más limpiaría la identidad vieja).
        """

        self._reset_trainer_state()

    def _known_nicknames(self, party):
        names = {
            pokemon.get("nickname")
            for pokemon in party
            if pokemon.get("nickname")
        }

        try:
            for pokemon in self.reader.read_boxes_range():
                if pokemon.get("nickname"):
                    names.add(pokemon.get("nickname"))
        except Exception:
            # Sin poder leer las cajas, la party sola alcanza para
            # reconocer la mayoría de los casos.
            pass

        return names

    def _resolve_trainer_identity(self, party):
        """
        Bloque 5: decide si ya se puede rastrear el Nuzlocke este ciclo
        y mantiene NuzlockeService apuntando al archivo de la PARTIDA
        cargada. Devuelve True si se puede rastrear.

        - Sin `storage_resolver`: siempre True (comportamiento previo).
        - Mientras la identidad no esté confirmada (o esté cambiando)
          devuelve False: reconciliar la party de una partida contra
          el archivo de otra mezclaría datos.
        - Lectura dudosa (None) con identidad ya conocida: se conserva
          la que había.
        - Si nunca se logra leer con party visible durante
          TRAINER_FALLBACK_CYCLES ciclos, se cae al archivo por juego
          (comportamiento previo) en vez de dejar el Nuzlocke sin
          funcionar.
        """

        if self._storage_resolver is None:
            return True

        process_name = self.reader.process_name

        if (
            self._trainer_process is not None
            and self._trainer_process != process_name
        ):
            # El juego cambió por debajo, sin pasar por una desconexión.
            self._reset_trainer_state()

        current = self.reader.read_trainer_identity()

        if current is None:
            if self._trainer is not None or self._trainer_fallback:
                return True

            self._trainer_unreadable_cycles += 1

            if self._trainer_unreadable_cycles >= self.TRAINER_FALLBACK_CYCLES:
                self._enter_trainer_fallback(process_name)
                return True

            return False

        self._trainer_unreadable_cycles = 0

        if current == self._trainer:
            self._pending_trainer = None
            self._pending_trainer_cycles = 0
            return True

        if current == self._pending_trainer:
            self._pending_trainer_cycles += 1
        else:
            self._pending_trainer = current
            self._pending_trainer_cycles = 1

        if self._pending_trainer_cycles < self.TRAINER_CONFIRM_CYCLES:
            return False

        return self._apply_trainer_identity(current, party)

    def _apply_trainer_identity(self, identity, party):
        process_name = self.reader.process_name

        try:
            storage = self._storage_resolver(
                process_name,
                identity,
                lambda: self._known_nicknames(party),
            )
        except Exception as error:
            print(
                f"[Partida] No se pudo abrir el archivo de esta partida: "
                f"{error}",
                flush=True,
            )
            return False

        # Descarta todo el seguimiento de la partida anterior (perdidos,
        # cajas cacheadas) y recién después fija la identidad nueva.
        self._reset_connection_dependent_state()

        self.nuzlocke_service.switch_storage(storage)
        self._cached_boxed_party = []

        # Medallas: mismo archivo por partida; `_last_badges = None`
        # fuerza guardar la lectura actual en el archivo nuevo.
        self.badges_storage = self._badges_storage_factory(
            process_name, identity["tid"], identity["sid"]
        )
        self._last_badges = None

        self._trainer = identity
        self._trainer_process = process_name
        self.state.trainer = dict(identity)

        path = getattr(storage, "path", None)
        file_name = getattr(path, "name", "?")

        print(
            f"[Partida] Entrenador '{identity['ot']}' "
            f"(TID {identity['tid']} / SID {identity['sid']}) -> "
            f"{file_name}",
            flush=True,
        )

        return True

    def _enter_trainer_fallback(self, process_name):
        print(
            "[Partida] No se pudo leer el Trainer ID de la partida: se usa "
            "el archivo por juego.",
            flush=True,
        )

        self._trainer_fallback = True
        self._trainer_process = process_name

        try:
            self.nuzlocke_service.switch_storage(
                self._storage_resolver(process_name, None, None)
            )
            self.badges_storage = BadgesStorage()
            self._last_badges = None
        except Exception as error:
            print(f"[Partida] Fallback falló: {error}", flush=True)

    def _log_lost(self, key, message):
        """print() de una sola vez por combate por `key`."""

        if key in self._lost_log_seen:
            return

        self._lost_log_seen.add(key)
        print(f"[Perdido] {message}", flush=True)

    # Cuántos ciclos de 200ms se reintenta el contador de capturas
    # antes de concluir "perdido" -- 1.5s de margen total, suficiente
    # para la transición de vuelta al mapa tras una captura real sin
    # demorar de más un "perdido" genuino (huida/derrota).
    LOST_ENCOUNTER_MAX_RETRIES = 8

    # Especie/nickname provisional de un "perdido" cuando no se pudo
    # leer el rival (editable después desde el panel).
    UNKNOWN_LOST_SPECIES = "Desconocido"

    def update(self):
        """Actualiza el estado realtime de DexRelay."""

        if not self.reader.is_connected():
            connected = self.reader.connect()

            if not connected:
                self.state.azahar_connected = False
                self.state.reader_active = False
                self._reset_connection_dependent_state()
                return

        self.state.azahar_connected = True

        party = self.reader.read_party()

        if not party:
            self.state.reader_active = False

            # Red de seguridad (18/09/2026): "conectado" pero sin
            # ningún dato durante ~5s puede ser un proceso
            # seleccionado equivocado tras reabrir Azahar. Forzar
            # una reconexión completa (find_game_process +
            # set_process). Con el juego en el menú y sin Pokémon
            # todavía es inofensivo: solo repite la búsqueda.
            self._empty_party_cycles += 1

            if self._empty_party_cycles >= self.EMPTY_PARTY_RECONNECT_CYCLES:
                self._empty_party_cycles = 0
                print(
                    "[Runtime] Sin datos de party hace un rato: "
                    "se fuerza una reconexión con el juego.",
                    flush=True,
                )
                self.reader.invalidate_connection()

            return

        self._empty_party_cycles = 0

        self.state.team = party
        self.state.reader_active = True
        self.state.team = party
        self.state.reader_active = True

        # Bloque 5: sin identidad de partida confirmada no se toca el
        # Nuzlocke (ni capturas, ni muertes, ni perdidos).
        tracking_ready = self._resolve_trainer_identity(party)

        # Detección de capturas nuevas (26-27/08/2026, reemplaza al
        # viejo camino de dos etapas por TOTAL_CAUGHT_ADDRESS +
        # LAST_CAUGHT_ADDRESS -- ver Documento Maestro sección 14,
        # "Detección de capturas en la Caja PC", y el comentario en
        # NuzlockeService.update() sobre por qué se separó de nuevo
        # por destino):
        #
        # - Las capturas que van a la PARTY se detectan directo en
        #   NuzlockeService.update() comparando `party` contra el
        #   roster guardado -- no hace falta nada especial acá.
        # - Las capturas que van a la CAJA PC (party llena) nunca
        #   aparecen en `party`, así que se escanean las Cajas PC
        #   reales (AzaharReader.read_boxes_range(), confirmado
        #   empíricamente contiguas) y se pasan como `boxed_party`.
        #
        # 07/09/2026 (a pedido del usuario, bug real): antes solo se
        # escaneaba la Caja 1 (read_box()) -- una captura depositada
        # directo en la Caja 2+ (algo que pasa apenas se llena la
        # Caja 1) nunca se registraba en el Nuzlocke Tracker.
        # read_boxes_range() ahora cubre las 7 cajas que el juego
        # trae habilitadas de fábrica en una sola lectura UDP (ver
        # su docstring en azahar_reader.py) -- comprar más cajas es
        # opcional y no todos los Nuzlocke lo necesitan, así que no
        # se escanea más allá de esto por defecto.
        #
        # Bloque 1.1 (22/09/2026): desacoplada del ciclo de 200ms,
        # ver el comentario junto a BOX_SCAN_INTERVAL_SECONDS en
        # __init__ -- se relee solo cada BOX_SCAN_INTERVAL_SECONDS,
        # reutilizando el último resultado el resto de los ciclos.
        now = self._time_source()

        if (
            now - self._last_box_scan_time
            >= self.BOX_SCAN_INTERVAL_SECONDS
        ):
            self._cached_boxed_party = self.reader.read_boxes_range()
            self._last_box_scan_time = now

        box = self._cached_boxed_party

        # Bloque 4.4 (23/09/2026, guía siguiente versión): solo se
        # lee la bolsa (400 casilleros, una UDP extra) mientras el
        # Nuzlocke todavía no arrancó -- una vez que
        # NuzlockeService confirma `nuzlocke_started`, se deja de
        # gastar esa lectura para siempre (ver
        # NuzlockeService.is_started()/update()).
        has_pokeballs = None

        if tracking_ready:
            if not self.nuzlocke_service.is_started():
                has_pokeballs = self.reader.read_has_pokeballs()

            # P3 (06/10/2026): en juegos cuyo perfil declara objetos de
            # fósil (Kalos), la bolsa se relee cada
            # FOSSIL_SCAN_INTERVAL_SECONDS (la baja precede 13-15 s al
            # Pokémon, no hace falta cada ciclo de 200 ms). ORAS no
            # declara ninguno y no gasta esta lectura.
            fossil_count = None
            profile = getattr(self.reader, "profile", None)

            if (
                profile is not None
                and profile.content.special_rules.fossil_item_ids
                and now - self._last_fossil_scan_time
                >= self.FOSSIL_SCAN_INTERVAL_SECONDS
            ):
                fossil_count = self.reader.read_fossil_item_count()
                self._last_fossil_scan_time = now

            # `fossil_count` viaja solo cuando se leyó en este ciclo
            # (los servicios de prueba sin esta señal no lo reciben).
            extra = (
                {"fossil_count": fossil_count}
                if fossil_count is not None
                else {}
            )

            self.state.nuzlocke = self.nuzlocke_service.update(
                party,
                boxed_party=box,
                has_pokeballs=has_pokeballs,
                **extra,
            )

        badges = self.badges_service.read_badges()

        self.state.badges = badges

        # Bloque 5: con la partida sin identificar no se guarda (iría al
        # archivo de otra partida); `state.badges` sí se actualiza.
        if tracking_ready and badges != self._last_badges:
            self.badges_storage.save(badges)
            self._last_badges = badges.copy()

        combat_hp = self.combat_service.read()

        if combat_hp is LECTURA_DESCARTADA:
            # Lectura inconsistente (el puntero cambió a mitad de
            # lectura): se descarta y se conserva el último estado
            # de combate válido, en vez de corromper el JSON.
            pass

        elif combat_hp is None:
            # base_address == 0: no hay combate activo.
            self.state.combat_active = False
            self.state.combat_hp = None

        else:
            self.state.combat_active = True
            self.state.combat_hp = combat_hp

        # Multi-version (30/08/2026): CURRENT_ZONE_ID_ADDRESS ya
        # esta confirmada para las dos versiones (ver
        # get_current_zone_id_address() en pointers.py) --
        # AzaharReader.read_current_zone_id() elige la correcta
        # solo. La guardia que desactivaba esto por completo en
        # Omega Ruby (bug real: "Zona 0" fantasma con la
        # direccion vieja de Alpha Sapphire) ya no hace falta --
        # sigue pendiente confirmar COMBAT_POINTER_ADDRESS/
        # WILD_BATTLE_FLAG_OFFSET en Omega Ruby, que es lo
        # proximo en la lista.
        if tracking_ready:
            self._resolve_pending_lost_encounter()
            self._update_lost_encounter_tracking()

    def _resolve_pending_lost_encounter(self):
        """
        Reintento del contador de capturas tras el fin de un combate
        salvaje (10/09/2026, bug real -- ver el comentario largo
        junto a `_pending_lost_resolution` en __init__). Se llama
        TODOS los ciclos, haya o no combate activo -- justo antes de
        `_update_lost_encounter_tracking()`, para no interferir con
        el snapshot de un combate nuevo si el jugador ya entró a otro
        mientras esto seguía pendiente (caso límite improbable en
        1.5s, pero se resuelve solo: acá abajo se descarta el
        pendiente ni bien se agotan los reintentos, dejando el
        camino libre).
        """

        if self._pending_lost_resolution is None:
            return

        total_after = self.reader.read_total_caught_count()

        # CORRECCIÓN (10/09/2026, segunda vuelta -- reportado por el
        # usuario: el bug seguía pasando después del primer arreglo,
        # justo tras reiniciar/cargar estado en Azahar en medio de la
        # sesión). Causa: una lectura FALLIDA (total_after es None,
        # típico durante la reconexión tras un reinicio del
        # emulador -- ver el WinError 10054 real que reportó el
        # usuario en el log) gastaba un reintento igual, sin haber
        # confirmado nada. Si la conexión estuvo inestable varios
        # ciclos seguidos justo en la ventana de reintento, se podían
        # agotar los 8 intentos sin haber llegado a leer el contador
        # ya actualizado ni una sola vez -- concluía "perdido" a
        # pesar de la captura real, igual que el bug original. Ahora
        # una lectura fallida NO cuenta como intento: se reintenta el
        # próximo ciclo sin tocar `retries_left`, mismo criterio que
        # ya usa el resto del proyecto para lecturas transitorias
        # fallidas (ver el flag salvaje más abajo, o
        # read_total_caught_count() mismo).
        if total_after is None:
            return

        if total_after > self._pending_lost_resolution["total_caught"]:
            # Subió de verdad: fue una captura real, que ya se
            # registra sola por el camino normal de party/Caja PC.
            # No hace falta (ni corresponde) registrar "perdido".
            print(
                "[Perdido] contador de capturas subió "
                f"({self._pending_lost_resolution['total_caught']} -> "
                f"{total_after}): captura real, no se registra "
                "perdido.",
                flush=True,
            )
            self._pending_lost_resolution = None
            return

        self._pending_lost_resolution["retries_left"] -= 1

        if self._pending_lost_resolution["retries_left"] > 0:
            # Todavía no se agotaron los reintentos -- puede ser el
            # mismo tipo de escritura progresiva ya documentado en
            # otros lugares del proyecto, se reintenta el próximo
            # ciclo sin concluir nada todavía.
            return

        species = self._pending_lost_resolution["species"]

        if not species:
            # Última chance: el buffer del rival puede haberse
            # poblado durante el combate. Si no, placeholder
            # honesto (nunca se inventa una especie).
            species = (
                self.reader.read_wild_rival_species()
                or self.UNKNOWN_LOST_SPECIES
            )

        print(
            "[Perdido] contador sin cambios tras "
            f"{self.LOST_ENCOUNTER_MAX_RETRIES} reintentos "
            f"(total={total_after}): registrando "
            f"{self._pending_lost_resolution['location']} como "
            f"perdido ({species}).",
            flush=True,
        )

        self.nuzlocke_service.register_lost_encounter(
            self._pending_lost_resolution["location"],
            species,
        )

        self._pending_lost_resolution = None

    def _zone_name_resolver(self):
        """Resolvedor id de zona -> nombre del juego actual, o None."""

        profile = getattr(self.reader, "profile", None)

        if profile is None or not profile.capabilities.has_zone_names:
            return None

        return profile.content.zone_name_resolver

    def current_place_name(self):
        """
        Nombre del catálogo del lugar donde está el jugador ahora
        (zona de memoria -> tabla de zonas del juego), o None si el
        juego no tiene tabla, la lectura falló o la zona no está
        mapeada. Lo usa NuzlockeService para anclar las filas
        especiales (P3).
        """

        resolver = self._zone_name_resolver()

        if resolver is None:
            return None

        zone_id = self.reader.read_current_zone_id()

        if zone_id is None:
            return None

        return resolver(zone_id)

    def _update_lost_encounter_tracking(self):
        """
        Detección automática del estado "perdido" del Nuzlocke
        Tracker (27/08/2026, ver
        DexRelay_Contexto_Deteccion_Perdido.md): cuando el primer
        combate salvaje en una ruta termina sin captura, esa ruta
        se registra sola como "perdido" -- sin distinguir huida de
        derrota (simplificación explícita del usuario).

        - Mientras el combate esté activo y todavía no se haya
          resuelto si corresponde un snapshot (`_lost_tracking_resolved`
          sigue en False), se reintenta CADA ciclo si
          `read_wild_flag()` ya da salvaje -- NO alcanza con mirarlo
          una sola vez en el instante exacto en que el puntero pasa
          a activo (bug real encontrado y confirmado en el juego el
          28/08/2026: el juego puede tardar uno o más ciclos de
          200ms en terminar de escribir la tabla de datos del
          encuentro salvaje que lee WILD_BATTLE_FLAG_OFFSET, el
          mismo tipo de escritura progresiva que ya obligó al
          "Intento 3" del nickname/ruta de LAST_CAUGHT_ADDRESS.
          Leer una sola vez, justo en el primer ciclo, podía
          capturar un 0 transitorio y quedarse fijado en
          "entrenador" para siempre -- validado con una partida
          real: reintentar cada ciclo lo resuelve).
        - Si la ruta actual (pieza 1) ya tiene un encuentro
          registrado, se marca resuelto sin snapshot (no hace falta
          reintentar cada ciclo restante del combate).
        - Al terminar el combate (puntero vuelve a inactivo): si
          había un snapshot pendiente, NO se decide en el momento --
          se arma una resolución pendiente que
          _resolve_pending_lost_encounter() reintenta cada ciclo
          hasta LOST_ENCOUNTER_MAX_RETRIES veces, recién ahí
          concluyendo "perdido" si el contador nunca subió (bug real
          corregido 10/09/2026, ver el comentario junto a
          `_pending_lost_resolution` en __init__: decidir en el
          mismo ciclo podía agarrar el contador todavía sin
          actualizar tras una captura real, duplicando el encuentro).
        - `_lost_tracking_resolved` se reinicia a False recién
          cuando el combate termina, así el próximo combate salvaje
          vuelve a tener sus propios intentos.

        Un combate de ENTRENADOR activo (wild_result == False) no
        dispara ningún snapshot, pero SÍ cuenta como "combate
        activo" para no confundir la transición de fin de combate.
        """

        # Bloque 4.4 (23/09/2026): sin sentido gastar la lectura de
        # memoria del flag salvaje (ni ensuciar Logs con "[Perdido]
        # ...") mientras el Nuzlocke todavía no arrancó -- ver el
        # guard real y autoritativo en
        # NuzlockeService.register_lost_encounter(), este es solo
        # para no hacer trabajo de más ni confundir con líneas de
        # log que de todos modos no iban a terminar en nada.
        if not self.nuzlocke_service.is_started():
            return

        # Bloque 13: sin tabla de zonas del juego conectado no hay
        # forma de nombrar la ruta, así que la detección automática
        # de "perdido" queda apagada para ese juego (en vez de usar
        # los nombres de zona de Hoenn).
        if self._zone_name_resolver() is None:
            return

        wild_result = self.combat_service.read_wild_flag()

        if wild_result is LECTURA_DESCARTADA:
            # Lectura inconsistente (el puntero cambió a mitad de
            # lectura): se reintenta el próximo ciclo, sin tocar
            # el estado de tracking.
            return

        combat_active_now = wild_result is not None

        if combat_active_now and not self._combat_was_active:
            # Diagnóstico (23/09/2026, ver read_combat_base_pointer()
            # en combat_service.py): logueamos el valor crudo del
            # puntero -- no cambia ninguna decisión, es para tener
            # evidencia dura la próxima vez que se sospeche un
            # falso positivo como el reportado por el usuario.
            base_pointer = self.combat_service.read_combat_base_pointer()
            base_pointer_hex = (
                hex(base_pointer) if base_pointer is not None else "?"
            )
            self._log_lost(
                "combat_start",
                "combate detectado (puntero de combate activo, "
                f"base={base_pointer_hex}).",
            )

        if wild_result is True:
            self._combat_wild_seen = True
            self._log_lost(
                "wild_flag",
                "flag salvaje = SALVAJE.",
            )

        if (
            combat_active_now
            and wild_result is True
            and self._lost_encounter_snapshot is None
            and not self._lost_tracking_resolved
        ):

            zone_id = self.reader.read_current_zone_id()
            location = self._zone_name_resolver()(zone_id)

            already_registered = (
                location is not None
                and self.nuzlocke_service.has_encounter_for_location(
                    location
                )
            )

            if location is None:
                # Lectura de zona fallida -- no marcar resuelto,
                # reintentar el próximo ciclo (podría ser
                # transitorio, igual que el flag salvaje).
                self._log_lost(
                    "zone_none",
                    "no se pudo leer la zona actual "
                    f"(zone_id={zone_id}); se reintenta.",
                )

            elif already_registered:
                self._log_lost(
                    f"already:{location}",
                    f"{location} ya tiene un encuentro registrado: "
                    "no se toma snapshot.",
                )
                # Esta ruta ya tiene un resultado -- no tomar
                # snapshot, y no hace falta reintentar el resto de
                # este combate (la ruta no va a "desregistrarse" a
                # mitad de la pelea).
                self._lost_tracking_resolved = True

            else:

                total_caught = self.reader.read_total_caught_count()
                species = self.reader.read_wild_rival_species()

                # 18/09/2026 (log real del usuario: combate salvaje en
                # Pueblo Azuliza con total_caught=9 y
                # last_caught.species=None): la ESPECIE del rival
                # dejó de ser requisito del snapshot. Solo se usa como
                # nickname/especie provisional del "perdido" (que el
                # usuario puede editar), y LAST_CAUGHT_ADDRESS no
                # devuelve un Pokémon válido en su partida -- exigirla
                # bloqueaba TODA la detección. Lo que decide si hubo
                # captura es el contador, no la especie.
                if total_caught is not None:

                    self._lost_encounter_snapshot = {
                        "location": location,
                        "species": species,
                        "total_caught": total_caught,
                    }

                    self._log_lost(
                        "snapshot",
                        f"snapshot tomado: {location}, rival="
                        f"{species!r}, total_caught={total_caught}.",
                    )

                else:
                    self._log_lost(
                        "snapshot_wait",
                        f"sin snapshot en {location}: "
                        f"total_caught={total_caught} "
                        "(se reintenta cada ciclo).",
                    )

                # Si total_caught/species vinieron None, no se
                # marca resuelto -- se reintenta el próximo ciclo
                # (mismo criterio que el flag salvaje: puede ser
                # una escritura progresiva del juego, no un dato
                # definitivo).

        # La especie del rival puede tardar unos ciclos en escribirse
        # (o el buffer traer al rival del combate ANTERIOR al
        # principio), así que mientras dura el combate salvaje se
        # sigue actualizando: la última lectura válida es la buena.
        if (
            wild_result is True
            and self._lost_encounter_snapshot is not None
        ):
            latest_species = self.reader.read_wild_rival_species()

            if (
                latest_species
                and latest_species
                != self._lost_encounter_snapshot["species"]
            ):
                self._lost_encounter_snapshot["species"] = latest_species
                print(
                    f"[Perdido] rival actualizado: {latest_species}.",
                    flush=True,
                )

        if not combat_active_now and self._combat_was_active:

            if self._lost_encounter_snapshot is not None:
                print(
                    "[Perdido] fin de combate con snapshot de "
                    f"{self._lost_encounter_snapshot['location']}: "
                    "esperando el contador de capturas.",
                    flush=True,
                )
            elif self._combat_wild_seen:
                print(
                    "[Perdido] fin de combate salvaje SIN snapshot: "
                    "no se registra nada (ver líneas anteriores "
                    "para el motivo).",
                    flush=True,
                )
            else:
                print(
                    "[Perdido] fin de combate (el flag salvaje "
                    "nunca dio SALVAJE: entrenador o flag no "
                    "detectado).",
                    flush=True,
                )

            if self._lost_encounter_snapshot is not None:

                # CORRECCIÓN (10/09/2026, ver el comentario largo
                # junto a `_pending_lost_resolution` en __init__):
                # antes se decidía "perdido" acá mismo, con una sola
                # lectura de total_caught en este ciclo exacto. Ahora
                # solo se arma la resolución PENDIENTE -- quien
                # decide de verdad es _resolve_pending_lost_encounter(),
                # que reintenta cada ciclo (llamada desde update(),
                # antes que este método) hasta LOST_ENCOUNTER_MAX_RETRIES
                # veces antes de concluir "perdido" -- le da margen
                # real al juego para terminar de escribir el contador
                # tras una captura, en vez de fallar en el primer
                # instante posible.
                self._pending_lost_resolution = {
                    "location": self._lost_encounter_snapshot["location"],
                    "species": self._lost_encounter_snapshot["species"],
                    "total_caught": self._lost_encounter_snapshot[
                        "total_caught"
                    ],
                    "retries_left": self.LOST_ENCOUNTER_MAX_RETRIES,
                }

            # Se reinicia siempre al terminar el combate (haya
            # habido snapshot o no -- por ejemplo, un combate de
            # entrenador genuino nunca toma snapshot pero igual
            # tiene que resetear _lost_tracking_resolved para que
            # el próximo combate salvaje tenga sus propios
            # intentos).
            self._lost_encounter_snapshot = None
            self._lost_tracking_resolved = False
            self._combat_wild_seen = False
            self._lost_log_seen = set()

        self._combat_was_active = combat_active_now
