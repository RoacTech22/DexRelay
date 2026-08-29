"""
Valida la detección automática de un Pokémon restaurado a partir
de un fósil (29/08/2026, investigación puntual con debug print en
LocationResolver, confirmada en el juego real reviviendo un
Tirtouga en Rustboro City).

Hallazgo clave: el motor revive un fósil internamente como un
huevo que "nace" al instante -- pero el placeholder de nickname
es "Egg" (inglés, SIN traducir), a diferencia del "Huevo" que sí
ve el jugador para un huevo real del Día Cuidado. Además, a
diferencia de un huevo real, nunca llega a resolver `eggLocation`
("Entregado por") -- en cambio, `metLocation` SÍ trae una ruta
real (ej. "Rustboro City", donde está Devon Corp).

Se ignora igual que un huevo sin nacer mientras el nickname sea
"Egg", pero se recuerda la especie en
`fossil_pending_species_ids` para que, apenas se resuelva el
nombre real, `_register_new_capture()` lo marque como
status="especial"/origin="fosil" en vez de una captura salvaje
normal en esa ciudad.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.services.nuzlocke_service import NuzlockeService


class FakeStorage:
    def __init__(self):
        self.saved = None

    def load(self):
        return {
            "roster": [],
            "graveyard": [],
            "encounters": [],
            "pending_encounters": [],
            "starter_assigned": False,
        }

    def save(self, data):
        self.saved = data


def _team_with(*slots):
    padded = list(slots) + [
        {"slot": i, "empty": True}
        for i in range(len(slots) + 1, 7)
    ]
    return padded


def _starter():
    return {
        "slot": 1,
        "empty": False,
        "nickname": "Rocío",
        "species": "Mudkip",
        "speciesId": 258,
        "level": 10,
        "hp": 30,
        "maxHp": 30,
        "shiny": False,
        "metLocation": "",
    }


def _new_service_with_starter():
    service = NuzlockeService(FakeStorage())
    starter = _starter()
    service.update(_team_with(starter))
    return service, starter


def test_fosil_sin_revivir_todavia_no_cuenta_para_nada():

    service, starter = _new_service_with_starter()

    fossil_pending = {
        "slot": 2,
        "empty": False,
        "nickname": "Egg",
        "species": "Tirtouga",
        "speciesId": 564,
        "level": 1,
        "hp": 20,
        "maxHp": 20,
        "shiny": False,
        "metLocation": "",
    }

    for _ in range(3):
        state = service.update(
            _team_with(starter, fossil_pending)
        )
        # Solo el inicial -- el fósil sin revivir del todo no
        # cuenta como captura, ni siquiera tras varios ciclos.
        assert len(state["roster"]) == 1

    assert state["encounters"] == [
        e for e in state["encounters"]
        if e["location"] == "Inicial"
    ]
    assert state["pending_encounters"] == []

    # La especie quedó recordada internamente, esperando el
    # nombre real.
    assert 564 in service._data.get(
        "fossil_pending_species_ids", []
    )

    print(
        "OK - un fósil todavía no revivido (placeholder 'Egg') "
        "no cuenta como captura para nada, ni se pierde la "
        "marca tras varios ciclos"
    )


def test_fosil_revivido_se_registra_como_especial_fosil():

    service, starter = _new_service_with_starter()

    fossil_pending = {
        "slot": 2,
        "empty": False,
        "nickname": "Egg",
        "species": "Tirtouga",
        "speciesId": 564,
        "level": 1,
        "hp": 20,
        "maxHp": 20,
        "shiny": False,
        "metLocation": "",
    }

    service.update(_team_with(starter, fossil_pending))

    # Se resuelve: mismo ciclo real reportado por el usuario, el
    # nickname ya viene directo con el nombre por defecto de la
    # especie y metLocation resuelto ("Rustboro City").
    revived = {
        **fossil_pending,
        "nickname": "Tirtouga",
        "metLocation": "Rustboro City",
    }

    state = service.update(_team_with(starter, revived))

    assert len(state["roster"]) == 2

    tirtouga_encounters = [
        e for e in state["encounters"]
        if e.get("nickname") == "Tirtouga"
    ]
    assert len(tirtouga_encounters) == 1

    entry = tirtouga_encounters[0]
    assert entry["status"] == "especial"
    assert entry["origin"] == "fosil"
    assert entry["location"] == "Rustboro City"

    assert state["pending_encounters"] == []

    # La marca interna se consumió -- no queda colgada.
    assert 564 not in service._data.get(
        "fossil_pending_species_ids", []
    )

    # Ciclos siguientes: estable, sin duplicar ni volver a
    # marcarlo como fósil pendiente.
    for _ in range(3):
        state = service.update(_team_with(starter, revived))
        assert len(state["roster"]) == 2
        assert len([
            e for e in state["encounters"]
            if e.get("nickname") == "Tirtouga"
        ]) == 1

    print(
        "OK - un fósil revivido se registra como "
        "status='especial'/origin='fosil' en la ruta real "
        "(Rustboro City), sin quedar pendiente ni duplicarse"
    )


def test_fosil_con_ubicacion_tardia_se_resuelve_por_retry():

    service, starter = _new_service_with_starter()

    fossil_pending = {
        "slot": 2,
        "empty": False,
        "nickname": "Egg",
        "species": "Tirtouga",
        "speciesId": 564,
        "level": 1,
        "hp": 20,
        "maxHp": 20,
        "shiny": False,
        "metLocation": "",
    }

    service.update(_team_with(starter, fossil_pending))

    # Se resuelve el nombre, pero el juego TODAVÍA no terminó de
    # escribir metLocation en este ciclo puntual (mismo tipo de
    # timing que ya motivó _retry_pending_captures()).
    revived_sin_ubicacion = {
        **fossil_pending,
        "nickname": "Tirtouga",
        "metLocation": "",
    }

    state = service.update(
        _team_with(starter, revived_sin_ubicacion)
    )

    assert len(state["pending_encounters"]) == 1
    assert state["pending_encounters"][0]["nickname"] == (
        "Tirtouga"
    )
    # La marca de fósil se reagregó -- el retry la va a seguir
    # usando.
    assert 564 in service._data.get(
        "fossil_pending_species_ids", []
    )

    # Un ciclo después, el juego ya terminó de escribir la ruta.
    revived_con_ubicacion = {
        **revived_sin_ubicacion,
        "metLocation": "Rustboro City",
    }

    state = service.update(
        _team_with(starter, revived_con_ubicacion)
    )

    assert state["pending_encounters"] == []

    tirtouga_encounters = [
        e for e in state["encounters"]
        if e.get("nickname") == "Tirtouga"
    ]
    assert len(tirtouga_encounters) == 1
    assert tirtouga_encounters[0]["origin"] == "fosil"
    assert tirtouga_encounters[0]["location"] == (
        "Rustboro City"
    )

    print(
        "OK - si metLocation todavía no está resuelto cuando "
        "el fósil ya tiene nombre, la marca de fósil sobrevive "
        "hasta que el reintento resuelve la ruta real"
    )


def test_fosil_guardado_en_la_caja_pc_tambien_se_detecta():

    service, starter = _new_service_with_starter()

    # Party llena de relleno + starter, el fósil recién revivido
    # cae directo a la Caja PC.
    fossil_pending_boxed = {
        "nickname": "Egg",
        "species": "Tirtouga",
        "speciesId": 564,
        "level": 1,
        "hp": 20,
        "maxHp": 20,
        "shiny": False,
        "metLocation": "",
        "empty": False,
    }

    state = service.update(
        _team_with(starter),
        boxed_party=[fossil_pending_boxed],
    )

    assert 564 in service._data.get(
        "fossil_pending_species_ids", []
    )
    assert len(state["roster"]) == 1

    revived_boxed = {
        **fossil_pending_boxed,
        "nickname": "Tirtouga",
        "metLocation": "Rustboro City",
    }

    state = service.update(
        _team_with(starter),
        boxed_party=[revived_boxed],
    )

    assert len(state["roster"]) == 2

    tirtouga_encounters = [
        e for e in state["encounters"]
        if e.get("nickname") == "Tirtouga"
    ]
    assert len(tirtouga_encounters) == 1
    assert tirtouga_encounters[0]["origin"] == "fosil"

    print(
        "OK - un fósil que cae directo a la Caja PC (party "
        "llena) se detecta igual que si estuviera en party"
    )


def test_fosil_shiny_prioriza_origin_fosil_sobre_shiny():

    service, starter = _new_service_with_starter()

    fossil_pending = {
        "slot": 2,
        "empty": False,
        "nickname": "Egg",
        "species": "Tirtouga",
        "speciesId": 564,
        "level": 1,
        "hp": 20,
        "maxHp": 20,
        "shiny": False,
        "metLocation": "",
    }

    service.update(_team_with(starter, fossil_pending))

    revived_shiny = {
        **fossil_pending,
        "nickname": "Tirtouga",
        "metLocation": "Rustboro City",
        "shiny": True,
    }

    state = service.update(_team_with(starter, revived_shiny))

    tirtouga_encounters = [
        e for e in state["encounters"]
        if e.get("nickname") == "Tirtouga"
    ]
    assert len(tirtouga_encounters) == 1
    assert tirtouga_encounters[0]["status"] == "especial"
    # Prioridad invertida (29/08/2026, a pedido del usuario):
    # fósil/huevo/intercambio le ganan a shiny -- shiny queda
    # como última prioridad.
    assert tirtouga_encounters[0]["origin"] == "fosil"

    print(
        "OK - un fósil shiny se registra como origin='fosil' "
        "(prioridad invertida: fósil/huevo/intercambio le ganan "
        "a shiny), no como 'shiny'"
    )


def test_captura_salvaje_normal_no_se_confunde_con_fosil():

    service, starter = _new_service_with_starter()

    wild = {
        "slot": 2,
        "empty": False,
        "nickname": "Zubat",
        "species": "Zubat",
        "speciesId": 41,
        "level": 5,
        "hp": 15,
        "maxHp": 15,
        "shiny": False,
        "metLocation": "Ruta 116",
    }

    state = service.update(_team_with(starter, wild))

    zubat_encounters = [
        e for e in state["encounters"]
        if e.get("nickname") == "Zubat"
    ]
    assert len(zubat_encounters) == 1
    assert zubat_encounters[0]["status"] == "capturado"
    assert zubat_encounters[0].get("origin") is None

    print(
        "OK - una captura salvaje normal (nunca pasó por 'Egg') "
        "sigue registrándose como 'capturado', sin origin"
    )


def test_fosil_shiny_conserva_flag_shiny_desacoplado_de_origin():
    """
    29/08/2026, a pedido del usuario: el ícono ✨ del panel tiene
    que seguir funcionando aunque el origen ganador ya no sea
    "shiny" (ver test anterior). Se verifica acá que el campo
    `shiny` del encuentro queda en True independientemente del
    `origin` guardado.
    """

    service, starter = _new_service_with_starter()

    fossil_pending = {
        "slot": 2,
        "empty": False,
        "nickname": "Egg",
        "species": "Tirtouga",
        "speciesId": 564,
        "level": 1,
        "hp": 20,
        "maxHp": 20,
        "shiny": False,
        "metLocation": "",
    }

    service.update(_team_with(starter, fossil_pending))

    revived_shiny = {
        **fossil_pending,
        "nickname": "Tirtouga",
        "metLocation": "Rustboro City",
        "shiny": True,
    }

    state = service.update(_team_with(starter, revived_shiny))

    entry = next(
        e for e in state["encounters"]
        if e.get("nickname") == "Tirtouga"
    )

    assert entry["origin"] == "fosil"
    assert entry["shiny"] is True

    # Editar nickname/especie después (mismo camino que la tabla
    # principal del panel) no debe perder la marca de shiny.
    encounters = service.save_encounter(
        entry["location"],
        "Tirtouga",
        "Tirtouga",
        "especial",
    )
    entry_after_edit = next(
        e for e in encounters
        if e["location"] == entry["location"]
    )
    assert entry_after_edit["shiny"] is True
    assert entry_after_edit["origin"] == "fosil"

    print(
        "OK - el campo 'shiny' queda guardado por separado del "
        "'origin' ganador, y sobrevive a una edición posterior "
        "de nickname/especie -- el ícono del panel puede seguir "
        "mostrándose sin importar qué origen ganó"
    )


def test_fosil_que_se_salta_la_ventana_de_egg_igual_se_detecta():
    """
    Reproduce el bug real reportado el 29/08/2026: DexRelay se
    reinició justo antes de revivir el fósil y nunca llegó a ver
    el placeholder "Egg" en ningún ciclo -- el Pokémon apareció
    directo con nombre resuelto, y sin la señal de respaldo se
    registraba como una captura salvaje normal en Rustboro City.

    Con la señal de respaldo (metLocationId == DEVON_CORP_LOCATION_ID,
    190 = Rustboro City / Ciudad Férrica), se detecta igual como
    fósil aunque `fossil_pending_species_ids` nunca haya tenido
    esta especie.
    """

    service, starter = _new_service_with_starter()

    # Nunca pasó por "Egg" en ningún ciclo visible -- aparece
    # directo resuelto, como si DexRelay se hubiera perdido por
    # completo la ventana corta del placeholder.
    revived_sin_egg_previo = {
        "slot": 2,
        "empty": False,
        "nickname": "Tirtouga",
        "species": "Tirtouga",
        "speciesId": 564,
        "level": 1,
        "hp": 20,
        "maxHp": 20,
        "shiny": False,
        "metLocation": "Ciudad Férrica",
        "metLocationId": 190,
    }

    assert 564 not in service._data.get(
        "fossil_pending_species_ids", []
    )

    state = service.update(
        _team_with(starter, revived_sin_egg_previo)
    )

    tirtouga_encounters = [
        e for e in state["encounters"]
        if e.get("nickname") == "Tirtouga"
    ]
    assert len(tirtouga_encounters) == 1
    assert tirtouga_encounters[0]["status"] == "especial"
    assert tirtouga_encounters[0]["origin"] == "fosil"
    assert tirtouga_encounters[0]["location"] == "Ciudad Férrica"

    print(
        "OK - un fósil que nunca pasó por el placeholder 'Egg' "
        "(ventana de polling perdida) igual se detecta como "
        "'fosil', gracias a la señal de respaldo por ID de "
        "ubicación (Devon Corp / Rustboro City)"
    )


def test_captura_salvaje_en_otra_ciudad_no_se_confunde_con_fosil():
    """
    Control: una captura con metLocationId distinto de Devon Corp
    (aunque también sea una ciudad, ej. un regalo cualquiera) NO
    se marca como fósil por la sola presencia de un ID de
    ubicación -- solo el ID específico de Rustboro City dispara la
    señal de respaldo.
    """

    service, starter = _new_service_with_starter()

    gift_en_otra_ciudad = {
        "slot": 2,
        "empty": False,
        "nickname": "Wynaut",
        "species": "Wynaut",
        "speciesId": 360,
        "level": 5,
        "hp": 10,
        "maxHp": 10,
        "shiny": False,
        "metLocation": "Ciudad Lavacalor",
        "metLocationId": 999,
    }

    state = service.update(
        _team_with(starter, gift_en_otra_ciudad)
    )

    wynaut_encounters = [
        e for e in state["encounters"]
        if e.get("nickname") == "Wynaut"
    ]
    assert len(wynaut_encounters) == 1
    assert wynaut_encounters[0]["status"] == "capturado"
    assert wynaut_encounters[0].get("origin") is None

    print(
        "OK - un ID de ubicación distinto al de Devon Corp no "
        "dispara la señal de respaldo, aunque también sea una "
        "ciudad"
    )


def test_dos_fosiles_distintos_se_registran_ambos_sin_pendientes():
    """
    Reproduce el segundo bug real reportado el 29/08/2026: el
    segundo fósil que se revive comparte la MISMA ubicación real
    (Devon Corp / Ciudad Férrica) que el primero -- antes eso
    activaba la protección genérica de "ruta ya tomada" y lo
    mandaba a pending_encounters (correcto para dos capturas
    salvajes DISTINTAS por coincidencia en la misma ruta, pero no
    para esto: revivir varios fósiles en la partida es rutinario).
    Con el branch dedicado (bare-primero-nickname-después), los
    dos quedan registrados directo en la tabla.
    """

    service, starter = _new_service_with_starter()

    primer_fosil = {
        "slot": 2,
        "empty": False,
        "nickname": "Tirtouga",
        "species": "Tirtouga",
        "speciesId": 564,
        "level": 1,
        "hp": 20,
        "maxHp": 20,
        "shiny": False,
        "metLocation": "Ciudad Férrica",
        "metLocationId": 190,
    }

    state = service.update(_team_with(starter, primer_fosil))

    assert state["pending_encounters"] == []
    primer_encuentros = [
        e for e in state["encounters"]
        if e.get("nickname") == "Tirtouga"
    ]
    assert len(primer_encuentros) == 1
    assert primer_encuentros[0]["location"] == "Ciudad Férrica"
    assert primer_encuentros[0]["origin"] == "fosil"

    segundo_fosil = {
        "slot": 3,
        "empty": False,
        "nickname": "Anorith",
        "species": "Anorith",
        "speciesId": 347,
        "level": 1,
        "hp": 15,
        "maxHp": 15,
        "shiny": False,
        "metLocation": "Ciudad Férrica",
        "metLocationId": 190,
    }

    state = service.update(
        _team_with(starter, primer_fosil, segundo_fosil)
    )

    # Sin pendientes -- se registró directo, no fue a la tarjeta
    # de "¿Pokémon Especial?".
    assert state["pending_encounters"] == []

    segundo_encuentros = [
        e for e in state["encounters"]
        if e.get("nickname") == "Anorith"
    ]
    assert len(segundo_encuentros) == 1
    assert segundo_encuentros[0]["origin"] == "fosil"
    # Se diferencia con el nickname, sin pisar al primero.
    assert segundo_encuentros[0]["location"] == (
        "Ciudad Férrica (Anorith)"
    )

    # El primero sigue intacto, sin modificar.
    primer_encuentros_despues = [
        e for e in state["encounters"]
        if e.get("nickname") == "Tirtouga"
    ]
    assert len(primer_encuentros_despues) == 1
    assert primer_encuentros_despues[0]["location"] == (
        "Ciudad Férrica"
    )

    print(
        "OK - dos fósiles distintos con la misma ubicación real "
        "se registran ambos directo en la tabla (bare + "
        "sufijado con nickname), sin caer a pendientes"
    )


def test_captura_extra_se_registra_como_capturado_no_especial():
    """
    29/08/2026, a pedido del usuario: "Captura Extra" es una
    opción más de la tarjeta "¿Pokémon Especial?", pero a
    propósito NO usa status="especial" -- queda como "capturado"
    normal, con una pseudo-ubicación única y el flag
    `extraCapture` para que el panel la muestre distinto.
    """

    service, starter = _new_service_with_starter()

    # Segundo Pokémon de la misma especie que el inicial (species
    # clause) -- no cuenta como encuentro nuevo automático, cae a
    # pending vía alguna vía externa simulada acá directo con
    # save_encounter/pending manual para aislar solo
    # _assign_extra_capture().
    service._data["pending_encounters"].append({
        "nickname": "Codicioso",
        "speciesId": 41,
        "species": "Zubat",
        "shiny": False,
        "metLocation": "",
        "eggLocation": "",
        "caughtAt": "2026-08-29T00:00:00+00:00",
    })

    result = service.assign_special_origin(
        "Codicioso", "captura_extra"
    )

    assert result["pending_encounters"] == []

    entry = next(
        e for e in result["encounters"]
        if e.get("nickname") == "Codicioso"
    )

    assert entry["status"] == "capturado"
    assert entry["origin"] is None
    assert entry["extraCapture"] is True
    assert entry["location"] == "Captura Extra (Codicioso)"

    print(
        "OK - 'Captura Extra' se registra con status='capturado' "
        "(no 'especial'), origin=None, y extraCapture=True para "
        "que el panel la muestre distinto"
    )


def test_captura_extra_conserva_shiny_si_correspondia():

    service, starter = _new_service_with_starter()

    service._data["pending_encounters"].append({
        "nickname": "Brillante",
        "speciesId": 41,
        "species": "Zubat",
        "shiny": True,
        "metLocation": "",
        "eggLocation": "",
        "caughtAt": "2026-08-29T00:00:00+00:00",
    })

    result = service.assign_special_origin(
        "Brillante", "captura_extra"
    )

    entry = next(
        e for e in result["encounters"]
        if e.get("nickname") == "Brillante"
    )

    assert entry["status"] == "capturado"
    assert entry["extraCapture"] is True
    assert entry["shiny"] is True

    print(
        "OK - 'Captura Extra' conserva el flag shiny si el "
        "Pokémon pendiente ya venía marcado como tal"
    )


def test_captura_extra_usa_la_ruta_real_si_esta_libre():
    """
    29/08/2026, corrección a pedido del usuario: la ubicación de
    una "Captura Extra" tiene que ser la ruta real donde se la
    atrapó, no un texto sintético "Captura Extra (nickname)" --
    ese texto queda solo como último recurso cuando no hay
    ninguna ruta real conocida (ver test de arriba).
    """

    service, starter = _new_service_with_starter()

    service._data["pending_encounters"].append({
        "nickname": "Segundo",
        "speciesId": 41,
        "species": "Zubat",
        "shiny": False,
        "metLocation": "Ruta 104",
        "eggLocation": "",
        "caughtAt": "2026-08-29T00:00:00+00:00",
    })

    result = service.assign_special_origin(
        "Segundo", "captura_extra"
    )

    entry = next(
        e for e in result["encounters"]
        if e.get("nickname") == "Segundo"
    )

    assert entry["status"] == "capturado"
    assert entry["extraCapture"] is True
    assert entry["location"] == "Ruta 104"

    print(
        "OK - 'Captura Extra' con ruta real libre usa esa ruta "
        "tal cual como ubicación, no un texto sintético"
    )


def test_captura_extra_con_ruta_ya_tomada_se_diferencia_con_nickname():
    """
    El caso típico: la ruta real ya tiene un encuentro registrado
    (por eso cayó a pendientes en primer lugar) -- se le agrega
    el nickname para no pisar el registro existente, mismo patrón
    que huevo/intercambio/fósil.
    """

    service, starter = _new_service_with_starter()

    primera_captura = {
        "slot": 2,
        "empty": False,
        "nickname": "Primero",
        "species": "Zubat",
        "speciesId": 41,
        "level": 5,
        "hp": 10,
        "maxHp": 10,
        "shiny": False,
        "metLocation": "Ruta 104",
    }

    state = service.update(_team_with(starter, primera_captura))

    assert [
        e for e in state["encounters"]
        if e.get("nickname") == "Primero"
    ][0]["location"] == "Ruta 104"

    service._data["pending_encounters"].append({
        "nickname": "Segundo",
        "speciesId": 42,
        "species": "Golbat",
        "shiny": False,
        "metLocation": "Ruta 104",
        "eggLocation": "",
        "caughtAt": "2026-08-29T00:00:00+00:00",
    })

    result = service.assign_special_origin(
        "Segundo", "captura_extra"
    )

    entry = next(
        e for e in result["encounters"]
        if e.get("nickname") == "Segundo"
    )

    assert entry["location"] == "Ruta 104 (Segundo)"

    # El primero sigue intacto, sin pisar.
    primero = next(
        e for e in result["encounters"]
        if e.get("nickname") == "Primero"
    )
    assert primero["location"] == "Ruta 104"
    assert primero["extraCapture"] is False

    print(
        "OK - 'Captura Extra' con la ruta real ya tomada se "
        "diferencia agregando el nickname, sin pisar el "
        "encuentro original de esa ruta"
    )


if __name__ == "__main__":
    test_fosil_sin_revivir_todavia_no_cuenta_para_nada()
    test_fosil_revivido_se_registra_como_especial_fosil()
    test_fosil_con_ubicacion_tardia_se_resuelve_por_retry()
    test_fosil_guardado_en_la_caja_pc_tambien_se_detecta()
    test_fosil_shiny_prioriza_origin_fosil_sobre_shiny()
    test_captura_salvaje_normal_no_se_confunde_con_fosil()
    test_fosil_shiny_conserva_flag_shiny_desacoplado_de_origin()
    test_fosil_que_se_salta_la_ventana_de_egg_igual_se_detecta()
    test_captura_salvaje_en_otra_ciudad_no_se_confunde_con_fosil()
    test_dos_fosiles_distintos_se_registran_ambos_sin_pendientes()
    test_captura_extra_se_registra_como_capturado_no_especial()
    test_captura_extra_conserva_shiny_si_correspondia()
    test_captura_extra_usa_la_ruta_real_si_esta_libre()
    test_captura_extra_con_ruta_ya_tomada_se_diferencia_con_nickname()
