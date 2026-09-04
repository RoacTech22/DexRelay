from app.services.pkhex.bridge import PKHeXBridge


class PokemonDetailResolver:
    """
    Resuelve el detalle completo de un Pokémon (tipos, habilidad,
    naturaleza, stats de combate y movimientos) a partir de sus
    datos ya descifrados, usando PKHeX (acción 'pokemon_details'
    del bridge -- ver dotnet/DexRelay.PKHeX/Program.cs).

    GUI v2, Bloque 3 (03/09/2026) -- página Pokémon.

    A DIFERENCIA de LocationResolver, esto NO se cachea por
    nickname. Motivo: el lugar de encuentro/shiny de un Pokémon
    puntual es fijo para siempre una vez resuelto, pero esto no --
    los stats cambian al subir de nivel, los movimientos cambian
    con MTs/reaprendizaje, y la habilidad puede cambiar con una
    cápsula de habilidad. Cachear por nickname mostraría datos
    viejos después de cualquiera de esos eventos.

    Por eso mismo, este resolver NO se llama desde el ciclo
    realtime normal (Runtime.update() / read_party()) -- se pide
    bajo demanda, solo mientras la página Pokémon de la GUI está
    abierta (ver Api.get_pokemon_page_data() en
    app/gui_web/api.py), a un ritmo más lento que el resto del
    Dashboard. Golpear el bridge para los 6 miembros de la party
    en cada ciclo de 200ms del Runtime sería innecesario -- ningún
    overlay ni el Dashboard necesitan este detalle.
    """

    def __init__(self, bridge=None):
        self.bridge = (
            bridge
            if bridge is not None
            else PKHeXBridge()
        )

    def resolve(self, decrypted_box_data):
        """
        Devuelve un dict con genderId/type1/type2/abilityId/
        abilityName/natureId/natureName/natureIncreasedStat/
        natureDecreasedStat/stats/moves. Si no se pudo resolver
        (bridge no disponible, error), devuelve un dict "vacío"
        -- nunca lanza, para no romper la página por esto.
        """

        empty_result = {
            "genderId": None,
            "type1Key": "",
            "type1": "",
            "type2Key": "",
            "type2": "",
            "abilityId": None,
            "abilityName": "",
            "natureId": None,
            "natureName": "",
            "natureIncreasedStat": "",
            "natureDecreasedStat": "",
            "stats": {
                "attack": 0,
                "defense": 0,
                "spAttack": 0,
                "spDefense": 0,
                "speed": 0,
            },
            "moves": [],
        }

        try:
            result = self.bridge.pokemon_details(
                decrypted_box_data
            )

        except Exception as error:
            # Diagnóstico temporal (03/09/2026): el resolver no
            # debe lanzar nunca hacia la GUI, pero tragar el error
            # en silencio hacía imposible saber por qué la página
            # Pokémon no traía datos. Se imprime a consola (mismo
            # canal que ya usa el resto de Application) -- no
            # rompe nada, Ronald corre DexRelay desde terminal.
            print(f"[PokemonDetailResolver] Error al resolver detalle: {error}")
            return empty_result

        stats = result.get("stats") or {}

        return {
            "genderId": result.get("genderId"),
            "type1Key": result.get("type1Key", ""),
            "type1": result.get("type1", ""),
            "type2Key": result.get("type2Key", ""),
            "type2": result.get("type2", ""),
            "abilityId": result.get("abilityId"),
            "abilityName": result.get("abilityName", ""),
            "natureId": result.get("natureId"),
            "natureName": result.get("natureName", ""),
            "natureIncreasedStat": result.get(
                "natureIncreasedStat", ""
            ),
            "natureDecreasedStat": result.get(
                "natureDecreasedStat", ""
            ),
            "stats": {
                "attack": stats.get("attack", 0),
                "defense": stats.get("defense", 0),
                "spAttack": stats.get("spAttack", 0),
                "spDefense": stats.get("spDefense", 0),
                "speed": stats.get("speed", 0),
            },
            "moves": result.get("moves", []),
        }
