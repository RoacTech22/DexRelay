"""
Textos en español de los líderes, el Alto Mando y la campeona de Kalos
(P4, 07/10/2026). Los equipos viven en data/gym_leaders_xy.json; acá solo
va lo que ese archivo no trae, con el mismo criterio que ORAS (nombres de
localización España, WikiDex). Los retratos salen de
assets/gym_leaders/kalos/N.png (N = orden, 1-13).
"""

from __future__ import annotations

from app.services.gym_leaders import LeaderSpec

KALOS_LEADER_NAMES_ES = {
    1: "Violeta",
    2: "Lino",
    3: "Corelia",
    4: "Amaro",
    5: "Lem",
    6: "Valeria",
    7: "Astrid",
    8: "Edel",
    9: "Malva",
    10: "Narciso",
    11: "Tileo",
    12: "Drácena",
    13: "Dianta",
}

# Clave = `badgeName` / `gymLocation` en inglés del dataset.
KALOS_BADGE_NAMES_ES = {
    "Bug Badge": "Medalla Bicho",
    "Cliff Badge": "Medalla Acantilado",
    "Rumble Badge": "Medalla Lucha",
    "Plant Badge": "Medalla Planta",
    "Voltage Badge": "Medalla Voltaje",
    "Fairy Badge": "Medalla Hada",
    "Psychic Badge": "Medalla Psíquica",
    "Iceberg Badge": "Medalla Iceberg",
}

KALOS_LOCATION_NAMES_ES = {
    "Santalune City": "Ciudad Novarte",
    "Cyllage City": "Ciudad Relieve",
    "Shalour City": "Ciudad Yantra",
    "Coumarine City": "Ciudad Témpera",
    "Lumiose City": "Ciudad Luminalia",
    "Laverre City": "Ciudad Romantis",
    "Anistar City": "Ciudad Fluxus",
    "Snowbelle City": "Ciudad Fractal",
    "Pokémon League": "Liga Pokémon",
}

KALOS_LEADER_SPEC = LeaderSpec(
    data_file="gym_leaders_xy.json",
    names_es=KALOS_LEADER_NAMES_ES,
    badge_names_es=KALOS_BADGE_NAMES_ES,
    location_names_es=KALOS_LOCATION_NAMES_ES,
    portrait_dir="kalos/",
    portrait_overrides={},
)
