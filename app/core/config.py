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

    def set(self, *keys, value):
        """
        Setea un valor anidado en memoria (no escribe a disco --
        para eso, save()). Requiere al menos una key. Crea los
        diccionarios intermedios que falten, igual que get() los
        recorre.
        """

        if not keys:
            raise ValueError("set() necesita al menos una key")

        target = self.data

        for key in keys[:-1]:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}

            target = target[key]

        target[keys[-1]] = value

    def save(self):
        """
        Persiste self.data a disco tal cual está en memoria. No se
        llama automáticamente desde set() a propósito -- para
        poder cambiar varios valores y guardar una sola vez.
        """

        with self.path.open("w", encoding="utf-8") as file:
            json.dump(self.data, file, indent=4, ensure_ascii=False)
