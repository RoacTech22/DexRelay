class ApplicationState:
    def __init__(self):
        self.azahar_connected = False
        self.reader_active = False
        self.team = []
        self.badges = []
        self.combat_active = False
        self.combat_hp = None
        self.nuzlocke = {
            "roster": [],
            "graveyard": [],
        }
