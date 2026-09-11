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
            self.reader.memory
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
        self._update_lost_encounter_tracking()

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
          había un snapshot pendiente, compara el contador de
          capturas contra el del snapshot -- si no subió, se
          perdió. Si subió, no hace falta hacer nada (la captura ya
          se registra sola por el camino normal de party/Caja PC).
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

                total_after = self.reader.read_total_caught_count()

                if (
                    total_after is not None
                    and total_after
                    <= self._lost_encounter_snapshot["total_caught"]
                ):

                    self.nuzlocke_service.register_lost_encounter(
                        self._lost_encounter_snapshot["location"],
                        self._lost_encounter_snapshot["species"],
                    )

            # Se reinicia siempre al terminar el combate (haya
            # habido snapshot o no -- por ejemplo, un combate de
            # entrenador genuino nunca toma snapshot pero igual
            # tiene que resetear _lost_tracking_resolved para que
            # el próximo combate salvaje tenga sus propios
            # intentos).
            self._lost_encounter_snapshot = None
            self._lost_tracking_resolved = False

        self._combat_was_active = combat_active_now
