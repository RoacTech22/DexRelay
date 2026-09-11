"""
Carga el dataset estático de líderes de gimnasio curado en
data/gym_leaders.json (roadmap sección 3.1, Fase A) y agrega lo que
el JSON no trae:

1. `nameEs`: el nombre en español de cada líder. El dataset curado
   (pokemondb.net/dittobase.com) usa el nombre en inglés (Roxanne,
   Brawly, ...) porque así lo trae la fuente. La localización al
   español YA existe en el proyecto -- la página Medallas
   (index.html, "Líderes de Gimnasio") tiene los 8 nombres
   correctos a mano, confirmados por el usuario. Se reusan acá tal
   cual en vez de volver a escribirlos/traducirlos, para no tener
   dos fuentes de verdad para el mismo dato.
2. `badgeNameEs`/`gymLocationEs`: traducción al español de la
   insignia y la ciudad (06/09/2026, a pedido del usuario -- el
   dataset trae "Stone Badge"/"Rustboro City" en inglés).
   Verificadas contra WikiDex/Bulbapedia (localización España,
   mismo criterio que los nombres de los líderes): la ciudad de
   cada líder está confirmada cruzando el nombre real del líder
   que aparece en cada artículo de WikiDex (ej. "Erico, el líder
   del Gimnasio de Ciudad Malvalona" confirma Erico=Malvalona, y
   "desafiar a la Líder de gimnasio Petra" en la guía de Ciudad
   Férrica confirma Petra=Rustboro/Férrica).
3. `portraitIndex`: qué archivo de sprite (`assets/gym_leaders/N.png`)
   usar para el retrato -- normalmente igual a `order`, EXCEPTO para
   order 1 y 6 (ver GYM_LEADER_PORTRAIT_OVERRIDES).
4. `levelCap`: el nivel más alto dentro del equipo de ese líder
   (roadmap 3.2, "nivel máximo según siguiente líder"). Se toma el
   máximo de `level` sobre todo el equipo en vez de asumir que
   siempre es el Ace -- más robusto ante cualquier caso raro futuro
   donde el Ace no sea el de nivel más alto (no pasa hoy en los 8
   equipos curados, pero no hace falta depender de esa asunción).
5. `abilityEs`/`movesEs`/`itemEs`: traducción al español de la
   habilidad, cada movimiento, y el objeto equipado del equipo.

   CORRECCIÓN REAL (09/09/2026, reportado por el usuario jugando el
   hackroom Rising Ruby/Sinking Sapphire -- Fase E: "el idioma de
   los movimientos y habilidades se han mezclado, aparecen algunos
   en español y otros en inglés", y después también "los objetos
   de los Pokémon de los líderes también están en inglés"): antes
   esto se resolvía en el
   FRONTEND con dos diccionarios chicos a mano (MOVE_NAME_ES, 64
   movimientos, y GYM_ABILITY_NAMES_ES, 24 habilidades) -- cubrían
   justo lo que necesitaba el juego BASE (8 líderes, 24 Pokémon),
   pero el hackroom usa muchos más movimientos/habilidades reales
   que no estaban en esas listas, así que se colaba texto en
   inglés. Ahora se resuelve acá, del lado del backend, contra el
   bridge PKHeX (MoveCatalog/AbilityCatalog, mismo mecanismo ya
   confirmado 100% correcto para nombres de movimiento el
   09/09/2026 -- ver tools/probes/verificar_nombres_movimiento_es.py)
   -- cubre CUALQUIER movimiento/habilidad real de Gen 6, no solo
   los que ya se habían visto. Si el bridge no está disponible (o
   un nombre puntual no matchea contra el dataset de identifiers en
   inglés), cae al nombre en inglés tal cual -- nunca inventa una
   traducción.

No lee memoria en vivo -- es 100% el dataset estático ya commiteado
(data/gym_leaders.json o data/gym_leaders_rrss.json, según
config.json -> hackroom.enabled), aunque SÍ necesita el bridge
PKHeX arrancado para resolver abilityEs/movesEs la primera vez
(después queda cacheado en disco, ver MoveCatalog/AbilityCatalog).
"""

from __future__ import annotations

import json

from app.core import paths
from app.services.ability_catalog import AbilityCatalog
from app.services.ability_description import AbilityDescriptionCatalog
from app.services.item_catalog import ItemCatalog
from app.services.item_description import ItemDescriptionCatalog
from app.services.move_catalog import MoveCatalog
from app.services.move_description import MoveDescriptionCatalog


