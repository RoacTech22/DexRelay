from __future__ import annotations

from datetime import datetime, timezone


def _now_iso() -> str:
    """Timestamp UTC en formato ISO 8601, con precisión de segundos."""

    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
    )


class NuzlockeService:
    """
    Detecta capturas nuevas y muertes persistentes comparando la
    party actual contra el roster/graveyard guardados.

    Identidad de cada Pokémon: el nickname. Es la misma lógica ya
    validada en el prototipo (PokeOverlay,
    azahar_reader_nuzlocke_realtime.py: pokemon_identity,
    is_already_dead, register_death, update_death_detector), portada
    a la arquitectura de servicios actual.

    Por qué nickname solo, y no nickname + speciesId (como en las
    animaciones del Team Overlay): el overlay compara el mismo slot
    entre dos ciclos consecutivos, así que necesita notar el cambio
    de especie para animar la evolución. Acá el objetivo es
    identidad ESTABLE a través de toda la partida -- una evolución
    no debe crear un registro nuevo en el roster, tiene que
    actualizar el mismo.

    Limitación conocida (heredada del prototipo original): si el
    jugador no le pone nickname a una captura, el nombre por
    defecto suele ser el de la especie, que cambia solo al
    evolucionar -- en ese caso se pierde la continuidad de
    identidad entre la pre-evolución y la post-evolución. Para
    Nuzlocke esto rara vez es un problema real porque la práctica
    estándar es nombrar cada captura, pero queda documentado.

    Una vez que un nickname aparece en el cementerio, no vuelve a
    entrar al roster aunque su HP actual sea > 0 -- la muerte es
    historial permanente, no depende de curarse después (ver
    Documento Maestro, sección 3: "Estado actual vs. historial").
    """

    def __init__(self, storage) -> None:
        self.storage = storage
        self._data = None

    def update(self, team: list[dict]) -> dict:
        """
        Compara la party actual contra el estado guardado, detecta
        capturas/evoluciones/muertes, persiste solo si hubo
        cambios, y devuelve el estado actual completo
        (roster + graveyard).
        """

        if self._data is None:
            self._data = self.storage.load()

        roster = self._data["roster"]
        graveyard = self._data["graveyard"]

        roster_by_nickname = {
            entry["nickname"]: entry
            for entry in roster
        }

        graveyard_nicknames = {
            entry["nickname"]
            for entry in graveyard
        }

        changed = False

        for pokemon in team:

            if not pokemon or pokemon.get("empty"):
                continue

            nickname = pokemon.get("nickname")

            if not nickname:
                continue

            # Ya está en el cementerio: la muerte es permanente,
            # no reaparece en el roster aunque el HP actual sea > 0.
            if nickname in graveyard_nicknames:
                continue

            species_id = pokemon.get("speciesId")
            species = pokemon.get("species")
            level = pokemon.get("level")
            hp = pokemon.get("hp")

            entry = roster_by_nickname.get(nickname)

            if entry is None:

                # Captura nueva.
                entry = {
                    "nickname": nickname,
                    "speciesId": species_id,
                    "species": species,
                    "level": level,
                    "caughtAt": _now_iso(),
                }

                roster.append(entry)
                roster_by_nickname[nickname] = entry

                changed = True

            elif (
                entry.get("speciesId") != species_id
                or entry.get("level") != level
            ):

                # Evolución y/o subida de nivel: actualiza el
                # mismo registro, no crea uno nuevo.
                entry["speciesId"] = species_id
                entry["species"] = species
                entry["level"] = level

                changed = True

            is_dead = (
                hp is not None
                and hp <= 0
            )

            if is_dead:

                roster.remove(entry)
                del roster_by_nickname[nickname]

                graveyard.append({
                    "nickname": nickname,
                    "speciesId": species_id,
                    "species": species,
                    "level": level,
                    "diedAt": _now_iso(),
                })

                graveyard_nicknames.add(nickname)

                changed = True

        if changed:
            self._data["roster"] = roster
            self._data["graveyard"] = graveyard
            self.storage.save(self._data)

        return self._data

    # =====================================
    # BLOQUE C: ENCUENTROS POR RUTA
    #
    # A diferencia de roster/graveyard, esto no se
    # deriva de la memoria del juego -- lo carga el
    # usuario a mano desde el panel de control
    # (panels/nuzlocke/). Un registro por ubicación
    # (se actualiza el mismo si ya existía en vez de
    # duplicar), identificado por el texto exacto de
    # `location`.
    # =====================================

    VALID_ENCOUNTER_RESULTS = (
        "sin_intentar",
        "atrapado",
        "perdido",
    )

    def get_encounters(self) -> list[dict]:
        """Devuelve la lista actual de encuentros registrados."""

        if self._data is None:
            self._data = self.storage.load()

        self._data.setdefault("encounters", [])

        return self._data["encounters"]

    def save_encounter(
        self,
        location: str,
        species: str,
        result: str,
    ) -> list[dict]:
        """
        Crea o actualiza el registro de encuentro de una
        ubicación. Devuelve la lista completa de encuentros
        ya actualizada.
        """

        if result not in self.VALID_ENCOUNTER_RESULTS:
            raise ValueError(
                f"Resultado invalido: {result!r}. "
                f"Debe ser uno de {self.VALID_ENCOUNTER_RESULTS}."
            )

        encounters = self.get_encounters()

        existing = next(
            (
                entry
                for entry in encounters
                if entry["location"] == location
            ),
            None,
        )

        if existing is None:

            encounters.append({
                "location": location,
                "species": species,
                "result": result,
                "updatedAt": _now_iso(),
            })

        else:

            existing["species"] = species
            existing["result"] = result
            existing["updatedAt"] = _now_iso()

        self.storage.save(self._data)

        return encounters
