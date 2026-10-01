"""
API expuesta a JavaScript (pywebview) para la GUI v2 de DexRelay.

Bloque 1 (GUI v2, pywebview): esqueleto -- Bienvenida, Espera,
Conectado, y el shell principal (sidebar + Dashboard placeholder).
Reemplaza en el flujo principal a la GUI Tkinter/ttkbootstrap
(`legacy/gui_tkinter/`, archivada), que se deja sin usarse --
mismo criterio que con los probes viejos (Documento Maestro:
"documenta lo que ya se probó, no estorba, no se borra").

Decisión de diseño: todos los métodos que devuelven datos leen
directo de `Application`/`ApplicationState` en memoria -- no pasan
por el HTTP server (`/api/*`), aunque esos endpoints sigan
existiendo igual para overlays/panel. Motivo: el webview carga la
UI desde un archivo local (file://), y un fetch() cross-origin
hacia http://localhost:8080 quedaría sujeto a la política CORS del
motor embebido (WebView2/GTK) sin que el HTTPServer mande
Access-Control-Allow-Origin -- no vale la pena agregar eso solo
para la GUI cuando el bridge JS<->Python de pywebview ya resuelve
lo mismo sin ser una petición de red real.

Bloque 9.4 (01/10/2026): esta clase quedó solo con el CABLEADO de
servicios (`__init__`); los métodos viven en un módulo por dominio
(api_dashboard, api_pokemon, api_nuzlocke, api_leaders, api_settings,
api_tools, api_hackroom) y se combinan acá por herencia múltiple --
para pywebview sigue siendo UNA sola clase con los mismos métodos.
"""

from __future__ import annotations

from app.core import paths
from app.services.ability_description import AbilityDescriptionCatalog
from app.services.gym_leaders import GymLeaderCatalog
from app.services.item_catalog import ItemCatalog
from app.services.location_catalog import LocationCatalog
from app.services.move_data import MoveDataCatalog
from app.services.move_description import MoveDescriptionCatalog
from app.services.playtime_service import PlaytimeService
from app.services.pokemon_detail_resolver import PokemonDetailResolver
from app.services.pre_evolution_catalog import PreEvolutionCatalog
from app.services.species_catalog import SpeciesCatalog
from app.services.species_extra import SpeciesExtraCatalog
from app.services.type_effectiveness import TypeChartCatalog
from app.gui_web.api_hackroom import HackroomMixin
from app.gui_web.api_dashboard import DashboardMixin
from app.gui_web.api_pokemon import PokemonMixin
from app.gui_web.api_nuzlocke import NuzlockeMixin
from app.gui_web.api_leaders import LeadersMixin
from app.gui_web.api_settings import SettingsMixin
from app.gui_web.api_tools import ToolsMixin