# Mismo orden 1-8 que gym_leaders.json y que el bitfield de
# medallas (badges_service.py, BADGE_COUNT=8, orden ya confirmado)
# -- índice 0 del bitfield = líder de order=1, y así sucesivamente.
#
# Corrección 06/09/2026 (a pedido del usuario, tras comparar la
# pestaña Líderes nueva contra el juego real): "Alana" y "Petra"
# estaban intercambiados -- la página Medallas (index.html, sección
# "Líderes de Gimnasio") también tenía este mismo error a mano, se
# corrigió ahí también para no dejar dos fuentes de verdad
# contradictorias. El líder de order=1 (tipo Roca, Ciudad Férrica,
# Insignia Piedra) es Petra, no Alana.
GYM_LEADER_NAMES_ES = {
    1: "Petra",
    2: "Marcial",
    3: "Erico",
    4: "Candela",
    5: "Norman",
    6: "Alana",
    7: "Vito y Letti",
    8: "Plubio",
}

# Insignia y ciudad en español (06/09/2026), verificadas contra
# WikiDex -- localización España, mismo criterio que
# GYM_LEADER_NAMES_ES. La clave es el `badgeName`/`gymLocation` en
# inglés tal como vienen en el dataset curado, para no depender del
# orden (por si el dataset cambia de orden en el futuro).
GYM_BADGE_NAMES_ES = {
    "Stone Badge": "Insignia Piedra",
    "Knuckle Badge": "Insignia Puño",
    "Dynamo Badge": "Insignia Dinamo",
    "Heat Badge": "Insignia Calor",
    "Balance Badge": "Insignia Equilibrio",
    "Feather Badge": "Insignia Pluma",
    "Mind Badge": "Insignia Mente",
    "Rain Badge": "Insignia Lluvia",
}

GYM_LOCATION_NAMES_ES = {
    "Rustboro City": "Ciudad Férrica",
    "Dewford Town": "Pueblo Azuliza",
    "Mauville City": "Ciudad Malvalona",
    "Lavaridge Town": "Pueblo Lavacalda",
    "Petalburg City": "Ciudad Petalia",
    "Fortree City": "Ciudad Arborada",
    "Mossdeep City": "Ciudad Algaria",
    "Sootopolis City": "Arrecípolis",
}

# Habilidad de cada Pokémon de cada líder (06/09/2026, a pedido del
# usuario -- antes se mostraba "No disponible" en toda la app).
# Investigadas contra Bulbapedia (páginas "X Gym", sección
# "Pokémon Omega Ruby and Alpha Sapphire") y cruzadas con un
# playthrough completo de ORAS -- en los 24 casos el nivel coincidió
# exacto con el dataset ya curado, lo que confirma la fuente. A
# diferencia de Naturaleza/IVs/EVs (que nunca se pueden saber sin el
# save real del entrenador rival), la habilidad de un Pokémon de un
# líder de gimnasio SÍ está fija en los datos del juego y documentada
# en guías -- por eso acá sí se cura como dato real, no se deja
# como "No disponible". El valor en sí (ej. "Sturdy") vive en
# data/gym_leaders.json/gym_leaders_rrss.json -- acá abajo ya NO
# hay un diccionario de traducción a mano (GYM_ABILITY_NAMES_ES se
# eliminó el 09/09/2026, ver punto 5 del docstring del módulo):
# la traducción a español se resuelve dinámicamente vía
# AbilityCatalog/AbilityDescriptionCatalog en _resolve_ability_es().

