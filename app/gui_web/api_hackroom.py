"""
Soporte del hack Rising Ruby / Sinking Sapphire (Fase E): catálogos de cambios
cargados al arrancar y helpers que aplican los overrides del hackroom. Los comparten
los mixins de Pokémon y de Líderes.

Bloque 9.4 (01/10/2026, guía siguiente versión): extraído de `app/gui_web/api.py`
(que llegó a 2588 líneas) sin cambiar ninguna lógica -- los métodos son los mismos, solo
viven en un módulo por dominio. `Api` (api.py) los combina por herencia múltiple, así que
para pywebview/JS sigue siendo UNA sola clase con los mismos métodos públicos.
"""

from __future__ import annotations

import json

from app.core import paths


# Fase E (09/09/2026, hackroom) -- methodKey de PKHeX que
# representan intercambio (mismos 3 valores reales usados por
# evolution_translations.py: METHOD_KEYS_ES/orden de prioridad). Se
# usan en _species_details_with_hackroom_overrides() para sacar el
# método de intercambio original cuando el hackroom agrega una
# alternativa -- a pedido del usuario, el intercambio deja de
# mostrarse del todo en ese caso, no queda como opción en paralelo.
TRADE_METHOD_KEYS = {
    "Trade",
    "TradeHeldItem",
    "TradeShelmetKarrablast",
}


