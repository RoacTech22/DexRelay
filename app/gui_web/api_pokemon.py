"""
Página Pokémon: equipo, cajas, modales de movimiento/habilidad/especie y árbol evolutivo.

Bloque 9.4 (01/10/2026, guía siguiente versión): extraído de `app/gui_web/api.py`
(que llegó a 2588 líneas) sin cambiar ninguna lógica -- los métodos son los mismos, solo
viven en un módulo por dominio. `Api` (api.py) los combina por herencia múltiple, así que
para pywebview/JS sigue siendo UNA sola clase con los mismos métodos públicos.
"""

from __future__ import annotations

from app.memory.pointers import BOX_COUNT, BOX_SLOT_COUNT
from app.services.evolution_translations import (
    EVOLUTION_METHOD_COMPACT_LABELS,
    METHOD_KEYS_USING_ITEM_ARGUMENT,
    METHOD_KEYS_USING_MOVE_ARGUMENT,
    METHOD_KEYS_USING_TEAMMATE_ARGUMENT,
    describe_evolution,
)
from app.services.move_data import merge_move_details
from app.services.type_effectiveness import (
    categorize_effectiveness,
    compute_effectiveness,
)


class PokemonMixin:
    """Mixin de `Api` (ver el docstring del módulo)."""

    # -----------------------------------------------------------
    # Shell principal -- se completa en los próximos bloques
    # (Pokémon, Medallas, Nuzlocke, Overlays, Configuración,
    # Logs)
    # -----------------------------------------------------------

    def get_pokemon_page_data(self):
        """
        Página Pokémon (GUI v2, Bloque 3) -- a pedido del usuario,
        reemplaza la vista de lista simple del mockup por el
        detalle completo (boceto: sprite, sexo, especie, tipos,
        habilidad, stats con indicador de naturaleza,
        movimientos) directo en cada una de las 6 tarjetas, sin
        vista aparte.

        Combina, por slot:
        - Identidad básica (nickname/especie/nivel/HP/shiny) --
          `state.team`, la misma lectura que ya usa el Dashboard,
          sin memoria nueva.
        - Detalle vía PKHeX (tipos/habilidad/naturaleza/stats/
          movimientos) -- bajo demanda, releyendo memoria fresca
          para cada slot (ver
          AzaharReader.read_pokemon_raw_for_slot()) y resolviendo
          con PokemonDetailResolver (sin caché, ver su docstring).

        Un slot vacío devuelve solo `{"slot": n, "empty": True}` --
        el detalle ni se pide.

        Bug real (03/09/2026, confirmado con logs reales del
        usuario): con Azahar/el juego cerrado, esto seguía
        intentando releer memoria por cada uno de los 6 slots en
        CADA poll de 2s de la página (ver POKEMON_POLL_MS en
        app.js) -- inofensivo (ya no rompe nada gracias a los
        fixes anteriores en read_pokemon_raw_for_slot()), pero
        inundaba la consola con la misma línea de error una y otra
        vez mientras el juego siguiera cerrado, y golpeaba un
        socket que se sabe de antemano que va a fallar. Se chequea
        `state.azahar_connected` (ya lo mantiene al día
        Runtime.update() en cada ciclo, no hace falta otra
        consulta) ANTES de intentar leer -- sin conexión, se
        devuelve la identidad básica que ya se tenía (o "vacío" si
        ni eso), sin tocar el socket para nada.
        """

        team = self.app.state.team or []
        connected = self.app.state.azahar_connected
        pages = []

        for slot in range(1, 7):
            basic = next(
                (
                    entry
                    for entry in team
                    if entry.get("slot") == slot
                ),
                None,
            )

            if not basic or basic.get("empty"):
                pages.append({"slot": slot, "empty": True})
                continue

            if not connected:
                entry = dict(basic)
                entry["details"] = None
                pages.append(entry)
                continue

            pokemon = self.app.reader.read_pokemon_raw_for_slot(
                slot
            )

            if pokemon is None:
                # La party dice que hay algo acá pero la lectura
                # bajo demanda falló de forma transitoria -- se
                # muestra la identidad básica igual (ya la
                # tenemos de `state.team`) sin detalle, en vez de
                # ocultar la tarjeta entera.
                print(
                    f"[Api] get_pokemon_page_data: lectura fallida "
                    f"para el slot {slot} (READ_FAILED o vacío "
                    f"inesperado)."
                )
                entry = dict(basic)
                entry["details"] = None
                pages.append(entry)
                continue

            details = self.pokemon_detail_resolver.resolve(
                pokemon.raw_data[:232],
                base_stats_override=self._hackroom_base_stats_override(
                    basic.get("speciesId")
                ),
            )

            details = self._apply_hackroom_pokemon_changes_to_live_detail(
                basic.get("speciesId"),
                details,
                raw_data=pokemon.raw_data[:232],
            )

            entry = dict(basic)
            entry["details"] = details
            pages.append(entry)

        return pages

    def get_boxes_overview(self):
        """
        Pestaña "General" de la página Pokémon (roadmap 08/09/2026,
        sección 5.1/5.2) -- equipo actual + las Cajas PC (BOX_COUNT,
        7 -- ver pointers.py), ambos con detalle MÍNIMO
        (sprite/nombre/nivel, sin golpear el bridge PKHeX) -- a
        diferencia de get_box_page_data() de más abajo, que sí
        resuelve detalle completo pero solo para UNA caja puntual
        (la que el usuario abre en la pestaña "Caja").

        Una sola lectura UDP para las BOX_COUNT cajas
        (AzaharReader.read_boxes_range(), ya usada para el matching
        del Nuzlocke Tracker) en vez de BOX_COUNT lecturas sueltas
        -- se pide bajo demanda, solo mientras la pestaña "General"
        está abierta (ver dexrelay:tabchange en app.js), no en el
        poll de fondo del Dashboard.

        DECISIÓN DE ALCANCE (09/09/2026, a pedido del usuario):
        BOX_COUNT quedó fijo en 7 (las cajas de fábrica), no en las
        31 que soporta el juego como máximo teórico -- un Nuzlocke
        real nunca necesita comprar más, las capturas están
        limitadas. Esto es exactamente la misma lectura que ya usa
        el Nuzlocke Tracker en producción desde antes (mismo
        BOX_COUNT, mismo read_boxes_range()), así que no hay
        incertidumbre de tamaño/latencia nueva acá -- ya está
        probado en vivo.

        Devuelve {"connected": bool, "team": [...] (mismo formato
        que ya usa el Dashboard), "boxes": [{"boxIndex", "pokemon":
        [...]}, ...]} -- una entrada por caja, 1 a BOX_COUNT, en
        orden, incluso las vacías (con "pokemon": []).
        """

        connected = self.app.state.azahar_connected
        team = self.app.state.team or []

        if not connected:
            return {
                "connected": False,
                "team": team,
                "boxes": [
                    {"boxIndex": box_index, "pokemon": []}
                    for box_index in range(1, BOX_COUNT + 1)
                ],
            }

        occupied = self.app.reader.read_boxes_range(
            1, BOX_COUNT
        )

        by_box_index = {}

        for entry in occupied:
            by_box_index.setdefault(
                entry.get("boxIndex"), []
            ).append({
                "slot": entry.get("slot"),
                "speciesId": entry.get("speciesId"),
                "species": entry.get("species"),
                "nickname": entry.get("nickname"),
                "level": entry.get("level"),
                "shiny": entry.get("shiny"),
                "isEgg": entry.get("isEgg"),
            })

        boxes = [
            {
                "boxIndex": box_index,
                "pokemon": by_box_index.get(box_index, []),
            }
            for box_index in range(1, BOX_COUNT + 1)
        ]

        return {
            "connected": True,
            "team": team,
            "boxes": boxes,
        }

    def get_box_page_data(self, box_index):
        """
        Pestaña "Caja" de la página Pokémon (roadmap 08/09/2026,
        sección 5.1/5.3) -- detalle COMPLETO (tipos/habilidad/
        naturaleza/stats/movimientos, vía PKHeX) para los Pokémon
        de UNA caja puntual, mismo criterio exacto que
        get_pokemon_page_data() ya usa para el equipo: identidad
        básica primero (read_box(), sin bridge), detalle vía
        PokemonDetailResolver bajo demanda después, solo para los
        slots ocupados.

        A diferencia de la party (siempre 6 slots fijos), acá se
        arma la lista completa de BOX_SLOT_COUNT (30) slots,
        marcando "empty": True los que no tengan Pokémon -- así el
        frontend puede mostrar la grilla completa de la caja igual
        que ya hace con los 6 slots del equipo.

        `box_index` es 1-based (Caja 1 = 1). Fuera de rango
        (1..BOX_COUNT) devuelve {"error": "..."} sin tocar memoria.
        """

        if not (1 <= box_index <= BOX_COUNT):
            return {"error": f"box_index fuera de rango: {box_index}"}

        connected = self.app.state.azahar_connected

        slots = [
            {"slot": slot, "boxIndex": box_index, "empty": True}
            for slot in range(1, BOX_SLOT_COUNT + 1)
        ]

        if not connected:
            return {
                "boxIndex": box_index,
                "boxCount": BOX_COUNT,
                "connected": False,
                "slots": slots,
            }

        occupied_by_slot = {
            entry["slot"]: entry
            for entry in self.app.reader.read_box(box_index)
        }

        for index, slot_number in enumerate(
            range(1, BOX_SLOT_COUNT + 1)
        ):

            basic = occupied_by_slot.get(slot_number)

            if not basic:
                continue

            raw_data = self.app.reader.read_box_slot_raw(
                box_index, slot_number
            )

            details = (
                self.pokemon_detail_resolver.resolve(
                    raw_data,
                    base_stats_override=self._hackroom_base_stats_override(
                        basic.get("speciesId")
                    ),
                )
                if raw_data is not None
                else None
            )

            details = self._apply_hackroom_pokemon_changes_to_live_detail(
                basic.get("speciesId"), details, raw_data=raw_data
            )

            entry = dict(basic)
            entry["details"] = details
            slots[index] = entry

        return {
            "boxIndex": box_index,
            "boxCount": BOX_COUNT,
            "connected": True,
            "slots": slots,
        }

    def get_move_modal_data(self, move_id):
        """
        Modal de movimiento (GUI v2, roadmap 07/09/2026, sección
        4.1) -- junta las 3 fuentes ya confirmadas en una sola
        respuesta: nombre/tipo/PP (bridge PKHeX,
        PKHeXBridge.move_details()), potencia/precisión/categoría
        (dataset estático, MoveDataCatalog/merge_move_details(), ya
        curado y verificado contra ORAS) y descripción en español
        (dataset estático, MoveDescriptionCatalog, ya curado desde
        move_flavor_text.csv).

        No necesita memoria del juego -- move_id ya lo tiene el
        frontend (viene en `details.moves[].id`, ver
        PokemonDetailResolver/HandlePokemonDetails() en Program.cs),
        así que esto se puede pedir independiente del ciclo de
        polling normal, solo cuando el usuario hace click en una
        fila de movimiento.

        Devuelve el dict combinado tal cual, o
        {"error": "..."} si el bridge falló -- el frontend decide
        cómo mostrar ese caso (no se inventa un valor de respaldo
        acá).
        """

        try:
            bridge_response = self.modal_bridge.move_details(
                move_id
            )
        except Exception as error:
            return {"error": str(error)}

        merged = merge_move_details(
            bridge_response, self.move_data_catalog
        )

        if "error" in merged:
            return merged

        description = self.move_description_catalog.get(move_id)

        merged["descriptionEs"] = description["descriptionEs"]
        merged["descriptionSource"] = description["source"]

        # Fase E (09/09/2026, hackroom -- AttackChanges.txt) -- el
        # bridge/dataset estático dan los valores del juego BASE,
        # sin saber que el ROM está parcheado. Mismo criterio que
        # los demás overrides de esta fase: solo se aplica con
        # hackroom.enabled prendido, y solo si este movimiento
        # puntual tiene algo documentado.
        if self.app.config.get("hackroom", "enabled", default=False):

            move_changes = self._hackroom_attack_changes_by_move.get(
                move_id
            )

            if move_changes:
                if "typeKey" in move_changes:
                    merged["typeKey"] = move_changes["typeKey"]
                if "power" in move_changes:
                    merged["power"] = move_changes["power"]
                if "accuracy" in move_changes:
                    merged["accuracy"] = move_changes["accuracy"]
                if "pp" in move_changes:
                    merged["basePP"] = move_changes["pp"]

        return merged

    def get_ability_modal_data(self, ability_id):
        """
        Modal de habilidad (GUI v2, roadmap 07/09/2026, sección
        4.1) -- a diferencia del de movimiento, no hace falta
        golpear el bridge de nuevo acá: el nombre de la habilidad
        ya lo tiene el frontend (viene en `details.abilityName`,
        resuelto por PokemonDetailResolver cuando se cargó la
        tarjeta), así que esto solo agrega la descripción en
        español (dataset estático, AbilityDescriptionCatalog).
        """

        description = self.ability_description_catalog.get(
            ability_id
        )

        return {
            "id": ability_id,
            "descriptionEs": description["descriptionEs"],
            "descriptionSource": description["source"],
        }

    def get_move_modal_data_by_name(self, name):
        """
        Mismo resultado que get_move_modal_data(), pero para
        lugares de la app que solo tienen el NOMBRE en inglés del
        movimiento, sin id -- hoy, la ventana de detalle de equipo
        de líder de gimnasio (leader_team_window.js), cuyos datos
        salen de data/gym_leaders.json (curado a mano, sin ids).

        Resuelve el id vía
        MoveDescriptionCatalog.get_id_by_name() y delega en
        get_move_modal_data() -- un solo lugar con la lógica real,
        no reimplementada aparte.
        """

        move_id = self.move_description_catalog.get_id_by_name(name)

        if move_id is None:
            return {
                "error": f"Movimiento no encontrado: {name!r}"
            }

        return self.get_move_modal_data(move_id)

    def get_ability_modal_data_by_name(self, name):
        """
        Mismo criterio que get_move_modal_data_by_name(), para
        habilidades.
        """

        ability_id = self.ability_description_catalog.get_id_by_name(
            name
        )

        if ability_id is None:
            return {
                "id": None,
                "descriptionEs": None,
                "descriptionSource": None,
            }

        return self.get_ability_modal_data(ability_id)

    def _resolve_evolution_transition(self, evolution):
        """
        Junta toda la info de CÓMO se da una evolución puntual
        (nivel/objeto/movimiento/compañero + descripción) a partir
        de un dict crudo {methodKey, level, argument} tal como lo
        devuelve species_details() del bridge. Reusado tanto por la
        lista plana de evoluciones como por _build_evolution_chain()
        (roadmap 4.2, 07/09/2026).
        """

        method_key = evolution.get("methodKey")
        level = evolution.get("level")
        argument = evolution.get("argument")

        item_id = None
        item_name = None

        if method_key in METHOD_KEYS_USING_ITEM_ARGUMENT:
            item_id = argument
            item_name = self.item_catalog.get_name(argument)

        move_name = None

        if method_key in METHOD_KEYS_USING_MOVE_ARGUMENT:
            try:
                move_result = self.modal_bridge.move_details(argument)
                if "error" not in move_result:
                    move_name = move_result.get("name")
            except Exception:
                move_name = None

        teammate_name = None

        if method_key in METHOD_KEYS_USING_TEAMMATE_ARGUMENT:
            teammate_name = self.species_catalog.get_name(argument)

        return {
            "level": level,
            "itemId": item_id,
            "itemName": item_name,
            "moveName": move_name,
            "teammateName": teammate_name,
            # Bug real corregido (08/09/2026, reportado por el
            # usuario: "Azurill evoluciona a Marill por amistad no
            # está saliendo eso") -- para los métodos sin nivel real
            # ni objeto/movimiento/compañero (amistad, intercambio
            # simple, belleza, etc. -- `level` viene en 0, que
            # JavaScript trata como "falso"), el frontend necesita
            # ALGO más que mostrar en el conector visual entre
            # etapas -- ver EVOLUTION_METHOD_COMPACT_LABELS.
            "conditionLabel": EVOLUTION_METHOD_COMPACT_LABELS.get(
                method_key
            ),
            "description": describe_evolution(
                method_key,
                level,
                argument,
                item_name=item_name,
                move_name=move_name,
                teammate_name=teammate_name,
            ),
        }

    def _build_forward_evolution_node(
        self, stage_id, stage_details, depth_remaining, seen_ids, current_species_id
    ):
        """
        Nodo de la cadena hacia adelante, con TODAS las ramas (no
        solo la primera) -- corrige el bug real reportado por el
        usuario el 08/09/2026: "Wurmple tiene dos ramas evolutivas
        (Silcoon/Cascoon -> Beautifly/Dustox) y la app solo
        mostraba una". Recursivo: cada nodo puede tener 0, 1 o
        varios hijos (uno por evolución posible), cada uno con su
        propia transición. `depth_remaining` limita cuántos saltos
        hacia adelante se siguen desde la especie actual (2, mismo
        tope que antes tenía el camino único) -- se aplica por
        rama, no en total, así que Wurmple (especie actual) -> 2
        ramas -> cada una 1 salto más alcanza sin problema dentro
        del límite de 2.
        """

        node = {
            "speciesId": stage_id,
            "name": stage_details.get("name") or f"#{stage_id}",
            "isCurrent": stage_id == current_species_id,
            "children": [],
        }

        if depth_remaining <= 0:
            return node

        # BUG REAL corregido (09/09/2026, reportado por el usuario
        # jugando el hackroom: "las evoluciones que se hacen por
        # intercambios no se han modificado al nuevo método").
        # Causa real: cuando una especie tiene VARIOS métodos
        # alternativos hacia el MISMO destino (ej. Kadabra ahora
        # evoluciona a Alakazam por Trade, por amistad, O al nivel
        # 36 -- ver evolution_changes_rrss.json, "in addition to
        # the trading way" en el documento del hack), el chequeo de
        # `next_id in seen_ids` de acá abajo descartaba TODAS las
        # transiciones menos la primera, porque las tres apuntan al
        # mismo `toSpeciesId` -- `seen_ids` fue pensado para evitar
        # ciclos/loops en el árbol, no para des-duplicar métodos
        # alternativos legítimos hacia un mismo destino. Se agrupan
        # ahora por toSpeciesId ANTES de chequear seen_ids, así el
        # nodo hijo se construye una sola vez pero con TODAS las
        # transiciones que lleven ahí.
        evolutions_by_target = {}

        for evolution in stage_details.get("evolutions", []):
            next_id = evolution.get("toSpeciesId")

            if not next_id:
                continue

            evolutions_by_target.setdefault(next_id, []).append(evolution)

        for next_id, evolutions in evolutions_by_target.items():

            if next_id in seen_ids:
                continue

            seen_ids.add(next_id)

            try:
                next_details = self._species_details_with_hackroom_overrides(next_id)
            except Exception:
                next_details = {}

            child_node = self._build_forward_evolution_node(
                next_id,
                next_details,
                depth_remaining - 1,
                seen_ids,
                current_species_id,
            )

            node["children"].append({
                "transitions": [
                    self._resolve_evolution_transition(evolution)
                    for evolution in evolutions
                ],
                "node": child_node,
            })

        return node

    def _build_evolution_chain(self, species_id, original_details):
        """
        Cadena de evolución COMPLETA (07/09/2026, a pedido del
        usuario: "haz que en la evolución siempre salgan las tres
        etapas" -- antes solo se mostraba lo que species_details()
        de la especie actual traía directo: hacia adelante siempre,
        hacia atrás nunca, así que una especie de 3ra etapa
        mostraba solo 2 eslabones en vez de los 3).

        Actualizado 08/09/2026 para mostrar TODAS las ramas hacia
        adelante, no solo la primera (bug real: Wurmple solo
        mostraba Silcoon->Beautifly, nunca Cascoon->Dustox -- puede
        haber otros casos de ramificación en ORAS con el mismo
        problema, ej. Gloom->Vileplume/Bellossom, Poliwhirl->
        Poliwrath/Politoed, Slowpoke->Slowbro/Slowking, Snorunt->
        Glalie/Froslass, Kirlia->Gallade, más las 8 ramas de Eevee).

        Arma la cadena así:
        1. Sube por PreEvolutionCatalog desde `species_id` hasta la
           raíz (especie que no evoluciona de ninguna otra) -- esta
           parte SIGUE siendo un camino único hacia atrás (un
           Pokémon evoluciona siempre desde una sola pre-evolución
           en los juegos principales, no hay ramificación posible
           yendo hacia atrás).
        2. Desde `species_id`, arma un ÁRBOL con TODAS las
           evoluciones posibles, hasta 2 saltos más hacia adelante
           por rama.

        Devuelve {"ancestors": [{"speciesId","name",
        "transitionsToNext"}, ...], "current": <nodo del árbol
        hacia adelante, ver _build_forward_evolution_node()>}.
        """

        # 1. Ancestros (de la raíz hacia `species_id`, sin incluirlo)
        ancestor_ids = []
        walker_id = species_id
        seen_ids = {species_id}

        while True:
            pre = self.pre_evolution_catalog.get(walker_id)
            if not pre or pre["speciesId"] in seen_ids:
                break
            ancestor_ids.append(pre["speciesId"])
            seen_ids.add(pre["speciesId"])
            walker_id = pre["speciesId"]

        ancestor_ids.reverse()

        # Detalle completo de cada ancestro -- hace falta su propio
        # species_details() para saber CÓMO evoluciona hacia el
        # siguiente eslabón (nivel/objeto/etc.), no solo su nombre.
        details_by_species_id = {species_id: original_details}

        for ancestor_id in ancestor_ids:
            try:
                details_by_species_id[ancestor_id] = (
                    self._species_details_with_hackroom_overrides(ancestor_id)
                )
            except Exception:
                details_by_species_id[ancestor_id] = {}

        ancestors = []
        ancestor_chain_ids = ancestor_ids + [species_id]

        for index, stage_id in enumerate(ancestor_ids):
            stage_details = details_by_species_id.get(stage_id, {})
            next_stage_id = ancestor_chain_ids[index + 1]

            # BUG REAL corregido (09/09/2026, mismo patrón que ya
            # se arregló en _build_forward_evolution_node() -- acá
            # se había quedado afuera): `next(...)` se quedaba con
            # la PRIMERA evolución que matcheara `next_stage_id` y
            # descartaba el resto -- rompía justo con las especies
            # "Trade Evolutions" del hackroom (Trade + amistad +
            # nivel, las tres apuntan al mismo destino) cuando esa
            # especie aparece como ANCESTRO de otra (ej. si algún
            # día se abre la cadena completa desde Alakazam, el
            # paso "Kadabra -> Alakazam" tiene que mostrar los 3
            # métodos, no solo uno).
            matching_evolutions = [
                evolution
                for evolution in stage_details.get("evolutions", [])
                if evolution.get("toSpeciesId") == next_stage_id
            ]

            ancestors.append({
                "speciesId": stage_id,
                "name": stage_details.get("name") or f"#{stage_id}",
                "transitionsToNext": [
                    self._resolve_evolution_transition(evolution)
                    for evolution in matching_evolutions
                ],
            })

        # 2. Árbol hacia adelante desde `species_id`, con todas las
        # ramas -- ver _build_forward_evolution_node().
        current_node = self._build_forward_evolution_node(
            species_id, original_details, 2, seen_ids, species_id
        )

        return {"ancestors": ancestors, "current": current_node}

    def get_species_modal_data(self, species_id):
        """
        Modal "Pokédex" de detalle de especie (GUI v2, roadmap
        07/09/2026, sección 4.2) -- junta las piezas ya confirmadas
        y curadas por separado:

        - Tipo/stats base/habilidades (bridge PKHeX,
          species_details(), ver Program.cs).
        - Cadena de evolución completa (pre-evolución + especie
          actual + evoluciones siguientes) -- ver
          _build_evolution_chain().
        - Resistencias/debilidades/inmunidades -- CÁLCULO LOCAL
          puro a partir del tipo (type_effectiveness.py +
          data/type_chart.json), no un dato para pedirle a nadie.
        - Altura/peso/categoría/descripción -- dataset estático
          curado (SpeciesExtraCatalog), no PKHeX (ver el docstring
          largo en build_species_extra.py para el porqué).

        No necesita memoria del juego -- species_id ya lo tiene el
        frontend (viene de `slot.speciesId`, ya presente en cada
        tarjeta de la página Pokémon desde antes).
        """

        try:
            details = self._species_details_with_hackroom_overrides(species_id)
        except Exception as error:
            return {"error": str(error)}

        if "error" in details:
            return details

        effectiveness = compute_effectiveness(
            details.get("type1Key", ""),
            details.get("type2Key", ""),
            self.type_chart_catalog,
        )

        categorized = categorize_effectiveness(effectiveness)

        details["evolutionChain"] = self._build_evolution_chain(
            species_id, details
        )
        details["weaknesses"] = categorized["weaknesses"]
        details["resistances"] = categorized["resistances"]
        details["immunities"] = categorized["immunities"]

        extra = self.species_extra_catalog.get(species_id)
        details["heightM"] = extra["heightM"]
        details["weightKg"] = extra["weightKg"]
        details["genus"] = extra["genus"]
        details["description"] = extra["description"]

        return details