class Api(
    HackroomMixin,
    DashboardMixin,
    PokemonMixin,
    NuzlockeMixin,
    LeadersMixin,
    SettingsMixin,
    ToolsMixin,
):
    """
    Clase expuesta como `window.pywebview.api` en el frontend. Cada
    método público acá es invocable desde JS
    (`pywebview.api.nombre_metodo(...)`, devuelve una Promise).
    """

    def __init__(self, application) -> None:
        self.app = application

        # Página Pokémon (Bloque 3) -- ver
        # app/services/pokemon_detail_resolver.py sobre por qué
        # esto vive acá (solo GUI) y no en Application (no lo usa
        # ningún overlay ni el HTTP server).
        #
        # Bloque 9.2 (01/10/2026): TODOS los servicios de esta clase
        # comparten el único bridge de la aplicación
        # (`application.bridge`, ver Application.__init__) -- antes
        # cada uno arrancaba su propio proceso .NET.
        bridge = self.app.bridge

        self.pokemon_detail_resolver = PokemonDetailResolver(bridge=bridge)

        # Modales de movimiento/habilidad/especie (07/09/2026,
        # roadmap 4.1/4.2) -- instancia PROPIA del bridge, mismo
        # criterio que ya usa PokemonDetailResolver (cada resolver/
        # catálogo de la GUI arranca su propio proceso .NET en vez
        # de compartir uno global; no es lo más liviano posible,
        # pero es el patrón ya establecido en el resto de este
        # archivo, no se cambia acá de paso). Se llama
        # "modal_bridge" (no "move_details_bridge" como al
        # principio) porque ahora también resuelve species_details()
        # para el modal Pokédex de especie, no solo movimientos.
        # MoveDataCatalog/MoveDescriptionCatalog/
        # AbilityDescriptionCatalog/TypeChartCatalog son lecturas de
        # JSON cacheadas, sin costo de mantener vivas.
        # (alias: es el mismo bridge único de la aplicación)
        self.modal_bridge = bridge
        self.move_data_catalog = MoveDataCatalog()
        self.move_description_catalog = MoveDescriptionCatalog()
        self.ability_description_catalog = AbilityDescriptionCatalog()
        self.type_chart_catalog = TypeChartCatalog()
        self.item_catalog = ItemCatalog(bridge=bridge)
        self.species_extra_catalog = SpeciesExtraCatalog()
        self.pre_evolution_catalog = PreEvolutionCatalog()

        # Página Nuzlocke (GUI v2, 04/09/2026) -- mismo criterio
        # que pokemon_detail_resolver: instancias propias, solo
        # para la GUI. species_catalog/location_catalog ya existen
        # también dentro de HTTPServer (para /api/species,
        # /api/locations que usa panels/nuzlocke/) -- se duplica la
        # instancia acá en vez de compartirla para no tener que
        # tocar Application/HTTPServer, mismo patrón que ya se usó
        # con PokemonDetailResolver.
        self.species_catalog = SpeciesCatalog(bridge=bridge)
        self.location_catalog = LocationCatalog(bridge=bridge)
        self.playtime_service = PlaytimeService(bridge=bridge)

        # Pestaña Líderes del Nuzlocke (Fase B, roadmap 3.1/3.2) --
        # dataset estático curado en Fase A, no necesita el bridge
        # PKHeX ni memoria en vivo para el JSON en sí (aunque sí
        # necesita el bridge la primera vez para resolver
        # abilityEs/movesEs, ver gym_leaders.py).
        #
        # Fase E (09/09/2026): soporte para el hack Rising Ruby /
        # Sinking Sapphire (Drayano) -- toggle manual en
        # Configuración (config.json -> hackroom.enabled), decisión
        # del usuario: Azahar no expone si el ROM cargado es el
        # juego base o el hack parcheado, así que no hay forma de
        # detectarlo solo.
        #
        # CORRECCIÓN (09/09/2026, a pedido del usuario: "el cambio
        # al hackroom no se puede hacer sin reiniciar la app"): se
        # instancian los DOS catálogos de una vez acá (vanilla y
        # rrss) en vez de elegir uno solo al arrancar -- cada uno
        # cachea su propio JSON en memoria por separado, así que
        # tenerlos los dos vivos no duplica trabajo real. Cuál se
        # usa se decide en cada pedido (_active_gym_leader_catalog()
        # más abajo), leyendo config.json en el momento -- así el
        # toggle de Configuración surte efecto ni bien se guarda,
        # sin reiniciar DexRelay.
        self.gym_leader_catalog = GymLeaderCatalog(
            bridge=self.modal_bridge
        )
        self.gym_leader_catalog_hackroom = GymLeaderCatalog(
            data_path=paths.path("data", "gym_leaders_rrss.json"),
            bridge=self.modal_bridge,
        )

        # Overrides de evolución del hackroom (09/09/2026, Fase E,
        # segunda parte -- EvolutionChanges.txt vía
        # build_evolution_changes_hackroom.py). species_details()
        # del bridge resuelve evoluciones desde las tablas
        # INTERNAS de PKHeX.Core (las del juego base) -- no tiene
        # forma de saber que el ROM está parcheado, así que estos
        # overrides se aplican a mano encima de lo que devuelve,
        # solo cuando hackroom.enabled está prendido (ver
        # _species_details_with_hackroom_overrides() más abajo,
        # usado en vez de self.modal_bridge.species_details()
        # directo en los 3 lugares que resuelven evoluciones).
        # Agrupado por fromSpeciesId para no recorrer la lista
        # entera en cada consulta.
        self._hackroom_evolution_overrides_by_species = (
            self._load_hackroom_evolution_overrides()
        )

        # Overrides de tipo/habilidad/stats base (09/09/2026, Fase
        # E, segunda parte -- PokemonChanges.txt vía
        # build_pokemon_changes_hackroom.py). Mismo motivo que los
        # de evolución: species_details() no sabe que el ROM está
        # parcheado. Ya viene indexado por species_id (el propio
        # documento usa el número de Pokédex real como clave, no
        # hizo falta resolver nombres).
        self._hackroom_pokemon_changes_by_species = (
            self._load_hackroom_pokemon_changes()
        )

        # Overrides de movimiento (09/09/2026, Fase E, tercera
        # parte -- AttackChanges.txt vía
        # build_attack_changes_hackroom.py). Ya viene indexado por
        # move_id -- el propio script de curación lo resuelve
        # usando MoveDescriptionCatalog, no hace falta resolverlo
        # de nuevo acá.
        self._hackroom_attack_changes_by_move = (
            self._load_hackroom_attack_changes()
        )

        # Tipo de movimiento resuelto vía bridge, por move_id (bug
        # 18/09/2026: movesTypeKeys de los equipos de líder del
        # hackroom salían vacíos porque MOVE_TYPE_KEYS de
        # gym_leaders.py solo cubre los 64 movimientos del juego
        # base). Solo se guardan resultados exitosos -- un fallo del
        # bridge no debe quedar cacheado como "sin tipo".
        self._move_type_key_cache = {}
