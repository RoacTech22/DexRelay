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

No lee memoria ni necesita el bridge PKHeX -- es 100% el dataset
estático ya commiteado (data/gym_leaders.json, Fase A).
"""

from __future__ import annotations

import json

from app.core import paths


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
# como "No disponible".
GYM_ABILITY_NAMES_ES = {
    "Sturdy": "Robustez",
    "Magnet Pull": "Imán",
    "Guts": "Agallas",
    "Soundproof": "Insonorizar",
    "Flame Body": "Cuerpo Llama",
    "Simple": "Simple",
    "White Smoke": "Humo Blanco",
    "Truant": "Pereza",
    "Vital Spirit": "Espíritu Vital",
    "Keen Eye": "Vista Lince",
    "Natural Cure": "Cura Natural",
    "Levitate": "Levitación",
    "Swift Swim": "Nado Rápido",
    "Oblivious": "Despiste",
    "Thick Fat": "Sebo",
    "Marvel Scale": "Escama Especial",
}

# Tipo de cada uno de los 64 movimientos que aparecen en los 8
# equipos de líder (06/09/2026, a pedido del usuario: "por qué no
# tienes los tipos de los movimientos también deberíamos tener ese
# dato"). A diferencia de los nombres de líderes/insignias/ciudades
# (que sí tienen variantes de localización), el tipo de un
# movimiento es un dato único y bien documentado en toda fuente
# Pokémon (Bulbapedia, Serebii, el juego mismo) -- no hace falta
# investigar caso por caso, es conocimiento estándar de la
# franquicia. Clave en inglés (igual que "moves" en el dataset).
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

    def __init__(self, data_path=None):
        self.data_path = (
            data_path
            if data_path is not None
            else paths.path("data", "gym_leaders.json")
        )
        self._leaders = None

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
                    "abilityEs": GYM_ABILITY_NAMES_ES.get(ability, ability),
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
