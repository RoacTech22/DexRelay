from __future__ import annotations

from app.core.state import ApplicationState
from app.readers.azahar_reader import AzaharReader
from app.services.badges_service import BadgesService


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

        self.state.badges = (
            self.badges_service.read_badges()
        )
        
