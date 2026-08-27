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
        #   aparecen en `party`, así que se escanea la caja real
        #   (AzaharReader.read_box(), array persistente confirmado
        #   empíricamente) y se pasa como `boxed_party`.
        box = self.reader.read_box()

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