class HackroomMixin:
    """Mixin de `Api` (ver el docstring del módulo)."""

    def _hackroom_available(self):
        """
        Bloque 13: el hackroom (Rising Ruby / Sinking Sapphire) solo
        existe sobre ORAS. Con un juego conectado cuyo perfil no lo
        declara, queda apagado aunque el interruptor esté activo.
        Sin juego detectado todavía se mantiene lo de siempre.
        """

        reader = getattr(self.app, "reader", None)
        profile = getattr(reader, "profile", None)

        return profile is None or profile.capabilities.has_hackroom

    def _hackroom_enabled(self):
        """Interruptor de Configuración Y disponible en este juego."""

        return bool(
            self._hackroom_available()
            and self.app.config.get("hackroom", "enabled", default=False)
        )

    def _load_hackroom_attack_changes(self):

        changes_path = paths.path("data", "attack_changes_rrss.json")

        if not changes_path.exists():
            return {}

        try:
            with open(changes_path, "r", encoding="utf-8") as file:
                raw = json.load(file)
        except Exception:
            return {}

        return {int(move_id): entry for move_id, entry in raw.items()}

    def _load_hackroom_pokemon_changes(self):

        changes_path = paths.path("data", "pokemon_changes_rrss.json")

        if not changes_path.exists():
            return {}

        try:
            with open(changes_path, "r", encoding="utf-8") as file:
                raw = json.load(file)
        except Exception:
            return {}

        return {int(species_id): entry for species_id, entry in raw.items()}

    def _load_hackroom_evolution_overrides(self):

        overrides_path = paths.path(
            "data", "evolution_changes_rrss.json"
        )

        if not overrides_path.exists():
            return {}

        try:
            with open(overrides_path, "r", encoding="utf-8") as file:
                raw = json.load(file)
        except Exception:
            return {}

        by_species = {}

        for override in raw.get("overrides", []):
            from_id = override.get("fromSpeciesId")
            by_species.setdefault(from_id, []).append(override)

        return by_species

    def _species_details_with_hackroom_overrides(self, species_id):
        """
        Reemplazo directo de self.modal_bridge.species_details(id)
        -- misma firma, mismo formato de respuesta -- que además
        aplica los overrides de evolución Y de tipo/habilidad/stats
        del hackroom (ver arriba) cuando config.json ->
        hackroom.enabled está prendido. Si está apagado, o la
        especie no tiene NINGÚN override de ningún tipo, el
        resultado es idéntico al del bridge sin tocar.

        BUG REAL corregido (09/09/2026, reportado por el usuario:
        Luxray no mostraba su tipo Dark nuevo): un `return`
        temprano acá abajo cortaba la función completa si la
        especie no tenía overrides de EVOLUCIÓN -- Luxray no
        evoluciona por intercambio, así que nunca tiene overrides
        de esa lista, y el bloque de tipo/habilidad/stats (que
        vive más abajo) nunca llegaba a ejecutarse. Afectaba a
        CASI TODAS las 306 especies con cambios de tipo/habilidad/
        stats (solo las pocas que además evolucionan por
        intercambio se salvaban de este bug). Los dos bloques de
        overrides son independientes -- ahora los dos se evalúan
        siempre, tengan o no overrides de evolución.
        """

        details = self.modal_bridge.species_details(species_id)

        if "error" in details:
            return details

        if not self._hackroom_enabled():
            return details

        overrides = self._hackroom_evolution_overrides_by_species.get(
            species_id
        )

        evolutions = list(details.get("evolutions", []))

        for override in overrides or []:

            to_id = override["toSpeciesId"]
            new_entry = {
                "toSpeciesId": to_id,
                "toSpeciesName": override["toSpecies"],
                "methodKey": override["methodKey"],
                "level": override["level"],
                "argument": override["argument"],
            }

            if override["mode"] == "replace":
                evolutions = [
                    entry for entry in evolutions
                    if entry.get("toSpeciesId") != to_id
                ]

            elif override["mode"] == "add":
                # CORRECCIÓN (09/09/2026, a pedido del usuario: "el
                # método de evolución por intercambios no debería
                # mostrarse porque no son necesarias" -- con el
                # hackroom activo, los métodos nuevos (amistad/
                # nivel/objeto/compañero) hacen innecesario el
                # intercambio original, así que se saca en vez de
                # mostrarse en paralelo). Se filtra específicamente
                # el/los métodos de intercambio (Trade/
                # TradeHeldItem/TradeShelmetKarrablast) hacia ESE
                # mismo destino -- no cualquier "Trade" de la
                # especie, por si en algún caso hubiera más de un
                # destino real (no pasa en las 24 especies de este
                # hackroom, pero es más correcto filtrar por
                # destino que por especie entera).
                evolutions = [
                    entry for entry in evolutions
                    if not (
                        entry.get("toSpeciesId") == to_id
                        and entry.get("methodKey") in TRADE_METHOD_KEYS
                    )
                ]

            evolutions.append(new_entry)

        details = {
            **details,
            "evolutions": evolutions,
        }

        # Overrides de tipo/habilidad/stats base (09/09/2026, Fase
        # E, segunda parte, a pedido del usuario: "sigamos con
        # tipos habilidades y stats"). Se aplican DESPUÉS de armar
        # `details` con las evoluciones ya resueltas -- son
        # independientes entre sí, no hay orden que importe acá.
        pokemon_changes = self._hackroom_pokemon_changes_by_species.get(
            species_id
        )

        if pokemon_changes:

            if "type1" in pokemon_changes:
                details["type1Key"] = pokemon_changes["type1"]
                details["type2Key"] = pokemon_changes.get("type2") or ""

            if "ability1" in pokemon_changes:
                ability_id, ability_name = self._resolve_hackroom_ability(
                    pokemon_changes["ability1"]
                )
                details["ability1Id"] = ability_id
                details["ability1Name"] = ability_name

            if "ability2" in pokemon_changes:
                ability_id, ability_name = self._resolve_hackroom_ability(
                    pokemon_changes["ability2"]
                )
                details["ability2Id"] = ability_id
                details["ability2Name"] = ability_name

            if "baseStats" in pokemon_changes:
                details["baseStats"] = {
                    **details.get("baseStats", {}),
                    **pokemon_changes["baseStats"],
                }

        return details

    def _hackroom_base_stats_override(self, species_id):
        """
        {"hp"?, "attack"?, ...} para pasarle a
        PokemonDetailResolver.resolve() (ver su docstring y la de
        bridge.pokemon_details()) -- None si el hackroom está
        apagado o esta especie no tiene cambio de stats.
        """

        if not self._hackroom_enabled():
            return None

        pokemon_changes = self._hackroom_pokemon_changes_by_species.get(
            species_id
        )

        if not pokemon_changes:
            return None

        return pokemon_changes.get("baseStats")

    # Offset de AbilityNumber en la estructura PK6 descifrada (byte
    # 0x15, justo después del id de habilidad en 0x14): bit 0 =
    # habilidad 1, bit 1 = habilidad 2, bit 2 = oculta -- mismo
    # significado que pk.AbilityNumber de PKHeX.
    _PK6_ABILITY_NUMBER_OFFSET = 0x15

    @classmethod
    def _live_ability_slot_key(cls, raw_data):
        """
        Qué slot de habilidad lleva puesto el Pokémon vivo, como la
        clave de pokemon_changes_rrss.json que le corresponde
        ("ability1" / "ability2"), o None si no se puede saber con
        certeza o es la oculta (el hackroom no cambia esa).

        Bug real (03/10/2026, reportado por el usuario): los
        iniciales (Mudkip/Torchic/Treecko) mostraban siempre la
        habilidad oculta aunque en el juego tenían la normal --
        el override de habilidad se aplicaba SIEMPRE que la
        especie tuviera un cambio en un solo slot, sin mirar si el
        Pokémon realmente llevaba ese slot.
        """

        try:
            ability_number = raw_data[cls._PK6_ABILITY_NUMBER_OFFSET]
        except (TypeError, IndexError):
            return None

        if ability_number == 1:
            return "ability1"

        if ability_number == 2:
            return "ability2"

        return None

    def _apply_hackroom_pokemon_changes_to_live_detail(
        self, species_id, details, raw_data=None
    ):
        """
        Mismo propósito que los overrides de species_details()
        (_species_details_with_hackroom_overrides()), pero para el
        detalle de un Pokémon VIVO (PokemonDetailResolver, ver su
        docstring) -- CORRECCIÓN REAL (09/09/2026, reportado por el
        usuario: revisó Luxray de la lista de cambios de tipo y no
        se había actualizado). Causa real: HandlePokemonDetails()
        en Program.cs resuelve type1Key/type2Key/abilidad desde SU
        PROPIA PersonalTable, en un lugar del bridge completamente
        distinto de species_details() (HandleSpeciesDetails) -- son
        dos handlers separados, arreglar uno no arregla el otro.

        Tipo/habilidad de la ESPECIE, y tipo de cada MOVIMIENTO --
        las stats CALCULADAS (attack/defense/etc, que dependen de
        IVs/EVs/naturaleza/nivel además de la stat base) se
        resuelven aparte, pasándole `base_stats_override` directo a
        PokemonDetailResolver.resolve() (ver
        _hackroom_base_stats_override() y bridge.pokemon_details())
        ANTES de que el bridge calcule -- más confiable que
        intentar reescribir un número ya calculado acá sin rehacer
        la fórmula completa del juego.
        """

        if details is None:
            return details

        if not self._hackroom_enabled():
            return details

        pokemon_changes = self._hackroom_pokemon_changes_by_species.get(
            species_id
        )

        if pokemon_changes:

            if "type1" in pokemon_changes:
                details["type1Key"] = pokemon_changes["type1"]
                details["type2Key"] = pokemon_changes.get("type2") or ""

            # El Pokémon vivo solo tiene UN slot de habilidad activo
            # (el que realmente lleva puesto, no los 3 posibles como
            # en species_details()) -- hay que saber CUÁL de los dos
            # (ability1/ability2) es el que overridear. Se compara
            # contra el nombre en inglés que ya resolvió el bridge
            # (details["abilityName"] está en español, así que se
            # compara por id vía AbilityCatalog en vez de por
            # texto).
            # Solo se overridea el slot que el Pokémon REALMENTE lleva
            # (AbilityNumber del PK6, ver _live_ability_slot_key()).
            # Antes (hasta 03/10/2026) se pisaba la habilidad con el
            # único slot que cambiara la especie sin verificar nada,
            # así que un Pokémon con la habilidad 1 mostraba la
            # nueva habilidad 2 (o la oculta, en iniciales). Si no
            # se puede determinar el slot, o lleva la oculta, se
            # deja la habilidad real que reportó el bridge.
            live_slot_key = self._live_ability_slot_key(raw_data)

            if live_slot_key and live_slot_key in pokemon_changes:
                new_id, new_name = self._resolve_hackroom_ability(
                    pokemon_changes[live_slot_key]
                )

                details["abilityId"] = new_id
                details["abilityName"] = new_name

        # CORRECCIÓN (09/09/2026, reportado por el usuario: "el
        # Corte aparece con el ícono de tipo Normal en la vista sin
        # abrir el modal, en el modal sí sale bien de tipo Planta")
        # -- BUG REAL idéntico al que ya se corrigió arriba en
        # _species_details_with_hackroom_overrides(): este override
        # de movimientos NO puede vivir adentro del `if
        # pokemon_changes:` de arriba, porque el tipo de un
        # MOVIMIENTO es independiente de si la ESPECIE del Pokémon
        # tiene algún cambio -- cualquier Pokémon que sepa Corte
        # necesita este override, tenga o no su especie algo en
        # pokemon_changes_rrss.json.
        moves = details.get("moves")

        if moves:
            for move in moves:
                move_changes = self._hackroom_attack_changes_by_move.get(
                    move.get("id")
                )

                if move_changes and "typeKey" in move_changes:
                    move["typeKey"] = move_changes["typeKey"]

        return details

    def _resolve_hackroom_ability(self, ability_name_en):
        """
        "Limber" -> (id_real, "Limber" en español) usando los
        mismos catálogos ya construidos para las habilidades de
        líderes de gimnasio (self.gym_leader_catalog, ver
        gym_leaders.py) -- comparten el mismo bridge/caché, no hace
        falta duplicar la lógica. Si no se puede resolver, devuelve
        (None, ability_name_en) tal cual -- nunca inventa.
        """

        ability_id = (
            self.gym_leader_catalog
            ._ability_description_catalog
            .get_id_by_name(ability_name_en)
        )

        if ability_id is None:
            return None, ability_name_en

        ability_name_es = (
            self.gym_leader_catalog._ability_catalog.get_name(ability_id)
            or ability_name_en
        )

        return ability_id, ability_name_es

    def _active_gym_leader_catalog(self):
        """
        Decide en el momento (leyendo config.json cada vez, no una
        sola vez al arrancar) si usar el catálogo vanilla o el del
        hackroom -- ver la corrección del 09/09/2026 junto a
        self.gym_leader_catalog en __init__ (el toggle de
        Configuración ahora surte efecto sin reiniciar DexRelay).
        """

        if self._hackroom_enabled():
            return self.gym_leader_catalog_hackroom

        return self.gym_leader_catalog

    def _apply_hackroom_move_type(self, move_name, type_key):
        """Override de tipo del hackroom sobre un tipo ya conocido."""

        if not self._hackroom_enabled():
            return type_key

        move_id = self.move_description_catalog.get_id_by_name(
            move_name
        )

        move_changes = self._hackroom_attack_changes_by_move.get(
            move_id
        )

        if move_changes and "typeKey" in move_changes:
            return move_changes["typeKey"]

        return type_key
