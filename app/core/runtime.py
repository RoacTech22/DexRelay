from __future__ import annotations

from app.core.state import ApplicationState
from app.readers.azahar_reader import AzaharReader
from app.services.badges_service import BadgesService
from app.services.badges_storage import BadgesStorage


class Runtime:
    def __init__(
        self,
        reader: AzaharReader,
        state: ApplicationState,
    ):
        self.reader = reader
        self.state = state

        self.badges_service = BadgesService(
            self.reader.memory
        )

        self.badges_storage = BadgesStorage()

        self._last_badges = None

    def update(self):
        """Actualiza el estado realtime de DexRelay."""

        if not self.reader.is_connected():
            self.state.azahar_connected = False
            self.state.reader_active = False
            return

        self.state.azahar_connected = True

        party = self.reader.read_party()

        if party:
            self.state.team = party
            self.state.reader_active = True

        badges = self.badges_service.read_badges()

        self.state.badges = badges

        if badges != self._last_badges:
            self.badges_storage.save(badges)
            self._last_badges = badges.copy()
