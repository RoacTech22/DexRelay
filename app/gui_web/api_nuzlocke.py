"""
Página Nuzlocke: datos de la página y acciones (encuentros, cementerio, reglas, respaldos).

Bloque 9.4 (01/10/2026, guía siguiente versión): extraído de `app/gui_web/api.py`
(que llegó a 2588 líneas) sin cambiar ninguna lógica -- los métodos son los mismos, solo
viven en un módulo por dominio. `Api` (api.py) los combina por herencia múltiple, así que
para pywebview/JS sigue siendo UNA sola clase con los mismos métodos públicos.
"""

from __future__ import annotations


class NuzlockeMixin:
    """Mixin de `Api` (ver el docstring del módulo)."""

    # -----------------------------------------------------------
    # Página Nuzlocke (GUI v2, 04/09/2026) -- reemplaza el
    # placeholder "Próximamente". A diferencia del panel de
    # siempre (panels/nuzlocke/, que sigue existiendo intacto para
    # quien lo abra directo en el navegador), esta página vive
    # dentro de la app con el mismo estilo visual del resto de la
    # GUI -- pedido explícito del usuario de no depender de un
    # panel aparte.
    #
    # Todo lo que lee esto viene de `self.app.nuzlocke_service`
    # directo (la MISMA instancia que usa Runtime cada 200ms y que
    # usaba HTTPServer para panels/nuzlocke/) -- no hay una copia
    # de datos aparte para la GUI, así que un cambio hecho acá se
    # refleja también si alguien tiene el panel viejo abierto al
    # mismo tiempo, y viceversa.
    # -----------------------------------------------------------

    def get_nuzlocke_page_data(self):
        """
        Todo lo que necesita la página Nuzlocke en una sola
        llamada: resumen, equipo actual (mismo dato que ya lee el
        Dashboard, sin memoria nueva), encuentros, pendientes,
        cementerio, reglas del run, y tiempo de juego real (ver
        PlaytimeService -- viene del archivo de guardado en disco,
        no de la memoria en vivo, así que puede tardar en
        reflejar una sesión larga sin guardar).

        El catálogo de especies/ubicaciones NO viaja acá (son
        ~700/~90 entradas, pesado para pedir en cada poll) -- se
        piden aparte, una sola vez, cuando se abre el modal de
        "Nuevo encuentro"/edición (ver get_species_catalog() /
        get_location_catalog()).
        """

        nuzlocke = self.app.state.nuzlocke or {}

        roster = nuzlocke.get("roster", [])
        graveyard = nuzlocke.get("graveyard", [])
        encounters = nuzlocke.get("encounters", [])
        pending = nuzlocke.get("pending_encounters", [])

        alive_count = len(roster)
        dead_count = len(graveyard)
        total_count = alive_count + dead_count

        unique_species = {
            entry.get("species")
            for entry in (roster + graveyard)
            if entry.get("species")
        }

        survival_rate = (
            round((alive_count / total_count) * 100, 1)
            if total_count > 0
            else 0
        )

        stats = {
            "alive": alive_count,
            "dead": dead_count,
            "encountersCount": len(encounters),
            "uniqueSpecies": len(unique_species),
            "captures": total_count,
            "survivalRate": survival_rate,
        }

        # Pestaña Líderes + tarjeta "líder siguiente" de Seguimiento
        # (Fase B, roadmap 3.1/3.2/3.3) -- ver
        # _gym_leaders_with_earned(), compartido con
        # get_leader_team_window_data() (misma cuenta, no
        # duplicada).
        gym_leaders = self._gym_leaders_with_earned()

        # Con las 8 medallas, pasa a la tarjeta del Alto Mando (P4);
        # None si el juego no tiene datos de liga -- el frontend lo
        # trata como "sin líder pendiente" en vez de romper.
        next_leader = self._next_boss(gym_leaders)

        return {
            "team": self.app.state.team or [],
            "roster": roster,
            "graveyard": graveyard,
            "encounters": encounters,
            "pendingEncounters": pending,
            "ruleset": self.app.nuzlocke_service.get_ruleset(),
            "playtime": self.playtime_service.get_playtime(
                self.app.reader.process_name
            ),
            "stats": stats,
            "gymLeaders": gym_leaders,
            "leadersAvailable": self._leaders_available(),
            "nextLeader": next_leader,
        }

    def get_species_catalog(self):
        """Lista completa {id, name} -- se pide una sola vez, se cachea en JS."""

        return self.species_catalog.list_all()

    def get_location_catalog(self):
        """Lista completa {id, name} -- se pide una sola vez, se cachea en JS."""

        return self.location_catalog.list_all()

    def nuzlocke_save_encounter(
        self,
        location,
        nickname,
        species,
        status,
        origin=None,
        shiny=None,
    ):
        """
        "Nuevo encuentro" / editar una fila existente a mano.
        Delega entero en NuzlockeService.save_encounter() -- ver su
        docstring para el significado de cada campo. Devuelve la
        lista de encuentros actualizada, o {"error": str(e)} si la
        validación del servicio falla (estado/origen inválido) --
        el frontend lo muestra tal cual en vez de romper la
        página.
        """

        try:
            return self.app.nuzlocke_service.save_encounter(
                location,
                nickname,
                species,
                status,
                origin=origin,
                shiny=shiny,
            )
        except ValueError as error:
            return {"error": str(error)}

    def nuzlocke_delete_encounter(self, location):
        """
        Botón de borrar una fila. "Inicial" está protegida por el
        propio servicio (ValueError) -- se devuelve como
        {"error": ...} en vez de dejar que la excepción rompa el
        puente JS<->Python.
        """

        try:
            return self.app.nuzlocke_service.delete_encounter(
                location
            )
        except ValueError as error:
            return {"error": str(error)}

    def nuzlocke_discard_pending(self, nickname):
        try:
            return self.app.nuzlocke_service.discard_pending_encounter(
                nickname
            )
        except ValueError as error:
            return {"error": str(error)}

    def nuzlocke_assign_special(self, nickname, origin):
        """
        "¿Pokémon Especial?" -- asigna un origen a una captura
        pendiente (shiny/huevo/intercambio/evento/regalo/fosil/
        captura_extra, ver NuzlockeService.VALID_ORIGINS +
        assign_special_origin()). Devuelve
        {"encounters": [...], "pendingEncounters": [...]}
        actualizados.
        """

        try:
            result = self.app.nuzlocke_service.assign_special_origin(
                nickname, origin
            )
        except ValueError as error:
            return {"error": str(error)}

        return {
            "encounters": result["encounters"],
            "pendingEncounters": result["pending_encounters"],
        }

    def nuzlocke_reset_all(self):
        return self.app.nuzlocke_service.reset_all()

    def nuzlocke_restore_backup(self):
        """
        Bloque 4.2 (23/09/2026): "Restaurar último respaldo" --
        deshace la última operación destructiva (borrar un
        encuentro, "Reiniciar todo"). Devuelve {"error": ...} si no
        había ningún respaldo, para que la GUI pueda avisar en vez
        de fallar en silencio.
        """

        restored = self.app.nuzlocke_service.restore_latest_backup()

        if restored is None:
            return {"error": "No hay ningún respaldo disponible todavía."}

        return restored

    def nuzlocke_get_ruleset(self):
        return self.app.nuzlocke_service.get_ruleset()

    def nuzlocke_save_ruleset(self, ruleset):
        try:
            return self.app.nuzlocke_service.save_ruleset(ruleset)
        except ValueError as error:
            return {"error": str(error)}
