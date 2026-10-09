"""
Pestaña Líderes del Nuzlocke y ventana nativa "Detalle de equipo" de un líder:
resolución de tipos de movimientos/especies de cada líder.

Bloque 9.4 (01/10/2026, guía siguiente versión): extraído de `app/gui_web/api.py`
(que llegó a 2588 líneas) sin cambiar ninguna lógica -- los métodos son los mismos, solo
viven en un módulo por dominio. `Api` (api.py) los combina por herencia múltiple, así que
para pywebview/JS sigue siendo UNA sola clase con los mismos métodos públicos.
"""

from __future__ import annotations

import webview

from app.core import paths


class LeadersMixin:
    """Mixin de `Api` (ver el docstring del módulo)."""

    def _leaders_available(self):
        """
        Bloque 13: False si el juego conectado no tiene datos de
        líderes confirmados (p. ej. X/Y hasta tener su contenido de
        Kalos). Sin juego detectado todavía, se mantiene lo de siempre.
        """

        profile = self.app.reader.profile

        return profile is None or profile.capabilities.has_leader_data

    def _gym_leaders_with_earned(self):
        """
        Los 8 líderes del catálogo (`GymLeaderCatalog.list_all()`)
        con `earned` (bool) agregado, cruzando `leader.order`
        contra el bitfield de medallas actual. `badges` se
        normaliza con el mismo placeholder honesto que
        `get_dashboard_data()` -- todavía puede no haber ninguna
        lectura exitosa en esta sesión (recién conectando).

        Compartido entre `get_nuzlocke_page_data()` (pestaña
        Líderes + tarjeta "líder siguiente") y
        `get_leader_team_window_data()` (ventana nativa de detalle
        de equipo, Fase B 06/09/2026) -- un solo lugar calcula
        `earned`, nadie más lo recalcula por su cuenta.
        """

        if not self._leaders_available():
            return []

        badges = self.app.state.badges

        if not isinstance(badges, dict):
            badges = {"value": 0, "count": 0, "badges": [False] * 8}

        badge_flags = badges.get("badges") or [False] * 8

        gym_leaders = []

        for leader in self._active_gym_leader_catalog().list_all():
            index = (leader.get("order") or 0) - 1

            # P4: solo los líderes de gimnasio tienen medalla. El
            # Alto Mando y el campeón no tienen señal de progreso
            # confirmada, así que nunca figuran como obtenidos.
            earned = (
                leader.get("kind", "gym") == "gym"
                and 0 <= index < len(badge_flags)
                and bool(badge_flags[index])
            )

            # CORRECCIÓN (09/09/2026, a pedido del usuario: revisó
            # el Luxio del equipo de Watson y seguía mostrando solo
            # Electric, no Electric/Dark). data/gym_leaders_rrss.json
            # se armó con "typeKeys": [] a propósito (ver docstring
            # de build_gym_leaders_hackroom.py -- en ese momento
            # todavía no existía el dataset de tipos del hackroom).
            # Ahora que sí existe, se completa acá bajo demanda,
            # reusando el MISMO mecanismo de species_details() +
            # override que ya usa el modal Pokédex -- así que
            # también sirve para el juego base sin tocar nada (si
            # `typeKeys` ya viene poblado a mano, como en
            # gym_leaders.json vanilla, no se pisa ni se vuelve a
            # pedir al bridge).
            team = [
                self._with_resolved_move_type_keys(
                    self._with_resolved_type_keys(member)
                )
                for member in leader.get("team", [])
            ]

            gym_leaders.append({**leader, "team": team, "earned": earned})

        return gym_leaders

    def _next_boss(self, gym_leaders):
        """
        Tarjeta "próximo líder" (P4): el primer líder de gimnasio sin
        medalla; con las 8 obtenidas, pasa al Alto Mando
        (`isLeague`), con el nivel máximo del Pokémon más fuerte del
        primer miembro y los rostros de los 4 miembros + el campeón.
        Sin datos de liga, None (como antes).
        """

        gyms = [
            leader for leader in gym_leaders
            if leader.get("kind", "gym") == "gym"
        ]

        pending = next(
            (leader for leader in gyms if not leader["earned"]),
            None,
        )

        if pending is not None or not gyms:
            return pending

        league = [
            leader for leader in gym_leaders
            if leader.get("kind", "gym") != "gym"
        ]

        if not league:
            return None

        first = league[0]

        return {
            "isLeague": True,
            "order": first["order"],
            "nameEs": "Alto Mando",
            "name": "Elite Four",
            "levelCap": first["levelCap"],
            "members": [
                {
                    "order": member["order"],
                    "nameEs": member.get("nameEs"),
                    "kind": member.get("kind"),
                    "portraitFile": member.get("portraitFile"),
                }
                for member in league
            ],
        }

    def _resolve_move_type_key(self, move_name):
        """
        Tipo (clave en inglés, enum MoveType de PKHeX) de un
        movimiento a partir de su NOMBRE en inglés, o None si no se
        pudo resolver -- nunca inventa uno. Camino: nombre ->
        move_id (MoveDescriptionCatalog) -> bridge.move_details()
        (mismo camino que el modal de movimiento) -> override del
        hackroom (AttackChanges) si está activo.

        "Hidden Power" se deja sin tipo a propósito: PKHeX devuelve
        Normal como tipo base, pero el tipo real depende de los IV
        del Pokémon y el dataset de líderes no los trae -- mostrar
        Normal sería un dato inventado.
        """

        if not move_name or move_name.strip().lower() == "hidden power":
            return None

        move_id = self.move_description_catalog.get_id_by_name(
            move_name
        )

        if move_id is None:
            return None

        type_key = self._move_type_key_cache.get(move_id)

        if type_key is None:
            try:
                response = self.modal_bridge.move_details(move_id)
            except Exception:
                return None

            if not isinstance(response, dict) or "error" in response:
                return None

            type_key = response.get("typeKey") or None

            if type_key is None:
                return None

            self._move_type_key_cache[move_id] = type_key

        if self._hackroom_enabled():
            move_changes = self._hackroom_attack_changes_by_move.get(
                move_id
            )

            if move_changes and "typeKey" in move_changes:
                return move_changes["typeKey"]

        return type_key

    def _with_resolved_move_type_keys(self, member):
        """
        Completa `moveTypeKeys` de un miembro de equipo de líder
        para los movimientos que MOVE_TYPE_KEYS (gym_leaders.py) no
        cubre -- 81 de los 113 movimientos distintos del hackroom
        Rising Ruby/Sinking Sapphire. Los que ya vienen resueltos se
        respetan tal cual, salvo el override de tipo del hackroom.
        """

        moves = member.get("moves") or []
        current = list(member.get("moveTypeKeys") or [])

        # Alinear el largo por si algún dataset trae la lista corta.
        current += [None] * (len(moves) - len(current))

        resolved = []

        for move_name, type_key in zip(moves, current):
            if type_key is None:
                type_key = self._resolve_move_type_key(move_name)
            else:
                type_key = self._apply_hackroom_move_type(
                    move_name, type_key
                )

            resolved.append(type_key)

        return {**member, "moveTypeKeys": resolved}

    def _with_resolved_type_keys(self, member):

        if member.get("typeKeys"):
            return member

        species_id = member.get("speciesId")

        if not species_id:
            return member

        try:
            details = self._species_details_with_hackroom_overrides(
                species_id
            )
        except Exception:
            return member

        if "error" in details:
            return member

        type_keys = [
            key for key in (
                details.get("type1Key"), details.get("type2Key")
            )
            if key
        ]

        return {**member, "typeKeys": type_keys}

    # -----------------------------------------------------------
    # Ventana nativa: detalle de equipo de un líder (Fase B,
    # 06/09/2026, a pedido del usuario -- reemplaza al modal
    # movible original). A diferencia de un modal HTML, esto abre
    # una ventana de sistema operativo real vía
    # `webview.create_window()`: se pueden abrir varias a la vez
    # (una por líder) y cada una se puede mover fuera de los
    # límites de la ventana principal. Vive en su propia página
    # standalone (`leader_team_window.html`/`leader_team_window.js`),
    # que NO comparte el bundle de `app.js` ni el poll de 2s de la
    # página Nuzlocke -- pide su dato una sola vez al abrir.
    # -----------------------------------------------------------

    def open_leader_team_window(self, order):
        """
        Crea la ventana nueva. El título ya viene resuelto acá
        (nombre en español del líder) para que la barra de tareas/
        título de la ventana sea legible desde el primer instante,
        en vez de mostrar un genérico "Cargando..." hasta que la
        página termine de pedir sus propios datos.
        """

        leader = self._resolve_leader_for_window(order)

        if leader:
            leader_name = leader.get("nameEs") or leader.get("name") or "líder"
        else:
            leader_name = "líder"

        title = "Equipo de " + leader_name

        window_path = (
            paths.base_dir() / "app" / "gui_web" / "web" / "leader_team_window.html"
        )

        webview.create_window(
            title,
            url=str(window_path) + "?order=" + str(order),
            js_api=self,
            width=880,
            height=640,
            min_size=(480, 360),
            background_color="#0a0e18",
        )

    def get_leader_team_window_data(self, order):
        """
        Datos para `leader_team_window.html` -- se pide una sola
        vez al abrir la ventana (ver docstring de la sección de
        arriba), no en un poll continuo como el resto de la GUI.
        """

        return self._resolve_leader_for_window(order)

    def _resolve_leader_for_window(self, order):
        try:
            order = int(order)
        except (TypeError, ValueError):
            return None

        for leader in self._gym_leaders_with_earned():
            if leader.get("order") == order:
                return leader

        return None