# Tipo de cada uno de los 64 movimientos que aparecen en los 8
# equipos de líder DEL JUEGO BASE (06/09/2026, a pedido del
# usuario: "por qué no tienes los tipos de los movimientos también
# deberíamos tener ese dato"). A diferencia de los nombres de
# líderes/insignias/ciudades (que sí tienen variantes de
# localización), el tipo de un movimiento es un dato único y bien
# documentado en toda fuente Pokémon (Bulbapedia, Serebii, el juego
# mismo) -- no hace falta investigar caso por caso, es conocimiento
# estándar de la franquicia. Clave en inglés (igual que "moves" en
# el dataset).
#
# GAP CONOCIDO (09/09/2026, hackroom Rising Ruby/Sinking Sapphire):
# esta tabla NO cubre los movimientos nuevos que usa
# gym_leaders_rrss.json -- quedan con moveTypeKeys=None (sin ícono
# de tipo), a diferencia de abilityEs/movesEs que ya se resuelven
# dinámicamente vía el bridge. No es lo que reportó el usuario
# (mezcla de idioma, ya resuelta) así que se deja para otra pasada
# si hace falta -- el tipo de un MOVIMIENTO no depende del idioma,
# pero sí necesitaría el mismo tipo de resolución dinámica (el
# bridge no expone el tipo de un movimiento por su nombre en
# inglés directamente, haría falta cruzar por id como con
# abilityEs/movesEs).
MOVE_TYPE_KEYS = {
    "Aerial Ace": "Flying", "Air Cutter": "Flying", "Amnesia": "Psychic",
    "Aqua Ring": "Water", "Arm Thrust": "Fighting", "Attract": "Normal",
    "Aurora Beam": "Ice", "Body Slam": "Normal", "Bulk Up": "Fighting",
    "Calm Mind": "Psychic", "Charge": "Electric", "Chip Away": "Normal",
    "Cotton Guard": "Grass", "Curse": "Ghost", "Defense Curl": "Normal",
    "Disarming Voice": "Fairy", "Double Team": "Normal", "Dragon Breath": "Dragon",
    "Draining Kiss": "Fairy", "Earth Power": "Ground", "Earthquake": "Ground",
    "Encore": "Normal", "Endeavor": "Normal", "Feint Attack": "Dark",
    "Fury Swipes": "Normal", "Harden": "Normal", "Horn Drill": "Normal",
    "Hydro Pump": "Water", "Hypnosis": "Psychic", "Ice Beam": "Ice",
    "Karate Chop": "Fighting", "Knock Off": "Dark", "Lava Plume": "Fire",
    "Leer": "Normal", "Light Screen": "Psychic", "Magnet Bomb": "Steel",
    "Mud Sport": "Ground", "Overheat": "Fire", "Protect": "Normal",
    "Psychic": "Psychic", "Quick Attack": "Normal", "Rain Dance": "Water",
    "Recover": "Normal", "Retaliate": "Normal", "Rock Slide": "Rock",
    "Rock Throw": "Rock", "Rock Tomb": "Rock", "Rollout": "Rock",
    "Roost": "Flying", "Sand Attack": "Ground", "Seismic Toss": "Fighting",
    "Solar Beam": "Grass", "Steel Wing": "Steel", "Sunny Day": "Fire",
    "Supersonic": "Normal", "Swagger": "Normal", "Sweet Kiss": "Fairy",
    "Tackle": "Normal", "Thunder Wave": "Electric", "Volt Switch": "Electric",
    "Water Pulse": "Water", "Waterfall": "Water", "Yawn": "Normal",
    "Zen Headbutt": "Psychic",
}

# Qué archivo de sprite (assets/gym_leaders/N.png) le corresponde a
# cada líder (06/09/2026, a pedido del usuario: "el sprite de Petra
# está intercambiado con el de Alana"). El bug está en los ARCHIVOS
# de imagen en sí (1.png y 6.png tienen las caras cambiadas), no en
# el nombre -- así que en vez de tocar binarios, se desacopla
# "índice de retrato" de "order": por defecto son iguales, salvo
# estas dos excepciones puntuales. Si en algún momento se
# reemplazan/corrigen los archivos de imagen, esto se puede borrar.
GYM_LEADER_PORTRAIT_OVERRIDES = {
    1: 6,
    6: 1,
}


