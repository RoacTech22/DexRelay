"""
Bosses (P4, 07/10/2026): datos de líderes, Alto Mando y campeón de ORAS y de
Kalos, catálogo por juego y tarjeta "próximo líder" (con las 8 medallas pasa
al Alto Mando).
"""

import json
from pathlib import Path

from app.services.gym_leaders import GymLeaderCatalog
from app.services.kalos_leaders import KALOS_LEADER_SPEC

DATA = Path(__file__).resolve().parents[1] / "data"
ASSETS = Path(__file__).resolve().parents[1] / "assets" / "gym_leaders"


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))["leaders"]


def _catalog(spec=None):
    catalog = GymLeaderCatalog(spec=spec)
    catalog._resolve_ability_es = lambda name: name
    catalog._resolve_move_es = lambda name: name
    catalog._resolve_item_es = lambda name: name
    return catalog


def test_datasets_de_oras_y_kalos_traen_8_lideres_4_del_alto_mando_y_el_campeon():
    for name in ("gym_leaders.json", "gym_leaders_xy.json"):
        leaders = _load(name)

        assert [leader["order"] for leader in leaders] == list(range(1, 14))
        assert [leader.get("kind", "gym") for leader in leaders] == (
            ["gym"] * 8 + ["elite4"] * 4 + ["champion"]
        )


def test_cada_equipo_tiene_un_unico_as_en_el_ultimo_pokemon_y_datos_completos():
    for name in ("gym_leaders.json", "gym_leaders_xy.json"):
        for leader in _load(name):
            team = leader["team"]

            assert team and team[-1]["isAce"], leader["name"]
            assert sum(1 for mon in team if mon["isAce"]) == 1, leader["name"]

            for mon in team:
                assert mon["speciesId"] > 0
                assert mon["ability"], (leader["name"], mon["species"])
                assert 3 <= len(mon["moves"]) <= 4, (leader["name"], mon["species"])
                assert all(mon["moves"]), (leader["name"], mon["species"])


def test_correcciones_de_ronald_en_los_equipos_de_kalos():
    by_name = {leader["name"]: leader for leader in _load("gym_leaders_xy.json")}

    mienfoo = by_name["Korrina"]["team"][0]
    assert (mienfoo["species"], mienfoo["ability"]) == ("Mienfoo", "Inner Focus")

    jumpluff = by_name["Ramos"]["team"][0]
    assert jumpluff["moves"] == ["Acrobatics", "Grass Knot", "Leech Seed"]

    drasna = [mon["species"] for mon in by_name["Drasna"]["team"]]
    assert drasna == ["Dragalge", "Altaria", "Druddigon", "Noivern"]
    assert by_name["Drasna"]["team"][-1]["moves"][-1] == "Super Fang"

    siebold = [mon["species"] for mon in by_name["Siebold"]["team"]]
    assert siebold[1] == "Gyarados"

    gardevoir = by_name["Diantha"]["team"][-1]
    assert (gardevoir["ability"], gardevoir["item"]) == ("Trace", "Gardevoirite")


def test_campeon_de_oras_sale_de_la_captura_de_ronald():
    steven = _load("gym_leaders.json")[-1]
    metagross = steven["team"][-1]

    assert [mon["species"] for mon in steven["team"]] == [
        "Skarmory", "Claydol", "Aggron", "Cradily", "Armaldo", "Metagross",
    ]
    assert metagross["level"] == 59 and metagross["item"] == "Metagrossite"
    assert metagross["ability"] == "Clear Body"
    assert steven["team"][3]["ability"] == "Suction Cups"


def test_oras_sigue_igual_en_sus_8_lideres():
    leaders = _catalog().list_all()
    gyms = [leader for leader in leaders if leader["kind"] == "gym"]

    assert [leader["nameEs"] for leader in gyms] == [
        "Petra", "Marcial", "Erico", "Candela", "Norman", "Alana", "Vito y Letti", "Plubio",
    ]
    assert gyms[0]["portraitFile"] == "faces/6.png"  # override histórico de ORAS
    assert [leader["nameEs"] for leader in leaders[8:]] == [
        "Sixto", "Fátima", "Nívea", "Dracón", "Máximo Peñas",
    ]
    assert leaders[8]["portraitFile"] == "faces/9.png"


def test_kalos_usa_su_propio_catalogo_y_retratos():
    leaders = _catalog(KALOS_LEADER_SPEC).list_all()

    assert [leader["nameEs"] for leader in leaders] == [
        "Violeta", "Lino", "Corelia", "Amaro", "Lem", "Valeria", "Astrid", "Edel",
        "Malva", "Narciso", "Tileo", "Drácena", "Dianta",
    ]
    assert leaders[0]["badgeNameEs"] == "Medalla Bicho"
    assert leaders[0]["gymLocationEs"] == "Ciudad Novarte"
    assert leaders[2]["portraitFile"] == "kalos/faces/3.png"
    assert leaders[8]["kind"] == "elite4" and leaders[12]["kind"] == "champion"
    assert leaders[8]["levelCap"] == 65  # Talonflame, el más fuerte de Malva


def test_alto_mando_y_campeon_tienen_rostro_y_cuerpo_completo_en_disco():
    from app.games.oras.profile import ALPHA_SAPPHIRE, OMEGA_RUBY
    from app.games.xy.profile import POKEMON_X, POKEMON_Y

    for profile, folder in (
        (ALPHA_SAPPHIRE, ""), (OMEGA_RUBY, ""),
        (POKEMON_X, "kalos"), (POKEMON_Y, "kalos"),
    ):
        names = profile.content.league_names
        assert len(names) == 5
        assert profile.content.leader_portrait_set == folder

        for number in range(9, 14):
            assert (ASSETS / folder / "faces" / f"{number}.png").exists()
            assert (ASSETS / folder / "full" / f"{number}.png").exists()

    assert OMEGA_RUBY.content.league_names == tuple(
        leader["nameEs"] for leader in _catalog().list_all()[8:]
    )
    assert POKEMON_X.content.league_names == tuple(
        leader["nameEs"] for leader in _catalog(KALOS_LEADER_SPEC).list_all()[8:]
    )


def test_los_retratos_existentes_de_los_8_lideres_estan_en_disco():
    for number in range(1, 9):
        assert (ASSETS / f"{number}.png").exists()
        assert (ASSETS / "kalos" / f"{number}.png").exists()
        assert (ASSETS / "faces" / f"{number}.png").exists()
        assert (ASSETS / "kalos" / "faces" / f"{number}.png").exists()
