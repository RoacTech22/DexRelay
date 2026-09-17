from __future__ import annotations

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
from app.services.zone_names import resolve_zone_name


class Runtime:
    def __init__(
        self,
        reader: AzaharReader,
        state: ApplicationState,
        nuzlocke_service: NuzlockeService | None = None,
    ):
        self.reader = reader
        self.state = state

        self.badges_service = BadgesService(
            self.reader
        )

        self.combat_service = CombatService(
            self.reader.memory
        )

        self.badges_storage = BadgesStorage()

        # Se puede compartir la misma instancia con HTTPServer
        # (ver app.py) para que el panel de encuentros escriba
        # sobre los mismos datos que el resto del sistema lee.
        # Si no se pasa ninguna, crea la suya propia (compatibilidad
        # con código/tests existentes que construyen Runtime solo).
        self.nuzlocke_service = (
            nuzlocke_service
            or NuzlockeService(NuzlockeStorage())
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

    # Cuántos ciclos de 200ms se reintenta el contador de capturas
    # antes de concluir "perdido" -- 1.5s de margen total, suficiente
    # para la transición de vuelta al mapa tras una captura real sin
    # demorar de más un "perdido" genuino (huida/derrota).
    LOST_ENCOUNTER_MAX_RETRIES = 8

    def update(self):
        """Actualiza el estado realtime de DexRelay."""

        if not self.reader.is_connected():
            connected = self.reader.connect()

            if not connected:
                self.state.azahar_connected = False
                self.state.reader_active = False
                return

        self.state.azahar_connected = True

        party = self.reader.read_party()

        if not party:
            self.state.reader_active = False
            return

        self.state.team = party
        self.state.reader_active = True

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
        box = self.reader.read_boxes_range()

        self.state.nuzlocke = self.nuzlocke_service.update(
            party,
            boxed_party=box,
        )

        badges = self.badges_service.read_badges()

        self.state.badges = badges

        if badges != self._last_badges:
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
            self._pending_lost_resolution = None
            return

        self._pending_lost_resolution["retries_left"] -= 1

        if self._pending_lost_resolution["retries_left"] > 0:
            # Todavía no se agotaron los reintentos -- puede ser el
            # mismo tipo de escritura progresiva ya documentado en
            # otros lugares del proyecto, se reintenta el próximo
            # ciclo sin concluir nada todavía.
            return

        self.nuzlocke_service.register_lost_encounter(
            self._pending_lost_resolution["location"],
            self._pending_lost_resolution["species"],
        )

        self._pending_lost_resolution = None

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

        wild_result = self.combat_service.read_wild_flag()

        if wild_result is LECTURA_DESCARTADA:
            # Lectura inconsistente (el puntero cambió a mitad de
            # lectura): se reintenta el próximo ciclo, sin tocar
            # el estado de tracking.
            return

        combat_active_now = wild_result is not None

        if (
            combat_active_now
            and wild_result is True
            and self._lost_encounter_snapshot is None
            and not self._lost_tracking_resolved
        ):

            zone_id = self.reader.read_current_zone_id()
            location = resolve_zone_name(zone_id)

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
                pass

            elif already_registered:
                # Esta ruta ya tiene un resultado -- no tomar
                # snapshot, y no hace falta reintentar el resto de
                # este combate (la ruta no va a "desregistrarse" a
                # mitad de la pelea).
                self._lost_tracking_resolved = True

            else:

                total_caught = self.reader.read_total_caught_count()
                last_caught = self.reader.read_last_caught()

                species = (
                    last_caught.get("species")
                    if last_caught
                    else None
                )

                if total_caught is not None and species:

                    self._lost_encounter_snapshot = {
                        "location": location,
                        "species": species,
                        "total_caught": total_caught,
                    }

                # Si total_caught/species vinieron None, no se
                # marca resuelto -- se reintenta el próximo ciclo
                # (mismo criterio que el flag salvaje: puede ser
                # una escritura progresiva del juego, no un dato
                # definitivo).

        if not combat_active_now and self._combat_was_active:

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

        self._combat_was_active = combat_active_now