class GymLeaderCatalog:
    """
    Instancia única, cacheada en memoria después de la primera
    lectura -- mismo patrón que SpeciesCatalog/LocationCatalog/
    MoveDataCatalog (el archivo no cambia mientras la app corre).
    """

    def __init__(self, data_path=None, bridge=None):
        self.data_path = (
            data_path
            if data_path is not None
            else paths.path("data", "gym_leaders.json")
        )
        self._leaders = None

        # Fase E (09/09/2026): resolución dinámica de nombres en
        # español, ver punto 5 del docstring del módulo.
        #
        # CORRECCIÓN REAL (09/09/2026, reportado por el usuario:
        # "ahora no me salen algunas evoluciones y en algunos
        # pokemon no me muestra todos los datos" -- síntoma
        # mezclado entre especies SIN relación con el hackroom,
        # como Nidorino y Bronzong, que descartó de entrada un bug
        # de lógica del árbol de evolución): sin un `bridge`
        # compartido, cada uno de estos 3 catálogos creaba SU
        # PROPIA instancia de PKHeXBridge -- y como hay DOS
        # GymLeaderCatalog (vanilla + hackroom, ver
        # self.gym_leader_catalog/_hackroom en api.py), eso podía
        # llegar a levantar hasta 6 procesos de dotnet nuevos
        # compitiendo con self.modal_bridge (el que usa
        # species_details() para el modal Pokédex) por CPU/memoria
        # al arrancar -- exactamente el tipo de contención que
        # explica datos "a veces sí, a veces no" en especies sin
        # ninguna relación entre sí. Ahora se recibe un bridge ya
        # existente (típicamente self.modal_bridge, ver api.py) y
        # se lo pasa a los 3 catálogos -- un solo proceso de dotnet
        # para toda la app, como debería haber sido desde el
        # principio.
        self._ability_catalog = AbilityCatalog(bridge=bridge)
        self._ability_description_catalog = AbilityDescriptionCatalog()
        self._move_catalog = MoveCatalog(bridge=bridge)
        self._move_description_catalog = MoveDescriptionCatalog()
        self._item_catalog = ItemCatalog(bridge=bridge)
        self._item_description_catalog = ItemDescriptionCatalog()

    def _resolve_ability_es(self, ability_name):
        """
        "Defeatist" -> id vía AbilityDescriptionCatalog (dataset de
        identifiers en inglés ya curado) -> nombre en español vía
        AbilityCatalog (bridge PKHeX). Cae al nombre en inglés tal
        cual si cualquiera de los dos pasos falla -- nunca inventa.
        """

        ability_id = self._ability_description_catalog.get_id_by_name(
            ability_name
        )

        if ability_id is None:
            return ability_name

        return self._ability_catalog.get_name(ability_id) or ability_name

    def _resolve_move_es(self, move_name):
        """Idem _resolve_ability_es(), para movimientos."""

        move_id = self._move_description_catalog.get_id_by_name(
            move_name
        )

        if move_id is None:
            return move_name

        return self._move_catalog.get_name(move_id) or move_name

    def _resolve_item_es(self, item_name):
        """
        Idem _resolve_ability_es(), para ítems -- reportado por el
        usuario jugando el hackroom (09/09/2026): "los objetos de
        los Pokémon de los líderes también están en inglés". Mismo
        mecanismo, con el cruce extra de numeración que hace falta
        para ítems (ver ItemDescriptionCatalog.get_id_by_name()).
        `item_name` puede ser None (Pokémon sin objeto) -- se
        devuelve None tal cual, sin tocar.
        """

        if not item_name:
            return item_name

        item_id = self._item_description_catalog.get_id_by_name(
            item_name
        )

        if item_id is None:
            return item_name

        return self._item_catalog.get_name(item_id) or item_name

    def _ensure_loaded(self):

        if self._leaders is not None:
            return

        if not self.data_path.exists():
            # Degradación con gracia (mismo criterio que
            # MoveDataCatalog): si el dataset no está, la pestaña
            # Líderes queda vacía en vez de romper toda la
            # respuesta de get_nuzlocke_page_data().
            self._leaders = []
            return

        with open(self.data_path, "r", encoding="utf-8") as file:
            raw = json.load(file)

        raw_leaders = sorted(
            raw.get("leaders", []),
            key=lambda leader: leader.get("order", 0),
        )

        leaders = []

        for leader in raw_leaders:
            order = leader.get("order")
            raw_team = leader.get("team", [])
            badge_name = leader.get("badgeName")
            gym_location = leader.get("gymLocation")

            level_cap = max(
                (member.get("level", 0) for member in raw_team),
                default=0,
            )

            # Copia de cada miembro del equipo + habilidad traducida
            # + tipo de cada movimiento (no se muta el dict
            # original del JSON cacheado).
            team = []
            for member in raw_team:
                ability = member.get("ability")
                moves = member.get("moves", [])
                team.append({
                    **member,
                    "abilityEs": self._resolve_ability_es(ability),
                    "itemEs": self._resolve_item_es(member.get("item")),
                    "movesEs": [
                        self._resolve_move_es(move) for move in moves
                    ],
                    "moveTypeKeys": [
                        MOVE_TYPE_KEYS.get(move) for move in moves
                    ],
                })

            leaders.append({
                "order": order,
                "portraitIndex": GYM_LEADER_PORTRAIT_OVERRIDES.get(
                    order, order
                ),
                "name": leader.get("name"),
                "nameEs": GYM_LEADER_NAMES_ES.get(
                    order, leader.get("name")
                ),
                "typeKey": leader.get("typeKey"),
                "badgeName": badge_name,
                "badgeNameEs": GYM_BADGE_NAMES_ES.get(
                    badge_name, badge_name
                ),
                "gymLocation": gym_location,
                "gymLocationEs": GYM_LOCATION_NAMES_ES.get(
                    gym_location, gym_location
                ),
                "team": team,
                "levelCap": level_cap,
            })

        self._leaders = leaders

    def list_all(self):
        """
        Devuelve la lista de 8 líderes (o vacía si el dataset no
        está disponible), ordenada por `order`. Cada entrada trae
        `nameEs`/`badgeNameEs`/`gymLocationEs`/`portraitIndex`/
        `levelCap` ya resueltos -- no incluye el estado `earned`
        (obtenida/pendiente), que depende de las medallas actuales
        del run y se calcula en el llamador
        (Api.get_nuzlocke_page_data(), que sí tiene `state.badges`
        a mano).
        """

        self._ensure_loaded()
        return self._leaders
