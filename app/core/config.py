import json
from pathlib import Path


class Config:
    def __init__(self, path="config.json"):
        self.path = Path(path)
        self.data = self._load()

    def _load(self):
        if not self.path.exists():
            raise FileNotFoundError(
                f"No se encontró el archivo de configuración: {self.path}"
            )

        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def get(self, *keys, default=None):
        value = self.data

        for key in keys:
            if not isinstance(value, dict) or key not in value:
                return default

            value = value[key]

        return value