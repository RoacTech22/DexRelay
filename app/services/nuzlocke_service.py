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

        self._data.setdefault("pending_encounters", [])
        self._data.setdefault("encounters", [])

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

                self._register_new_capture(
                    pokemon,
                    entry["caughtAt"],
                )

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

                # Sincronización con el panel de encuentros
                # (Bloque C): si ya existe un registro de
                # encuentro para este Pokémon (por nickname), su
                # estado pasa a 'muerto' automáticamente, sin
                # importar cuál fuera antes (capturado/shiny/etc).
                # No hace falta que el usuario lo actualice a mano.
                for encounter in self._data["encounters"]:

                    if encounter.get("nickname") == nickname:
                        encounter["status"] = "muerto"
                        encounter["updatedAt"] = _now_iso()

                changed = True

        if changed:
            self._data["roster"] = roster
            self._data["graveyard"] = graveyard
            self.storage.save(self._data)

        return self._data

    def _register_new_capture(
        self,
        pokemon: dict,
        caught_at: str,
    ) -> None:
        """
        Se llama justo cuando se detecta una captura nueva.

        Si el Pokémon ya trae resuelto el lugar de encuentro
        (`metLocation`, vía PKHeX -- ver LocationResolver en
        azahar_reader.py), el encuentro se registra directo en
        `encounters`, ruta incluida: automatización completa, sin
        que el usuario tenga que hacer nada.

        Si no hay lugar de encuentro disponible (huevo, regalo,
        intercambio, o el bridge PKHeX no resolvió nada), cae al
        flujo anterior: se guarda en `pending_encounters` para que
        el usuario le asigne la ruta a mano desde el panel.
        """

        nickname = pokemon.get("nickname")
        species_id = pokemon.get("speciesId")
        species = pokemon.get("species")
        met_location = pokemon.get("metLocation")
        is_shiny = bool(pokemon.get("shiny"))

        status = "shiny" if is_shiny else "capturado"

        if met_location:

            self.save_encounter(
                met_location,
                nickname,
                species,
                status,
            )

            return

        self._data["pending_encounters"].append({
            "nickname": nickname,
            "speciesId": species_id,
            "species": species,
            "shiny": is_shiny,
            "caughtAt": caught_at,
        })

    # =====================================
    # BLOQUE C: ENCUENTROS POR RUTA
    #
    # Un registro por ubicación (se actualiza el mismo si ya
    # existía en vez de duplicar), identificado por el texto
    # exacto de `location`. La mayoría de las capturas se
    # completan solas (ver _register_new_capture); lo que no se
    # pudo resolver automático se carga a mano desde el panel
    # (panels/nuzlocke/).
    # =====================================

    VALID_ENCOUNTER_STATUSES = (
        "sin_intentar",
        "capturado",
        "perdido",
        "muerto",
        "intercambiado",
        "regalo",
        "shiny",
    )

    def get_encounters(self) -> list[dict]:
        """Devuelve la lista actual de encuentros registrados."""

        if self._data is None:
            self._data = self.storage.load()

        self._data.setdefault("encounters", [])

        return self._data["encounters"]

    def get_pending_encounters(self) -> list[dict]:
        """
        Devuelve las capturas detectadas automáticamente que
        todavía no tienen una ruta asignada (porque PKHeX no pudo
        resolver el lugar de encuentro -- huevos, regalos,
        intercambios, o una lectura fallida del bridge).
        """

        if self._data is None:
            self._data = self.storage.load()

        self._data.setdefault("pending_encounters", [])

        return self._data["pending_encounters"]

    def assign_encounter_location(
        self,
        nickname: str,
        location: str,
    ) -> dict:
        """
        Asigna una ubicación a una captura pendiente: la saca de
        `pending_encounters` y la registra en `encounters`.
        Devuelve {'encounters': [...], 'pending_encounters': [...]}
        actualizados.
        """

        pending = self.get_pending_encounters()

        match = next(
            (
                entry
                for entry in pending
                if entry["nickname"] == nickname
            ),
            None,
        )

        if match is None:
            raise ValueError(
                f"No hay ninguna captura pendiente con "
                f"nickname {nickname!r}."
            )

        pending.remove(match)

        status = (
            "shiny"
            if match.get("shiny")
            else "capturado"
        )

        encounters = self.save_encounter(
            location,
            match["nickname"],
            match["species"],
            status,
        )

        return {
            "encounters": encounters,
            "pending_encounters": pending,
        }

    def save_encounter(
        self,
        location: str,
        nickname: str,
        species: str,
        status: str,
    ) -> list[dict]:
        """
        Crea o actualiza el registro de encuentro de una
        ubicación. Devuelve la lista completa de encuentros
        ya actualizada.
        """

        if status not in self.VALID_ENCOUNTER_STATUSES:
            raise ValueError(
                f"Estado invalido: {status!r}. "
                f"Debe ser uno de {self.VALID_ENCOUNTER_STATUSES}."
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
                "nickname": nickname,
                "species": species,
                "status": status,
                "updatedAt": _now_iso(),
            })

        else:

            existing["nickname"] = nickname
            existing["species"] = species
            existing["status"] = status
            existing["updatedAt"] = _now_iso()

        self.storage.save(self._data)

        return encounters
