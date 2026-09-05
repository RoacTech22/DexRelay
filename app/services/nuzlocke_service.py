from __future__ import annotations

from datetime import datetime, timezone


def _now_iso() -> str:
    """Timestamp UTC en formato ISO 8601, con precisión de segundos."""

    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
    )


# ID de ubicación de Rustboro City / "Ciudad Férrica" (traducción
# verificada en hoenn_locations_es.py), donde está Devon Corp --
# el único lugar del juego donde se revive un fósil (29/08/2026,
# a pedido del usuario, tras confirmar en el juego real que
# depender SOLO de cazar el placeholder "Egg" no es confiable: a
# diferencia de un huevo real, que tarda muchos pasos en nacer y
# por eso queda "Huevo" en memoria durante minutos, un fósil
# "nace" al instante -- la ventana en la que el nickname es
# literalmente "Egg" puede ser más corta que un ciclo de polling
# de 200ms, y se puede perder por completo).
#
# Señal de respaldo: en Rustboro City NO hay pasto salvaje, así
# que CUALQUIER Pokémon cuyo Met_Location resuelva a este ID no
# puede ser una captura salvaje real -- tiene que ser un fósil
# revivido. Se usa el ID, no el texto traducido, para no depender
# de que la traducción exista o coincida exactamente (mismo
# criterio que ya usa LocationCatalog/LocationResolver en otros
# lados del proyecto).
DEVON_CORP_LOCATION_ID = 190


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

        # Detección de "se fue por intercambio" (28/08/2026, ver
        # update()). Solo en memoria -- no hace falta persistir
        # esto entre reinicios de la app, el peor caso de perderlo
        # es no detectar UN intercambio si la app se reinicia justo
        # en el medio, un caso extremadamente raro.
        self._last_visible_nicknames = None

    def switch_storage(self, storage) -> None:
        """
        Cambia a qué archivo lee/escribe este servicio (02/09/2026,
        GUI v2 -- Application.restart_reader() la llama cuando
        detecta que el juego conectado cambió, con
        NuzlockeStorage.for_game() del juego nuevo).

        `self._data = None` fuerza que la próxima llamada a
        update() recargue desde el storage nuevo en vez de seguir
        usando el roster/cementerio del juego anterior todavía en
        memoria -- sin esto, el bug de "/overlay/nuzlocke muestra
        la partida de Omega Ruby con Alpha Sapphire abierto"
        seguiría pasando aunque el archivo en disco ya fuera el
        correcto, porque el caché en memoria no se habría
        actualizado.
        """

        self.storage = storage
        self._data = None
        self._last_visible_nicknames = None

    def reset_all(self) -> dict:
        """
        Botón "reiniciar todo" del panel (provisional): borra
        roster, graveyard, encounters, pending_encounters y
        starter_assigned -- vuelve a un estado como si DexRelay
        nunca hubiera visto esta partida. No toca config.json ni
        nada fuera del Nuzlocke Tracker.

        Devuelve el estado vacío recién guardado.

        El ruleset (04/09/2026, ver get_ruleset()/save_ruleset())
        NO se borra acá a propósito -- son las reglas de la casa
        que el jugador eligió para este Nuzlocke, no datos de la
        partida en sí. "Reiniciar todo" vuelve a empezar el
        registro de capturas/muertes/rutas, no te hace elegir de
        nuevo si jugás con dupes clause o no.
        """

        previous_ruleset = self.get_ruleset()

        self._data = {
            "roster": [],
            "graveyard": [],
            "encounters": [],
            "pending_encounters": [],
            "starter_assigned": False,
            "traded_away": [],
            "ignored_nicknames": [],
            "fossil_pending_species_ids": [],
            "ruleset": previous_ruleset,
        }

        self._last_visible_nicknames = None

        self.storage.save(self._data)

        return self._data

    def _reconcile_starter_rename(
        self,
        nickname: str,
        species_id: int,
        roster: list[dict],
        roster_by_nickname: dict,
    ) -> dict | None:
        """
        Caso especial del Inicial (27/08/2026, bug real reportado
        y confirmado con datos de partida real -- roster con
        "Mudkip" nivel 5 y "Daron" nivel 7, mismo speciesId, y
        "Inicial" apuntando solo al primero).

        En la pelea contra el Pokémon salvaje que ataca al
        profesor (justo al arrancar la partida), el inicial YA
        está en la party -- por eso se puede pelear con él -- pero
        todavía no pasó por el evento oficial del laboratorio
        donde el jugador le pone nombre. En ese momento el juego
        lo reporta con el nombre por defecto de la especie;
        DexRelay lo registra como "Inicial" ahí mismo (comportamiento
        correcto en general: registrar la party directo y sin
        espera). Después, en el laboratorio, el MISMO Pokémon
        aparece con el nickname real -- como la identidad acá es
        por nickname, sin este chequeo se trataría como una
        captura nueva: queda como entrada fantasma en el roster
        (bloqueada de convertirse en un segundo "Inicial" por la
        regla de especie repetida, pero sin limpiar el fantasma ni
        migrar la ruta).

        Detecta ese caso puntual: si ya existe un encuentro
        "Inicial" registrado, y el Pokémon de ese encuentro sigue
        en el roster con la MISMA especie que este nickname nuevo
        pero un nickname DISTINTO, se asume que es el mismo
        Pokémon renombrado -- migra la identidad completa (roster
        + encuentro "Inicial") al nickname nuevo, en vez de crear
        un registro aparte. El nivel se actualiza solo después,
        por el chequeo de evolución/nivel normal del loop (acá
        solo se migra la identidad).

        Devuelve el registro de roster ya migrado, o None si no
        aplica (no hay Inicial registrado todavía, coincide con el
        nickname actual, o no coincide la especie).
        """

        starter_encounter = next(
            (
                encounter
                for encounter in self._data.get("encounters", [])
                if encounter["location"] == "Inicial"
            ),
            None,
        )

        if starter_encounter is None:
            return None

        starter_nickname = starter_encounter.get("nickname")

        if starter_nickname == nickname:
            return None

        # Nunca "retroceder": si la lectura nueva es literalmente
        # "Huevo" pero el Inicial ya tiene un nombre posterior (no
        # "Huevo"), no es el mismo Pokémon renombrado -- es un
        # huevo distinto que todavía no nació (mismo criterio que
        # _reconcile_pending_rename(), 28/08/2026).
        if (
            nickname.strip().lower() == "huevo"
            and starter_nickname.strip().lower() != "huevo"
        ):
            return None

        starter_entry = roster_by_nickname.get(starter_nickname)

        if starter_entry is None:
            return None

        if starter_entry.get("speciesId") != species_id:
            return None

        roster.remove(starter_entry)
        del roster_by_nickname[starter_nickname]

        starter_entry["nickname"] = nickname
        roster.append(starter_entry)
        roster_by_nickname[nickname] = starter_entry

        starter_encounter["nickname"] = nickname
        starter_encounter["updatedAt"] = _now_iso()

        return starter_entry

    @staticmethod
    def _is_trade_location(met_location: str | None) -> bool:
        """
        True si `met_location` es el texto que el juego reporta
        para un Pokémon recibido por trueque (link trade, tanto
        con un NPC en un intercambio scriptado como con otro
        jugador real) -- en inglés, con el nombre del entrenador
        entre paréntesis (ej. "a Link Trade (NPC)", confirmado en
        el juego real el 28/08/2026). No hay ninguna ruta real
        asociada a esto -- se usa para decidir cuándo aplicar el
        pseudo-lugar "Intercambiado" en vez de mostrar ese texto.
        """

        if not met_location:
            return False

        return (
            met_location.strip().lower().startswith("a link trade")
        )

    @staticmethod
    def _is_placeholder_nickname(
        nickname: str | None,
        species: str | None,
    ) -> bool:
        """
        True si `nickname` todavía es un nombre "sin personalizar"
        -- el placeholder literal de un huevo sin nacer ("Huevo"),
        o el nombre por defecto de la especie (nickname == species,
        sin importar mayúsculas -- mismo patrón que ya se usaba
        para el Inicial: "Mudkip" antes de que el jugador elija
        "Daron" en el laboratorio).

        Usado por _reconcile_pending_rename() para identificar
        candidatos a migrar de identidad en vez de registrarse
        como una captura nueva.
        """

        if not nickname:
            return False

        normalized = nickname.strip().lower()

        if normalized == "huevo":
            return True

        if species and normalized == species.strip().lower():
            return True

        return False

    def _reconcile_pending_rename(
        self,
        nickname: str,
        species_id: int,
        roster: list[dict],
        roster_by_nickname: dict,
    ) -> dict | None:
        """
        Generaliza _reconcile_starter_rename() (que solo cubría el
        caso puntual del Inicial, atado a la existencia de un
        encuentro "Inicial") a CUALQUIER Pokémon cuyo nickname
        todavía no es definitivo. El mismo patrón se repite con
        los que nacen de un huevo, con una etapa más: el juego los
        reporta primero como "Huevo" (nickname placeholder, la
        especie ya está resuelta en el PK6 aunque todavía no
        nació), después con el nombre por defecto de la especie
        apenas nace (mismo patrón que una captura salvaje recién
        agarrada, sin renombrar todavía), y recién con el nickname
        real una vez que el jugador confirma el nombre.

        Bug real reportado el 28/08/2026: sin esto, cada
        transición se trataba como una captura nueva -- hasta 3
        registros de roster/encuentro distintos para el MISMO
        Pokémon (Huevo nv.1 -> Togepi nv.1 -> AA nv.6).

        Busca en el roster una entrada con la MISMA especie cuyo
        nickname actual todavía sea un placeholder (ver
        _is_placeholder_nickname). Si encuentra EXACTAMENTE UNA
        candidata migra la identidad completa (roster + encuentro
        + pendiente, si tenía) al nickname nuevo. Si encuentra 0 o
        más de 1 (ambigüedad real -- ej. dos capturas de la misma
        especie sin renombrar todavía en simultáneo), NO migra a
        propósito: es más seguro tratarlas por separado que
        arriesgarse a fusionar la identidad de dos Pokémon
        distintos.

        Devuelve el registro de roster ya migrado, o None si no
        aplica.
        """

        new_normalized = nickname.strip().lower()

        candidates = [
            entry
            for entry in roster
            if entry.get("speciesId") == species_id
            and entry.get("nickname") != nickname
            and self._is_placeholder_nickname(
                entry.get("nickname"),
                entry.get("species"),
            )
            and not (
                # Nunca "retroceder": si la lectura nueva es
                # literalmente "Huevo" pero la candidata YA tiene
                # un nombre por defecto post-nacimiento (no
                # "Huevo"), no son el mismo Pokémon -- es un
                # segundo huevo distinto que todavía no nació.
                new_normalized == "huevo"
                and (entry.get("nickname") or "").strip().lower()
                != "huevo"
            )
        ]

        if len(candidates) != 1:
            return None

        old_entry = candidates[0]
        old_nickname = old_entry.get("nickname")

        roster.remove(old_entry)
        del roster_by_nickname[old_nickname]

        old_entry["nickname"] = nickname
        roster.append(old_entry)
        roster_by_nickname[nickname] = old_entry

        for encounter in self._data.get("encounters", []):
            if encounter.get("nickname") == old_nickname:
                encounter["nickname"] = nickname
                encounter["updatedAt"] = _now_iso()

        for pending in self._data.get("pending_encounters", []):
            if pending.get("nickname") == old_nickname:
                pending["nickname"] = nickname

        return old_entry

    def _add_new_roster_entry(
        self,
        pokemon: dict,
        roster: list[dict],
        roster_by_nickname: dict,
    ) -> dict:
        """
        Crea el registro de roster para una captura nueva (venga
        de la party o de la Caja PC vía read_box()) y dispara
        _register_new_capture() para el tracker de rutas. Devuelve
        el registro nuevo.
        """

        nickname = pokemon.get("nickname")

        entry = {
            "nickname": nickname,
            "speciesId": pokemon.get("speciesId"),
            "species": pokemon.get("species"),
            "level": pokemon.get("level"),
            "caughtAt": _now_iso(),
            # Ícono de género en la GUI (05/09/2026, a pedido del
            # usuario) -- ver azahar_reader.py:build_pokemon_data()
            # sobre de dónde sale.
            "genderId": pokemon.get("genderId"),
        }

        roster.append(entry)
        roster_by_nickname[nickname] = entry

        self._register_new_capture(
            pokemon,
            entry["caughtAt"],
        )

        return entry

    def _retry_pending_captures(
        self,
        team: list[dict],
        boxed_party: list[dict] | None,
    ) -> bool:
        """
        Reintenta resolver la ubicación de capturas que quedaron
        en `pending_encounters` sin metLocation NI eggLocation en
        el momento exacto de la captura (28/08/2026, bug real
        reportado por el usuario: pasaba sobre todo cuando el
        jugador NO le pone nombre al Pokémon).

        `_register_new_capture()` solo se llama UNA VEZ, en el
        instante en que se detecta la captura -- si en ese
        instante el juego todavía no terminó de escribir el lugar
        de encuentro (mismo tipo de escritura progresiva que ya
        motivó varios fixes en este proyecto: el checksum PK6, el
        "Intento 3" de LAST_CAUGHT_ADDRESS, el flag salvaje de
        "perdido"), la captura quedaba pendiente PARA SIEMPRE,
        aunque el dato se terminara de escribir un par de ciclos
        después -- nada volvía a mirarlo.

        Teoría de por qué se nota más sin nombre (no confirmada al
        100%, pero consistente con el bug): con el cuadro de
        diálogo de nombre de por medio, pasa más tiempo real antes
        de que el nickname definitivo aparezca en memoria, así que
        para cuando DexRelay lo ve, el juego ya terminó de escribir
        todo. Sin el diálogo, DexRelay puede llegar a leer el
        Pokémon recién atrapado ANTES de que el juego termine de
        escribir el lugar de encuentro.

        Se ejecuta cada ciclo, con los datos frescos de
        `team`/`boxed_party` (que ya vienen con metLocation/
        eggLocation re-resueltos por LocationResolver si antes
        habían fallado -- ver el docstring de
        LocationResolver.resolve()). Para cada entrada pendiente
        sin datos: si el Pokémon sigue visible (party o caja) y
        AHORA sí trae metLocation o eggLocation, se reintenta el
        registro completo con `_register_new_capture()` (misma
        lógica de siempre: Inicial, species clause, protección de
        ruta ya tomada, intercambio, etc).

        Devuelve True si se resolvió o actualizó algo (para que
        `update()` sepa que hay que persistir).
        """

        original_pending = list(
            self._data.get("pending_encounters", [])
        )

        if not original_pending:
            return False

        current_by_nickname = {}

        for pokemon in team:
            if (
                pokemon
                and not pokemon.get("empty")
                and pokemon.get("nickname")
            ):
                current_by_nickname[pokemon["nickname"]] = (
                    pokemon
                )

        for boxed in (boxed_party or []):
            if (
                boxed
                and not boxed.get("empty")
                and boxed.get("nickname")
            ):
                current_by_nickname.setdefault(
                    boxed["nickname"],
                    boxed,
                )

        self._data["pending_encounters"] = []

        retried_any = False

        for pending in original_pending:

            current = current_by_nickname.get(
                pending.get("nickname")
            )

            had_no_data_before = not (
                pending.get("metLocation")
                or pending.get("eggLocation")
            )

            has_new_data_now = current is not None and (
                current.get("metLocation")
                or current.get("eggLocation")
            )

            if had_no_data_before and has_new_data_now:

                # _register_new_capture() decide sola qué hacer
                # con los datos frescos -- si se resuelve, queda
                # en `encounters` y no se vuelve a agregar acá; si
                # por algún motivo sigue sin poder resolverse (caso
                # raro: colisión de ubicación), se vuelve a agregar
                # a pending_encounters con los datos actualizados,
                # dentro de la misma llamada.
                self._register_new_capture(
                    current,
                    pending.get(
                        "caughtAt",
                        _now_iso(),
                    ),
                )

                retried_any = True

            else:

                self._data["pending_encounters"].append(
                    pending
                )

        return retried_any

    def update(
        self,
        team: list[dict],
        boxed_party: list[dict] | None = None,
    ) -> dict:
        """
        Compara la party actual contra el estado guardado, detecta
        capturas/evoluciones/muertes, persiste solo si hubo
        cambios, y devuelve el estado actual completo
        (roster + graveyard).

        `boxed_party`: resultado de AzaharReader.read_box() -- la
        lista completa de Pokémon actualmente en la Caja PC (fue
        ahí directo porque la party estaba llena; en ese caso nunca
        aparecen en `team`, y sin esto el Tracker nunca se enteraba
        de esas capturas). Identidad-basada, sin estado adicional
        que mantener: cualquier nickname que no esté ya en
        roster/graveyard se registra como captura nueva, igual que
        un Pokémon nuevo visto en la party.
        """

        if self._data is None:
            self._data = self.storage.load()

        roster = self._data["roster"]
        graveyard = self._data["graveyard"]

        self._data.setdefault("pending_encounters", [])
        self._data.setdefault("encounters", [])
        self._data.setdefault("starter_assigned", False)
        self._data.setdefault("traded_away", [])
        self._data.setdefault("ignored_nicknames", [])
        self._data.setdefault("fossil_pending_species_ids", [])

        # Reintento de ubicación pendiente (28/08/2026, bug real
        # reportado: pasaba sobre todo cuando el jugador NO le
        # ponía nombre al Pokémon). Ver _retry_pending_captures()
        # para el detalle completo -- se ejecuta cada ciclo, antes
        # de procesar capturas nuevas.
        if self._retry_pending_captures(team, boxed_party):
            changed_by_retry = True
        else:
            changed_by_retry = False

        roster_by_nickname = {
            entry["nickname"]: entry
            for entry in roster
        }

        graveyard_nicknames = {
            entry["nickname"]
            for entry in graveyard
        }

        # Borrado manual permanente (28/08/2026, a pedido del
        # usuario): un nickname borrado con el botón ✕ del panel
        # (delete_encounter()) nunca se vuelve a registrar solo,
        # ni ahí ni en ninguna otra ruta, aunque el Pokémon siga
        # vivo en el juego -- antes se re-creaba en el ciclo
        # siguiente porque nada bloqueaba la re-detección, lo que
        # hacía inútil el botón para corregir un error (volvía a
        # aparecer igual). Mismo criterio que graveyard_nicknames,
        # pero sin pasar por el cementerio (no murió, se ignora a
        # propósito).
        ignored_nicknames = set(
            self._data["ignored_nicknames"]
        )

        # Detección de "se fue por intercambio" (28/08/2026, a
        # pedido del usuario) -- ver el bloque de correlación al
        # final de este método para el resto de la explicación.
        # `roster_nicknames_at_start` es una foto de quién estaba
        # "vivo" ANTES de procesar este ciclo (no se recalcula
        # después, a propósito: alguien que muere este mismo ciclo
        # sigue siendo VISIBLE con hp<=0, nunca "desaparece" de la
        # lectura, así que no hay superposición posible entre
        # "murió" y "se fue por intercambio").
        roster_nicknames_at_start = set(
            roster_by_nickname.keys()
        )

        currently_visible_nicknames = set()

        for pokemon in team:
            if (
                pokemon
                and not pokemon.get("empty")
                and pokemon.get("nickname")
            ):
                currently_visible_nicknames.add(
                    pokemon["nickname"]
                )

        for boxed in (boxed_party or []):
            if (
                boxed
                and not boxed.get("empty")
                and boxed.get("nickname")
            ):
                currently_visible_nicknames.add(
                    boxed["nickname"]
                )

        vanished_candidates = []

        if self._last_visible_nicknames is not None:

            already_traded_nicknames = {
                entry["nickname"]
                for entry in self._data["traded_away"]
            }

            vanished_candidates = [
                nickname
                for nickname in (
                    self._last_visible_nicknames
                    - currently_visible_nicknames
                )
                if nickname in roster_nicknames_at_start
                and nickname not in already_traded_nicknames
            ]

        # Nicknames de capturas NUEVAS registradas este ciclo cuyo
        # metLocation es un patrón de intercambio -- se arma acá
        # (no dentro de _register_new_capture, para no tener que
        # cambiarle la firma) y se usa más abajo para correlacionar
        # con vanished_candidates.
        trade_registrations_this_cycle = []

        # Nicknames que se renombraron (no desaparecieron de
        # verdad) durante este ciclo, vía las reconciliaciones de
        # arriba -- se excluyen de vanished_candidates para no
        # confundir un renombre con un intercambio real si por
        # coincidencia pasan en el mismo ciclo (ver más abajo).
        renamed_away_nicknames = set()

        changed = changed_by_retry

        for slot_index, pokemon in enumerate(team):

            if not pokemon or pokemon.get("empty"):
                continue

            nickname = pokemon.get("nickname")

            if not nickname:
                continue

            # Todavía no nació (28/08/2026, a pedido del usuario):
            # un huevo sin eclosionar no cuenta como captura para
            # nada -- ni roster, ni encuentro/pendiente -- hasta
            # que el juego le asigne el nombre por defecto de la
            # especie al nacer. Se ignora por completo mientras
            # siga en este estado; en cuanto nazca (nickname deja
            # de ser "Huevo"), se registra recién ahí como una
            # captura nueva de la forma normal.
            if nickname.strip().lower() == "huevo":
                continue

            # Fósil restaurado (29/08/2026, confirmado en el juego
            # real reviviendo un Tirtouga): el motor lo revive
            # internamente como un huevo que "nace" al instante,
            # pero usa el placeholder EN INGLÉS ("Egg") sin
            # traducir -- distinto de "Huevo", que sí ve el
            # jugador para un huevo real del Día Cuidado. Se
            # ignora igual que un huevo sin nacer, pero además se
            # recuerda la especie en `fossil_pending_species_ids`
            # para que _register_new_capture() lo marque como
            # origin="fosil" apenas se resuelva el nombre real --
            # la ubicación que reporta el juego para esto SÍ es
            # una ruta real (ej. "Rustboro City"), a diferencia
            # del huevo/intercambio, que usan pseudo-lugares.
            #
            # Caveat conocido: si el ciclo de polling (200ms) se
            # salta por completo el instante en que el nickname es
            # literalmente "Egg" (ventana muy corta), esta captura
            # se registra como salvaje normal en vez de "fosil" --
            # no hay forma de detectarlo retroactivamente. Se
            # puede corregir a mano desde el panel si pasa.
            if nickname.strip().lower() == "egg":
                fossil_pending = self._data.setdefault(
                    "fossil_pending_species_ids", []
                )
                fossil_species_id = pokemon.get("speciesId")
                if fossil_species_id not in fossil_pending:
                    fossil_pending.append(fossil_species_id)
                continue

            # Ya está en el cementerio: la muerte es permanente,
            # no reaparece en el roster aunque el HP actual sea > 0.
            if nickname in graveyard_nicknames:
                continue

            # Se borró a mano con el botón ✕ (28/08/2026): se
            # ignora para siempre, no se re-registra solo aunque
            # el Pokémon siga vivo en el juego.
            if nickname in ignored_nicknames:
                continue

            species_id = pokemon.get("speciesId")
            species = pokemon.get("species")
            level = pokemon.get("level")
            hp = pokemon.get("hp")

            entry = roster_by_nickname.get(nickname)

            if entry is None:

                nicknames_before_reconcile = set(
                    roster_by_nickname.keys()
                )

                entry = self._reconcile_starter_rename(
                    nickname,
                    species_id,
                    roster,
                    roster_by_nickname,
                )

                if entry is not None:
                    changed = True

                    # Se renombró, no "desapareció" -- no cuenta
                    # como candidato a intercambio (ver la
                    # correlación al final de update()).
                    renamed_away_nicknames.update(
                        nicknames_before_reconcile
                        - set(roster_by_nickname.keys())
                    )

            if entry is None:

                # Caso general (28/08/2026): Pokémon nacido de un
                # huevo (o cualquier otro con nickname todavía sin
                # personalizar) renombrado -- ver
                # _reconcile_pending_rename().
                nicknames_before_reconcile = set(
                    roster_by_nickname.keys()
                )

                entry = self._reconcile_pending_rename(
                    nickname,
                    species_id,
                    roster,
                    roster_by_nickname,
                )

                if entry is not None:
                    changed = True

                    renamed_away_nicknames.update(
                        nicknames_before_reconcile
                        - set(roster_by_nickname.keys())
                    )

            if entry is None:

                # Captura nueva vista en la party -- se registra
                # directo acá, sin espera (26-27/08/2026: vuelve a
                # este comportamiento, el mismo del Bloque A
                # original).
                #
                # Nota histórica: entre el 26/08 y el 27/08 esto
                # estuvo restringido solo al Inicial, delegando
                # TODA otra captura -- de party o de Caja PC por
                # igual -- a un único camino de memoria
                # (TOTAL_CAUGHT_ADDRESS + LAST_CAUGHT_ADDRESS en
                # Runtime), para que ambos destinos compartieran la
                # misma lógica de espera de nickname/ruta. Se
                # revierte esa unificación acá: el problema de
                # nombre/ruta a medio escribir resultó ser
                # específico de la Caja PC (ver
                # AzaharReader.read_box() y el bloque de
                # `boxed_party` más abajo) -- el camino directo de
                # party nunca mostró ese bug en el Bloque A
                # original, y forzarlo a esperar igual solo sumaba
                # una dependencia innecesaria de una dirección de
                # memoria (el buffer reciclado) que además resultó
                # ser poco confiable para el propósito real que
                # motivó investigarla. El checksum de
                # structures.py ya garantiza que una lectura válida
                # de un slot de party es un snapshot completo, así
                # que no hace falta ninguna espera adicional acá.
                #
                # _register_new_capture() decide sola si esta
                # captura es el Inicial (primera de la partida) o
                # una normal, con su lógica de siempre (species
                # clause, protección de ruta ya tomada, etc).
                entry = self._add_new_roster_entry(
                    pokemon,
                    roster,
                    roster_by_nickname,
                )

                if self._is_trade_location(
                    pokemon.get("metLocation")
                ):
                    trade_registrations_this_cycle.append(
                        nickname
                    )

                changed = True

            elif (
                entry.get("speciesId") != species_id
                or entry.get("level") != level
            ):

                species_changed = (
                    entry.get("speciesId") != species_id
                )

                # Evolución y/o subida de nivel: actualiza el
                # mismo registro, no crea uno nuevo.
                entry["speciesId"] = species_id
                entry["species"] = species
                entry["level"] = level

                if species_changed:

                    # Sincronización con el panel de encuentros
                    # (28/08/2026, a pedido del usuario): si el
                    # Pokémon evolucionó (no solo subió de nivel),
                    # el encuentro de esa ruta (por nickname)
                    # actualiza el nombre de especie también --
                    # antes quedaba fijado para siempre con la
                    # especie de la captura original. El panel
                    # resuelve el sprite en el frontend a partir de
                    # este mismo nombre (species_list ->
                    # speciesId -> sprite), así que alcanza con
                    # actualizar el texto acá. Mismo criterio que
                    # la sincronización de "muerto" de abajo: no
                    # hace falta que el usuario lo actualice a
                    # mano.
                    for encounter in self._data["encounters"]:

                        if encounter.get("nickname") == nickname:
                            encounter["species"] = species
                            encounter["updatedAt"] = _now_iso()

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
                    # Ícono de género en la GUI (05/09/2026).
                    "genderId": entry.get("genderId"),
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

        # Capturas nuevas detectadas directo en la Caja PC
        # (26-27/08/2026, ver AzaharReader.read_box() y Documento
        # Maestro sección 14 "Detección de capturas en la Caja
        # PC"). Reemplaza al viejo camino de TOTAL_CAUGHT_ADDRESS +
        # LAST_CAUGHT_ADDRESS (un buffer reciclado de "último
        # Pokémon salvaje enfrentado", con datos que tardaban en
        # terminar de escribirse y que además no lograba resolver
        # bien el lugar de encuentro específicamente para
        # capturas de caja).
        #
        # La Caja PC real es almacenamiento persistente, no un
        # buffer de scratch -- cada slot ocupado es una captura
        # real y completa, así que se registra igual que un
        # Pokémon nuevo de la party: sin espera. Si en pruebas
        # reales resulta que el juego escribe el slot de forma
        # progresiva (nombre por defecto primero, nickname real
        # después, igual que hacía el buffer viejo), esto va a
        # registrar el nombre por defecto -- pendiente de
        # confirmar en el juego (decisión explícita: probar sin
        # colchón de estabilidad primero, agregar uno después solo
        # si hace falta).
        #
        # Misma identidad por nickname que el resto del sistema:
        # si ya está en roster/graveyard (porque ya se había
        # registrado antes, en un ciclo anterior), no se hace nada
        # -- no hace falta ningún estado adicional para evitar
        # duplicados.
        for boxed_pokemon in (boxed_party or []):

            if not boxed_pokemon or boxed_pokemon.get("empty"):
                continue

            boxed_nickname = boxed_pokemon.get("nickname")

            if not boxed_nickname:
                continue

            # Mismo criterio que el loop de party (28/08/2026): un
            # huevo sin nacer no cuenta como captura todavía, ni
            # siquiera si está guardado en la Caja PC (un huevo
            # nunca eclosiona estando en la caja -- solo avanza
            # caminando en la party -- pero igual puede quedar ahí
            # guardado indefinidamente sin nacer, y no debe
            # aparecer como capturado mientras tanto).
            if boxed_nickname.strip().lower() == "huevo":
                continue

            # Fósil restaurado guardado directo en la Caja PC
            # (party llena) -- mismo criterio que el loop de party
            # de arriba, ver ese comentario para el detalle
            # completo.
            if boxed_nickname.strip().lower() == "egg":
                fossil_pending = self._data.setdefault(
                    "fossil_pending_species_ids", []
                )
                fossil_species_id = boxed_pokemon.get(
                    "speciesId"
                )
                if fossil_species_id not in fossil_pending:
                    fossil_pending.append(fossil_species_id)
                continue

            if (
                boxed_nickname in roster_by_nickname
                or boxed_nickname in graveyard_nicknames
                or boxed_nickname in ignored_nicknames
            ):
                continue

            self._add_new_roster_entry(
                boxed_pokemon,
                roster,
                roster_by_nickname,
            )

            if self._is_trade_location(
                boxed_pokemon.get("metLocation")
            ):
                trade_registrations_this_cycle.append(
                    boxed_nickname
                )

            changed = True

        # Correlación "se fue por intercambio" (28/08/2026, a
        # pedido del usuario): un trueque es 1-para-1 y
        # transaccional -- el mismo ciclo en que aparece un
        # Pokémon nuevo con metLocation de intercambio, el que
        # diste vos desaparece de la party/caja para siempre (no
        # hay ningún "murió" para eso, DexRelay solo deja de verlo
        # en la memoria del juego). Se aprovecha esa simultaneidad
        # como señal: si en este ciclo se registró EXACTAMENTE una
        # captura nueva por intercambio, y EXACTAMENTE un Pokémon
        # que antes se veía dejó de verse (party+caja) sin haber
        # muerto, se asume que ese es el que se fue -- move a
        # `traded_away`, no se pisa el roster/graveyard.
        #
        # Si hay ambigüedad (0 o más de 1 de cualquiera de los dos
        # lados) NO se adivina -- se prefiere no marcar nada antes
        # que marcar mal a un Pokémon que en realidad no se fue por
        # trueque (ej. se liberó, o el usuario cerró la app justo
        # en el medio de una lectura).
        if (
            len(trade_registrations_this_cycle) == 1
            and len(
                [
                    n for n in vanished_candidates
                    if n not in renamed_away_nicknames
                ]
            )
            == 1
        ):

            traded_nickname = next(
                n for n in vanished_candidates
                if n not in renamed_away_nicknames
            )
            traded_entry = roster_by_nickname.get(
                traded_nickname
            )

            if traded_entry is not None:

                roster.remove(traded_entry)
                del roster_by_nickname[traded_nickname]

                self._data["traded_away"].append({
                    "nickname": traded_nickname,
                    "speciesId": traded_entry.get(
                        "speciesId"
                    ),
                    "species": traded_entry.get("species"),
                    "level": traded_entry.get("level"),
                    "receivedNickname": (
                        trade_registrations_this_cycle[0]
                    ),
                    "tradedAt": _now_iso(),
                })

                # Sincronización con el panel (28/08/2026, a
                # pedido del usuario): el encuentro original de
                # este Pokémon (la ruta donde se lo capturó, si la
                # tiene) queda marcado con `tradedAway: true` sin
                # tocar su status/ubicación -- el panel usa este
                # flag para tacharlo y ponerlo en gris, sin perder
                # el registro de dónde se lo había atrapado. Mismo
                # patrón que la sincronización de "muerto".
                for encounter in self._data["encounters"]:

                    if encounter.get("nickname") == traded_nickname:
                        encounter["tradedAway"] = True
                        encounter["updatedAt"] = _now_iso()

                changed = True

        self._last_visible_nicknames = currently_visible_nicknames

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

        Orden de decisión:

        1. Si es el PRIMER Pokémon que se obtiene en toda la
           partida (nunca se asignó un inicial antes), se
           registra como "Inicial" sin importar lo que diga
           metLocation -- el juego suele reportar el regalo del
           inicial con un lugar de encuentro especial/vacío, no
           una ruta real, y aunque reportara algo, la regla acá
           es "el primero que se obtiene es el inicial", punto.

        2. Si `eggLocation` viene resuelto (28/08/2026,
           "Entregado por" -- SOLO existe si este Pokémon fue
           huevo alguna vez, nunca en una captura salvaje normal)
           tiene PRIORIDAD sobre metLocation: una vez que un huevo
           nace, el juego le asigna una ruta real (la de eclosión)
           en metLocation, pero para el tracker eso no cuenta como
           una captura salvaje normal -- se registra como
           "especial"/"huevo", usando el texto de "Entregado por"
           como pseudo-ubicación (bare primero; con el nickname
           agregado si ya estaba tomada por otro huevo del mismo
           origen).

        3. Si no es un huevo y `metLocation` reporta un intercambio
           (28/08/2026, "a Link Trade..." -- ver
           _is_trade_location()), se registra como "especial"/
           "intercambiado" con un pseudo-lugar fijo en español en
           vez de mostrar el texto en inglés (bare primero; con el
           nickname agregado si ya estaba tomada).

        4. Si no es huevo ni intercambio y ya trae `metLocation`
           resuelto (vía PKHeX), se intenta registrar directo en
           `encounters` -- PERO solo si esa ubicación todavía no
           tiene un encuentro registrado. Si ya hay uno (por
           ejemplo, una segunda captura que por lo que sea quedó
           marcada con el mismo lugar), NO se pisa el registro
           existente -- cae a pending_encounters para que el
           usuario decida a mano, en vez de perder en silencio el
           primer encuentro real de esa ruta.

        5. Si no hay ni eggLocation, ni intercambio, ni metLocation
           disponibles (regalo, o el bridge falló), cae a
           pending_encounters como siempre.

        Fósil restaurado (29/08/2026): no es un paso más en este
        orden -- se resuelve ANTES, marcando status/origin como
        "especial"/"fosil" si esta especie pasó por el placeholder
        "Egg" (ver el loop de party/caja). A partir de ahí sigue el
        camino normal del punto 4 (metLocation SÍ viene resuelto
        con una ruta real, ej. "Rustboro City" -- no hace falta
        ningún pseudo-lugar como huevo/intercambio).
        """

        nickname = pokemon.get("nickname")
        species_id = pokemon.get("speciesId")
        species = pokemon.get("species")
        met_location = pokemon.get("metLocation")
        met_location_id = pokemon.get("metLocationId", 0)
        egg_location = pokemon.get("eggLocation")
        is_shiny = bool(pokemon.get("shiny"))

        # Fósil restaurado (29/08/2026): si esta especie pasó por
        # el placeholder "Egg" (ver el loop de party/caja más
        # arriba), se consume acá la marca. Se saca de la lista
        # YA -- si más abajo termina cayendo a pending_encounters
        # sin poder registrarse todavía (metLocation no resuelto
        # aún), se vuelve a agregar al final de esta función para
        # que el reintento (_retry_pending_captures) lo siga
        # tratando como fósil la próxima vez.
        fossil_pending = self._data.setdefault(
            "fossil_pending_species_ids", []
        )
        was_fossil = species_id in fossil_pending
        if was_fossil:
            fossil_pending.remove(species_id)

        # Señal de respaldo (29/08/2026, bug real reportado: la
        # ventana de "Egg" se saltó por completo -- se registró
        # como captura salvaje normal): sin importar si se cazó
        # "Egg" o no, si el lugar de encuentro resuelto es Devon
        # Corp (ver DEVON_CORP_LOCATION_ID), es un fósil sí o sí --
        # ahí no hay pasto salvaje. Las dos señales son
        # independientes, cualquiera de las dos alcanza.
        is_fossil = was_fossil or (
            met_location_id == DEVON_CORP_LOCATION_ID
        )

        # "shiny"/"fosil" ya no son un status suelto (27-29/08/2026)
        # -- son un origen dentro del status unificado "especial"
        # (ver VALID_ORIGINS). Esto aplica tanto acá, cuando se
        # detecta shiny/fósil automático con una ruta real ya
        # resuelta, como en el flujo manual de "¿Pokémon Especial?"
        # del panel para huevo/regalo/intercambio/evento (ver
        # assign_special_origin() más abajo). Prioridad de origen
        # (29/08/2026, a pedido del usuario -- invertida respecto
        # al criterio anterior): huevo/fósil/intercambio ganan por
        # sobre shiny -- shiny queda como ÚLTIMA prioridad, solo se
        # usa cuando ninguno de los otros tres aplica. Un fósil
        # shiny se registra como origin="fosil" (no "shiny"); mismo
        # criterio para huevo e intercambio, ver más abajo.
        status = (
            "especial" if (is_shiny or is_fossil) else "capturado"
        )
        origin = (
            "fosil" if is_fossil
            else "shiny" if is_shiny
            else None
        )

        if not self._data.get("starter_assigned"):

            self._data["starter_assigned"] = True

            self.save_encounter(
                "Inicial",
                nickname,
                species,
                status,
                origin=origin,
                shiny=is_shiny,
            )

            return

        # Regla de especie repetida (species clause): si YA hay
        # otro Pokémon de la misma especie vivo en el equipo, esta
        # captura no cuenta como un encuentro nuevo -- ni se
        # registra en `encounters` ni queda pendiente. Sigue
        # existiendo en `roster` con normalidad (el Bloque A no
        # cambia: si muere, se sigue detectando igual), solo no se
        # cuenta para el tracker de rutas. Si el primero de esa
        # especie ya está en el cementerio, esta SÍ cuenta normal.
        species_already_alive = any(
            entry.get("speciesId") == species_id
            and entry.get("nickname") != nickname
            for entry in self._data.get("roster", [])
        )

        if species_already_alive:
            return

        if egg_location:

            # "Entregado por" (28/08/2026, a pedido del usuario):
            # eggLocation SOLO viene resuelto si este Pokémon fue
            # huevo alguna vez -- nunca en una captura salvaje
            # normal. Tiene prioridad sobre metLocation a
            # propósito: una vez que el huevo nace, el juego le
            # asigna una ruta real (la de eclosión) a metLocation,
            # pero eso no debe tratarse como una captura salvaje
            # ahí -- se usa "Entregado por" como pseudo-ubicación
            # para no tener que asignarlo a mano en el panel cada
            # vez.
            #
            # Se prueba el texto tal cual primero (preferencia
            # explícita del usuario: no agregarle nada si no hace
            # falta). Si esa "ruta" ya está tomada -- otro huevo
            # entregado por la misma persona/lugar -- recién ahí
            # se le agrega el nickname para diferenciarlo, mismo
            # patrón que "Especial (Nickname)" del flujo manual de
            # asignación.
            pseudo_location = egg_location

            location_taken = any(
                entry["location"] == pseudo_location
                for entry in self._data["encounters"]
            )

            if location_taken:

                pseudo_location = (
                    f"{egg_location} ({nickname})"
                )

                location_taken = any(
                    entry["location"] == pseudo_location
                    for entry in self._data["encounters"]
                )

            if not location_taken:

                self.save_encounter(
                    pseudo_location,
                    nickname,
                    species,
                    "especial",
                    # Huevo le gana a shiny (29/08/2026, prioridad
                    # invertida -- ver comentario más arriba).
                    origin="huevo",
                    shiny=is_shiny,
                )

                return

            # Ni el texto tal cual ni el sufijado con nickname
            # sirvieron (caso extremo, prácticamente imposible con
            # nicknames -- son únicos por diseño). Cae al flujo
            # pendiente de abajo, igual que cualquier otro caso sin
            # resolver.

        elif met_location and self._is_trade_location(met_location):

            # Intercambio (28/08/2026, a pedido del usuario): el
            # juego reporta el lugar de encuentro de un Pokémon
            # recibido por trueque como texto libre en inglés (ver
            # _is_trade_location) -- no hay ninguna ruta real
            # asociada, así que se usa un pseudo-lugar fijo en
            # español en vez de mostrar ese texto. Mismo patrón
            # bare-primero-nickname-después que "Entregado por".
            # Intercambio le gana a shiny (29/08/2026, prioridad
            # invertida -- ver comentario en el bloque de arriba).
            trade_origin = "intercambio"

            pseudo_location = "Intercambiado"

            location_taken = any(
                entry["location"] == pseudo_location
                for entry in self._data["encounters"]
            )

            if location_taken:

                pseudo_location = f"Intercambiado ({nickname})"

                location_taken = any(
                    entry["location"] == pseudo_location
                    for entry in self._data["encounters"]
                )

            if not location_taken:

                self.save_encounter(
                    pseudo_location,
                    nickname,
                    species,
                    "especial",
                    origin=trade_origin,
                    shiny=is_shiny,
                )

                return

            # Ídem: cae al flujo pendiente de abajo si ni el bare
            # ni el sufijado sirvieron.

        elif is_fossil and met_location:

            # Fósil (29/08/2026, a pedido del usuario): la
            # ubicación real que reporta el juego (Devon Corp /
            # "Ciudad Férrica") es SIEMPRE la misma para
            # cualquier fósil que se revive en la partida --a
            # diferencia de una colisión real entre dos capturas
            # salvajes DISTINTAS que por coincidencia caen en la
            # misma ruta (eso sí necesita revisión manual vía
            # "¿Pokémon Especial?"), acá la colisión es esperable
            # y rutinaria (vas a revivir más de un fósil). Mismo
            # patrón bare-primero-nickname-después que huevo/
            # intercambio, para que TODOS los fósiles se registren
            # directo en la tabla sin pasar por pendientes.
            pseudo_location = met_location

            location_taken = any(
                entry["location"] == pseudo_location
                for entry in self._data["encounters"]
            )

            if location_taken:

                pseudo_location = f"{met_location} ({nickname})"

                location_taken = any(
                    entry["location"] == pseudo_location
                    for entry in self._data["encounters"]
                )

            if not location_taken:

                self.save_encounter(
                    pseudo_location,
                    nickname,
                    species,
                    "especial",
                    origin="fosil",
                    shiny=is_shiny,
                )

                return

            # Ídem: cae al flujo pendiente de abajo si ni el bare
            # ni el sufijado sirvieron.

        elif met_location:

            location_taken = any(
                entry["location"] == met_location
                for entry in self._data["encounters"]
            )

            if not location_taken:

                self.save_encounter(
                    met_location,
                    nickname,
                    species,
                    status,
                    origin=origin,
                    shiny=is_shiny,
                )

                return

            # Ya hay un encuentro registrado en esa ubicación --
            # no se pisa. Cae al flujo pendiente de abajo para que
            # el usuario lo revise a mano.

        # No se pudo registrar todavía (metLocation/eggLocation sin
        # resolver, o ubicación ya tomada) -- si era un fósil, se
        # vuelve a marcar la especie como pendiente para que la
        # próxima vez (retry o una nueva captura vista) lo siga
        # tratando como fósil en vez de perder la señal.
        if was_fossil and species_id not in fossil_pending:
            fossil_pending.append(species_id)

        self._data["pending_encounters"].append({
            "nickname": nickname,
            "speciesId": species_id,
            "species": species,
            "shiny": is_shiny,
            "metLocation": met_location,
            "eggLocation": egg_location,
            "caughtAt": caught_at,
            # Ícono de género en la GUI (05/09/2026).
            "genderId": pokemon.get("genderId"),
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
        "especial",
    )

    # Origenes válidos para el estado "especial" (27/08/2026,
    # reemplaza a los viejos estados sueltos "regalo",
    # "intercambiado" y "shiny" -- ahora son un único status
    # ("especial") con el origen guardado en un campo aparte
    # ("origin" en el encuentro), para que el panel pueda mostrar
    # "Especial/Shiny", "Especial/Huevo", etc. sin necesitar 5
    # estados distintos coloreados por separado).
    VALID_ORIGINS = (
        "shiny",
        "huevo",
        "intercambio",
        "evento",
        "regalo",
        "fosil",
    )

    def has_encounter_for_location(self, location: str) -> bool:
        """
        True si ya existe cualquier encuentro registrado para esa
        ubicación, sin importar su estado (capturado/perdido/
        especial/etc).

        Usado por la detección automática del estado "perdido"
        (ver Runtime._update_lost_encounter_tracking()) para NO
        tomar un snapshot al empezar un combate salvaje si esa
        ruta ya tiene un resultado -- evita pisar un encuentro real
        con un "perdido" viejo si, por ejemplo, el jugador vuelve a
        pelear en una ruta ya completada.
        """

        return any(
            entry["location"] == location
            for entry in self.get_encounters()
        )

    def register_lost_encounter(
        self,
        location: str,
        species: str,
    ) -> list[dict]:
        """
        Registra una ruta como "perdido": el primer combate
        salvaje ahí terminó sin captura (huida o derrota -- no se
        distingue a propósito, ver
        DexRelay_Contexto_Deteccion_Perdido.md).

        El nickname usa el nombre de la especie rival como
        placeholder (decisión del usuario, 27/08/2026) -- no hay
        ningún Pokémon capturado del que sacar un nickname real.

        No pisa un encuentro ya existente en esa ubicación (mismo
        criterio de protección que _register_new_capture()) --
        Runtime ya evita tomar el snapshot en ese caso, pero se
        revalida acá también por si el encuentro se registró por
        otro camino mientras el combate estaba en curso.
        """

        if self.has_encounter_for_location(location):
            return self.get_encounters()

        return self.save_encounter(
            location,
            species,
            species,
            "perdido",
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

    def discard_pending_encounter(
        self,
        nickname: str,
    ) -> list[dict]:
        """
        Botón "Descartar" del panel: saca una captura de
        `pending_encounters` sin registrarla en `encounters`. El
        Pokémon sigue en `roster` con normalidad (sigue siendo
        parte del equipo real) -- esto solo significa "no quiero
        que esta captura cuente para el tracker de rutas".

        Devuelve la lista de pendientes actualizada. Lanza
        ValueError si no había ninguna captura pendiente con ese
        nickname.
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

        self.storage.save(self._data)

        return pending

    def delete_encounter(self, location: str) -> list[dict]:
        """
        Botón de reseteo de una ruta (panel): elimina el registro
        de encuentro de esa ubicación Y el Pokémon capturado ahí
        -- lo saca de `roster`/`graveyard` también, no solo de
        `encounters`. Pensado para deshacer una captura mal
        registrada (ej. una fila duplicada por el bug de idioma),
        no para el uso normal del juego.

        "Inicial" es la única excepción: nunca se puede resetear,
        ni siquiera si ese Pokémon murió después -- el inicial de
        la partida es permanente por definición, no depende de que
        siga vivo.

        BUG REAL corregido (28/08/2026): borrar acá no alcanzaba
        para "deshacer" nada -- si el Pokémon seguía vivo en el
        juego, el ciclo siguiente lo volvía a ver en la party/caja
        y lo re-registraba solo, idéntico a como estaba. Ahora el
        nickname se agrega a `ignored_nicknames` (decisión
        explícita del usuario: para siempre, no hay forma de
        "deshacer el borrado" todavía) -- update() lo salta por
        completo de ahí en más, sin importar que el Pokémon siga
        vivo.

        Devuelve la lista de encuentros actualizada. Lanza
        ValueError si no había ningún encuentro en esa ubicación,
        o si se intenta resetear "Inicial".
        """

        if location == "Inicial":
            raise ValueError(
                "El Inicial no se puede resetear -- es "
                "permanente por definición, incluso si ese "
                "Pokémon murió después."
            )

        if self._data is None:
            self._data = self.storage.load()

        self._data.setdefault("ignored_nicknames", [])

        encounters = self.get_encounters()

        match = next(
            (
                entry
                for entry in encounters
                if entry["location"] == location
            ),
            None,
        )

        if match is None:
            raise ValueError(
                f"No hay ningún encuentro registrado en "
                f"{location!r}."
            )

        encounters.remove(match)

        nickname = match.get("nickname")

        if nickname:

            self._data["roster"] = [
                entry
                for entry in self._data.get("roster", [])
                if entry.get("nickname") != nickname
            ]

            self._data["graveyard"] = [
                entry
                for entry in self._data.get(
                    "graveyard", []
                )
                if entry.get("nickname") != nickname
            ]

            if nickname not in self._data["ignored_nicknames"]:
                self._data["ignored_nicknames"].append(
                    nickname
                )

        self.storage.save(self._data)

        return encounters

    def assign_encounter_location(
        self,
        nickname: str,
        location: str,
    ) -> dict:
        """
        Asigna una ubicación LIBRE a una captura pendiente: la
        saca de `pending_encounters` y la registra en
        `encounters` bajo la ruta que se le pase. Devuelve
        {'encounters': [...], 'pending_encounters': [...]}
        actualizados.

        NOTA (27/08/2026): el panel ya no usa este método -- el
        flujo de "Capturas sin ruta asignada" pasó a ser
        "¿Pokémon Especial?" (ver assign_special_origin() más
        abajo), que no le pide al jugador elegir una ruta sino un
        origen, y genera la pseudo-ubicación sola. Se deja este
        método funcionando por si hace falta reactivar un flujo de
        asignación de ruta libre a futuro.
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
            "especial"
            if match.get("shiny")
            else "capturado"
        )

        origin = (
            "shiny"
            if match.get("shiny")
            else None
        )

        encounters = self.save_encounter(
            location,
            match["nickname"],
            match["species"],
            status,
            origin=origin,
        )

        return {
            "encounters": encounters,
            "pending_encounters": pending,
        }

    def assign_special_origin(
        self,
        nickname: str,
        origin: str,
    ) -> dict:
        """
        Registra una captura pendiente como "Especial" (27/08/2026,
        corregido el mismo día tras una aclaración del usuario --
        ver Documento Maestro).

        La ubicación final depende de si PKHeX pudo resolver un
        lugar de encuentro real para esta captura (`metLocation`
        en el registro pendiente -- lo mismo que el panel muestra
        como "Ruta real detectada"):

        - CON ruta real conocida: se usa esa ruta -- es la razón
          de ser de "¿Pokémon Especial?" para este caso (shiny/
          etc. encontrado en una ruta que ya tenía otro encuentro
          registrado, la colisión que lo mandó a pendientes en
          primer lugar). Como esa ruta casi siempre YA está
          tomada (si no lo estuviera, no habría caído a
          pendientes), NO se pisa el registro existente -- se
          guarda como "{ruta} (Especial)" en su lugar, vía
          `_resolve_special_location()`. Duplicar la fila de la
          ruta en sí (dos filas con el mismo texto de ubicación)
          NO es viable sin rediseñar cómo se identifica cada fila
          en todo el proyecto (tabla, backend, botón de reseteo)
          -- `location` es la clave única de cada encuentro en
          todos lados.
        - SIN ruta real (huevo/regalo/intercambio/evento, o el
          bridge falló): no hay ninguna ruta que preservar, se
          usa la pseudo-ubicación única de siempre:
          "Especial ({nickname})".

        Saca la captura de `pending_encounters` y la registra en
        `encounters` con status="especial" y el origen elegido
        guardado aparte. Devuelve
        {'encounters': [...], 'pending_encounters': [...]}
        actualizados.

        `origin="captura_extra"` (29/08/2026, a pedido del
        usuario) es un caso especial DENTRO de este método pero
        NO usa status="especial" -- se delega a
        `_assign_extra_capture()`, ver su docstring.
        """

        if origin == "captura_extra":
            return self._assign_extra_capture(nickname)

        if origin not in self.VALID_ORIGINS:
            raise ValueError(
                f"Origen invalido: {origin!r}. "
                f"Debe ser uno de {self.VALID_ORIGINS}."
            )

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

        met_location = match.get("metLocation")

        if met_location:

            location = self._resolve_special_location(
                met_location,
                match["nickname"],
            )

            anchor_location = met_location

        else:

            location = f"Especial ({match['nickname']})"
            anchor_location = None

        encounters = self.save_encounter(
            location,
            match["nickname"],
            match["species"],
            "especial",
            origin=origin,
            anchor_location=anchor_location,
            shiny=bool(match.get("shiny", False)),
        )

        return {
            "encounters": encounters,
            "pending_encounters": pending,
        }

    def _assign_extra_capture(self, nickname: str) -> dict:
        """
        "Captura Extra" (29/08/2026, a pedido del usuario): una
        opción más de la tarjeta "¿Pokémon Especial?", pero a
        propósito NO usa status="especial" -- se registra como
        "capturado" normal (es un dato histórico real: ahí se lo
        atrapó), solo con un flag de presentación (`extraCapture`)
        para que el panel muestre "Captura Extra" en el <select>
        en vez de "Capturado" para esta fila puntual. Mismo patrón
        que `tradedAway`/"Intercambiado" (sección 14 del Documento
        Maestro).

        La UBICACIÓN mostrada es la ruta real donde se lo capturó
        (`metLocation`), NO un texto sintético "Captura Extra"
        (corregido 29/08/2026 -- versión anterior usaba
        "Captura Extra (nickname)" como pseudo-ubicación siempre,
        a pedido del usuario ahora se prioriza la ruta real). Como
        esta captura cayó a pendientes casi siempre por colisión
        de ruta (ya había otro encuentro ahí), se prueba la ruta
        real tal cual primero y, si ya está tomada, se le agrega
        el nickname para diferenciarla sin pisar el registro
        existente -- mismo patrón bare-primero-nickname-después
        que huevo/intercambio/fósil. Sin ruta real conocida
        (regalo sin ubicación, bridge caído), se usa el pseudo-
        lugar de siempre como último recurso.
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

        met_location = match.get("metLocation")

        if met_location:

            location = met_location

            location_taken = any(
                entry["location"] == location
                for entry in self.get_encounters()
            )

            if location_taken:
                location = f"{met_location} ({match['nickname']})"

        else:

            location = f"Captura Extra ({match['nickname']})"

        encounters = self.save_encounter(
            location,
            match["nickname"],
            match["species"],
            "capturado",
            # anchor_location (30/08/2026, bug real corregido): la
            # fila caia siempre al final de la tabla porque esto
            # nunca se pasaba -- el panel necesita la ruta real
            # (sin el sufijo con nickname) para poder ubicarla
            # debajo de su ruta, igual que ya hace "especial".
            anchor_location=met_location,
            shiny=bool(match.get("shiny", False)),
            extra_capture=True,
        )

        return {
            "encounters": encounters,
            "pending_encounters": pending,
        }

    def _resolve_special_location(
        self,
        met_location: str,
        nickname: str,
    ) -> str:
        """
        Encuentra dónde guardar una captura especial que SÍ tiene
        una ruta real conocida.

        Lo normal es que `met_location` ya esté tomada (por eso
        la captura cayó a pendientes en primer lugar) -- en ese
        caso se le agrega el sufijo "(Especial)" para conservar la
        ruta real visible sin pisar el registro existente. Si por
        algún motivo la ruta NO está tomada (caso raro), se usa
        directo, sin sufijo. Y si hasta la variante con sufijo ya
        está ocupada (más de una captura especial distinta en la
        misma ruta -- todavía más raro), se suma el nickname para
        garantizar unicidad.
        """

        encounters = self.get_encounters()

        taken_locations = {
            entry["location"]
            for entry in encounters
        }

        if met_location not in taken_locations:
            return met_location

        with_suffix = f"{met_location} (Especial)"

        if with_suffix not in taken_locations:
            return with_suffix

        return f"{with_suffix} - {nickname}"

    def save_encounter(
        self,
        location: str,
        nickname: str,
        species: str,
        status: str,
        origin: str | None = None,
        anchor_location: str | None = None,
        shiny: bool | None = None,
        extra_capture: bool | None = None,
    ) -> list[dict]:
        """
        Crea o actualiza el registro de encuentro de una
        ubicación. Devuelve la lista completa de encuentros
        ya actualizada.

        `origin` solo tiene sentido junto con status="especial"
        (shiny/huevo/intercambio/evento/regalo/fosil, ver
        VALID_ORIGINS) -- para cualquier otro status se fuerza a
        None, así no queda un dato viejo pegado si un encuentro
        pasa de "especial" a otro estado más adelante.

        `anchor_location` (27/08/2026): SOLO para encuentros
        "especial" con ruta real conocida pero ya tomada -- es la
        ruta real (sin el sufijo "(Especial)"), para que el panel
        pueda ubicar la fila justo debajo de esa ruta sin tener
        que parsear el texto de `location`. None para especiales
        sin ruta real conocida (huevo/regalo/intercambio/evento) o
        para cualquier encuentro que no sea "especial". Mismo
        criterio de conservación que `origin`: si no viaja uno
        nuevo pero el registro ya tenía uno, se mantiene.

        `shiny` (29/08/2026, a pedido del usuario): DESACOPLADO de
        `origin` -- desde que se invirtió la prioridad (huevo/
        fósil/intercambio le ganan a shiny para decidir `origin`),
        un Pokémon shiny con otro origen ya no queda marcado como
        tal en ningún lado si solo se guarda `origin`. Se guarda
        aparte, en CUALQUIER status (no solo "especial"), para que
        el ícono ✨ del panel se pueda mostrar sin importar qué
        origen ganó. Mismo criterio de conservación que `origin`:
        si no viaja un valor nuevo (None) pero el registro ya
        tenía uno, se mantiene -- así una edición de nickname/
        especie sin tocar shiny no lo borra.

        `extra_capture` (29/08/2026, a pedido del usuario):
        "Captura Extra" -- opción de la tarjeta "¿Pokémon
        Especial?" que NO usa status="especial" (queda como
        "capturado", un dato histórico normal), solo cambia el
        TEXTO que el panel muestra en el <select> para esta fila
        puntual. Mismo patrón que `tradedAway`/"Intercambiado":
        un flag de presentación independiente del status real.
        Mismo criterio de conservación que `shiny`.
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

        if shiny is None:
            shiny = (
                bool(existing.get("shiny", False))
                if existing is not None
                else False
            )
        else:
            shiny = bool(shiny)

        if extra_capture is None:
            extra_capture = (
                bool(existing.get("extraCapture", False))
                if existing is not None
                else False
            )
        else:
            extra_capture = bool(extra_capture)

        if status == "especial":

            if origin is None and existing is not None:

                # Edición directa desde la tabla principal (nickname
                # o especie) sobre una fila que YA era "especial" --
                # no manda origen porque el select de estado no
                # tiene forma de elegirlo inline (eso vive en la
                # tarjeta de "¿Pokémon Especial?"). Se conserva el
                # que ya tenía en vez de exigir que se vuelva a
                # elegir.
                origin = existing.get("origin")

            if origin not in self.VALID_ORIGINS:
                raise ValueError(
                    f"Origen invalido para status='especial': "
                    f"{origin!r}. Debe ser uno de "
                    f"{self.VALID_ORIGINS}."
                )

            if anchor_location is None and existing is not None:
                anchor_location = existing.get("anchorLocation")

        elif extra_capture:

            # Captura Extra (30/08/2026, bug real corregido): aunque
            # el status es "capturado" (no "especial"), esta fila
            # igual necesita poder llevar anchor_location para que
            # el panel la posicione debajo de su ruta real, en vez
            # de caer siempre al final de la tabla (ver docstring
            # de _assign_extra_capture()). origin sigue sin
            # aplicar aca -- es exclusivo de status="especial".
            origin = None

            if anchor_location is None and existing is not None:
                anchor_location = existing.get("anchorLocation")

        else:

            origin = None
            anchor_location = None

        if existing is None:

            encounters.append({
                "location": location,
                "nickname": nickname,
                "species": species,
                "status": status,
                "origin": origin,
                "anchorLocation": anchor_location,
                "shiny": shiny,
                "extraCapture": extra_capture,
                "updatedAt": _now_iso(),
            })

        else:

            existing["nickname"] = nickname
            existing["species"] = species
            existing["status"] = status
            existing["origin"] = origin
            existing["anchorLocation"] = anchor_location
            existing["shiny"] = shiny
            existing["extraCapture"] = extra_capture
            existing["updatedAt"] = _now_iso()

        self.storage.save(self._data)

        return encounters

    # =====================================
    # REGLAS DEL RUN (RULESET)
    #
    # Lista editable de reglas de la casa (dupes clause, muerte
    # permanente, etc. -- ver DEFAULT_RULESET en
    # nuzlocke_storage.py), GUI v2 página Nuzlocke (04/09/2026).
    # Persiste junto al resto del run, pero conceptualmente es
    # independiente de roster/graveyard/encounters -- no se borra
    # con reset_all() (ver su docstring).
    # =====================================

    def get_ruleset(self) -> list[dict]:
        """
        Devuelve la lista actual de reglas
        ({id, label, enabled}). Si el archivo es de antes de que
        existiera esto, NuzlockeStorage.load() ya la completa con
        DEFAULT_RULESET -- acá no hace falta un default aparte.
        """

        if self._data is None:
            self._data = self.storage.load()

        self._data.setdefault("ruleset", [])

        return self._data["ruleset"]

    def save_ruleset(self, ruleset: list[dict]) -> list[dict]:
        """
        Reemplaza la lista completa de reglas -- la GUI manda
        siempre la lista entera (agregar/quitar/tildar todo se
        resuelve del lado del frontend sobre una copia, y esto solo
        persiste el resultado final), más simple que tener un
        método aparte por cada tipo de edición.

        Validación mínima: cada regla necesita "id" y "label" no
        vacíos -- "enabled" se normaliza a bool, con default
        `True` si no viene (una regla recién agregada por el
        usuario nace activa).
        """

        cleaned: list[dict] = []
        seen_ids: set[str] = set()

        for rule in ruleset:
            rule_id = str(rule.get("id") or "").strip()
            label = str(rule.get("label") or "").strip()

            if not rule_id or not label:
                raise ValueError(
                    "Cada regla necesita 'id' y 'label'."
                )

            if rule_id in seen_ids:
                raise ValueError(
                    f"Id de regla duplicado: {rule_id!r}."
                )

            seen_ids.add(rule_id)

            cleaned.append({
                "id": rule_id,
                "label": label,
                "enabled": bool(rule.get("enabled", True)),
            })

        if self._data is None:
            self._data = self.storage.load()

        self._data["ruleset"] = cleaned

        self.storage.save(self._data)

        return cleaned
