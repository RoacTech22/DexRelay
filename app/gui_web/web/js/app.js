/*
 * Controlador de la GUI v2 de DexRelay (Bloque 1).
 *
 * Toda la navegación entre pantallas (Bienvenida -> Espera ->
 * Conectado -> shell principal) vive acá, no en Python -- window.py
 * solo crea la ventana y expone el bridge `Api`
 * (app/gui_web/api.py). Los datos y las acciones que sí necesitan
 * Python (arrancar/detener Application, leer ApplicationState) se
 * piden vía `window.pywebview.api.*`, que pywebview solo deja
 * disponible después del evento `pywebviewready`.
 */

(function () {
  "use strict";

  var WAITING_POLL_MS = 400;
  var MAIN_POLL_MS = 1000;

  // Página Pokémon (Bloque 3, 03/09/2026): a diferencia del resto
  // del Dashboard, esta página pide detalle vía PKHeX bajo demanda
  // (ver Api.get_pokemon_page_data()) -- por eso un ritmo más lento
  // y propio, y solo mientras la página está realmente abierta (se
  // arranca/para al cambiar de pestaña en el sidebar, ver
  // initSidebarNav()), en vez de sumarse al poll de 1s del
  // Dashboard que corre siempre.
  var POKEMON_POLL_MS = 2000;

  var waitingPollTimer = null;
  var mainPollTimer = null;
  var pokemonPollTimer = null;
  var connectedSince = null;
  var uptimeTimer = null;

  // Base URL del HTTPServer (ej. "http://127.0.0.1:8080"),
  // resuelta la primera vez que llega get_dashboard_data() y
  // reutilizada para armar las URLs de los sprites de Pokémon y
  // medallas -- se sirven directo como <img src> contra el
  // servidor que ya está corriendo, no como data URI por el
  // puente JS<->Python (ver comentario de get_dashboard_data() en
  // api.py).
  var spriteBaseUrl = "";

  function api() {
    return window.pywebview.api;
  }

  function showView(id) {
    document.querySelectorAll(".view").forEach(function (el) {
      el.classList.remove("active");
    });
    document.getElementById(id).classList.add("active");
  }

  // ===================== BIENVENIDA =====================

  function initWelcome() {
    api()
      .get_app_version()
      .then(function (version) {
        document.getElementById("footer-version").textContent = version;
        document.getElementById("sidebar-version").textContent = version;
      });

    api()
      .get_logo_data_uri()
      .then(function (dataUri) {
        if (!dataUri) {
          return;
        }
        var img = document.getElementById("logo-img");
        var fallback = document.getElementById("logo-fallback");
        img.src = dataUri;
        img.hidden = false;
        fallback.style.display = "none";

        var sidebarImg = document.getElementById("sidebar-logo-img");
        sidebarImg.src = dataUri;
        sidebarImg.hidden = false;
      });

    api()
      .get_welcome_background_data_uri()
      .then(function (dataUri) {
        if (!dataUri) {
          return;
        }
        document.getElementById("view-welcome").style.setProperty(
          "--welcome-bg", "url('" + dataUri + "')"
        );
      });

    api()
      .get_game_versions()
      .then(renderVersionList);

    api()
      .get_github_url()
      .then(function (url) {
        document.getElementById("link-github").addEventListener(
          "click",
          function (event) {
            event.preventDefault();
            api().open_external(url);
          }
        );
      });

    // Documentación/Discord: sin destino confirmado todavía --
    // no rompen nada, simplemente no navegan a ningún lado por
    // ahora (a completar cuando haya URLs reales).
    ["link-docs", "link-discord"].forEach(function (id) {
      document.getElementById(id).addEventListener("click", function (event) {
        event.preventDefault();
      });
    });

    document
      .getElementById("btn-start")
      .addEventListener("click", onStartClicked);
  }

  function renderVersionList(versions) {
    var container = document.getElementById("version-list");
    container.innerHTML = "";

    versions.forEach(function (game) {
      var card = document.createElement("div");
      card.className = "version-card";
      card.dataset.processName = game.process_name;
      card.dataset.badge = game.badge;

      if (game.background) {
        // Va en la variable --card-bg (consumida por
        // .version-card::before en css/style.css), no en
        // background-image directo -- así el CSS puede espejar
        // solo la imagen sin dar vuelta el texto de la tarjeta.
        card.style.setProperty(
          "--card-bg",
          "linear-gradient(180deg, rgba(10,14,24,0.15) 0%, rgba(10,14,24,0.55) 55%, rgba(10,14,24,0.92) 100%), " +
            "url('" + game.background + "')"
        );
      }

      card.innerHTML =
        '<div class="version-label">' + game.label + "</div>" +
        '<span class="version-badge">' + game.badge + "</span>";

      // Ya no son seleccionables (02/09/2026, ver
      // Api.start_auto()) -- son informativas ("juegos soportados
      // actualmente"), DexRelay detecta solo cuál está abierto.

      container.appendChild(card);
    });
  }

  function onStartClicked() {
    api()
      .start_auto()
      .then(function () {
        showView("view-waiting");
        startWaitingPoll();
      });
  }

  // ===================== ESPERA =====================

  function startWaitingPoll() {
    stopWaitingPoll();
    waitingPollTimer = setInterval(pollWaiting, WAITING_POLL_MS);

    document
      .getElementById("btn-cancel")
      .onclick = onCancelClicked;
  }

  function stopWaitingPoll() {
    if (waitingPollTimer) {
      clearInterval(waitingPollTimer);
      waitingPollTimer = null;
    }
  }

  function pollWaiting() {
    api()
      .get_connection_status()
      .then(function (status) {
        if (status.connected) {
          stopWaitingPoll();
          onConnected(status);
        }
      });
  }

  function onCancelClicked() {
    stopWaitingPoll();
    api()
      .cancel()
      .then(function () {
        showView("view-welcome");
      });
  }

  // ===================== CONECTADO =====================

  function applyConnectionInfo(status) {
    document.getElementById("info-game").textContent = status.game_label || "—";

    var regionEl = document.getElementById("info-region");
    if (status.region) {
      regionEl.textContent = status.region;
      regionEl.classList.remove("muted");
    } else {
      regionEl.textContent = "Desconocido";
      regionEl.classList.add("muted");
    }

    document.getElementById("info-pid").textContent =
      status.process_id != null ? status.process_id : "—";
  }

  function onConnected(status) {
    applyConnectionInfo(status);

    connectedSince = Date.now();
    updateUptime();
    uptimeTimer = setInterval(updateUptime, 1000);

    showView("view-connected");

    document.getElementById("btn-enter").onclick = onEnterClicked;
  }

  function updateUptime() {
    if (!connectedSince) {
      return;
    }

    var totalSeconds = Math.floor((Date.now() - connectedSince) / 1000);
    var hours = Math.floor(totalSeconds / 3600);
    var minutes = Math.floor((totalSeconds % 3600) / 60);
    var seconds = totalSeconds % 60;

    document.getElementById("info-uptime").textContent =
      pad(hours) + ":" + pad(minutes) + ":" + pad(seconds);
  }

  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function onEnterClicked() {
    if (uptimeTimer) {
      clearInterval(uptimeTimer);
      uptimeTimer = null;
    }

    showView("view-main");
    initSidebarNav();
    initDashboardActions();
    startMainPoll();
  }

  // ===================== SHELL PRINCIPAL =====================

  function initSidebarNav() {
    document.querySelectorAll(".nav-item").forEach(function (item) {
      item.addEventListener("click", function () {
        switchToPage(item.dataset.page);
      });
    });
  }

  // Extraído de initSidebarNav() (04/09/2026) para que el botón
  // "Ver todo" del Dashboard pueda llevar directo a la página
  // Pokémon con la misma lógica exacta que un click en el
  // sidebar -- no una versión aparte a medias.
  function switchToPage(page) {
    document.querySelectorAll(".nav-item").forEach(function (el) {
      el.classList.toggle("active", el.dataset.page === page);
    });

    document.querySelectorAll(".page").forEach(function (el) {
      el.classList.remove("active");
    });
    document.getElementById("page-" + page).classList.add("active");

    // Poll propio de la página Pokémon (golpea el bridge
    // PKHeX) -- solo corre mientras esa página está a la
    // vista, no todo el tiempo como el resto del Dashboard.
    if (page === "pokemon") {
      startPokemonPoll();
    } else {
      stopPokemonPoll();
    }
  }

  function startPokemonPoll() {
    stopPokemonPoll();
    pollPokemonPage();
    pokemonPollTimer = setInterval(pollPokemonPage, POKEMON_POLL_MS);
  }

  function stopPokemonPoll() {
    if (pokemonPollTimer) {
      clearInterval(pokemonPollTimer);
      pokemonPollTimer = null;
    }
  }

  function pollPokemonPage() {
    api()
      .get_pokemon_page_data()
      .then(renderPokemonPage);
  }

  function startMainPoll() {
    pollMain();
    mainPollTimer = setInterval(pollMain, MAIN_POLL_MS);
  }

  function pollMain() {
    api()
      .get_dashboard_data()
      .then(function (data) {
        applySidebarStatus(data);
        applyDashboard(data);
      });
  }

  function applySidebarStatus(data) {
    setDot("status-dot-azahar", data.connected);
    setDot("status-dot-reader", data.reader_active);
    setDot("status-dot-server", data.http_running);

    var runningDot = document.getElementById("status-dot-running");
    var runningText = document.getElementById("status-running-text");

    if (data.running) {
      runningDot.classList.add("on");
      runningDot.classList.remove("warn");
      runningText.textContent = "RUNNING";
    } else {
      runningDot.classList.remove("on");
      runningDot.classList.add("warn");
      runningText.textContent = "DETENIDO";
    }
  }

  // ===================== DASHBOARD (Bloque 2) =====================

  var overlaysRendered = false;

  function applyDashboard(data) {
    if (data.http_server) {
      spriteBaseUrl = data.http_server.base_url;
    }

    applyDashboardAlert(data);

    // AZAHAR
    setDashDot("dash-dot-azahar", data.connected);
    setDashStatus("dash-azahar-status", data.connected, "Conectado", "Desconectado");
    setText("dash-azahar-process", data.game_label || "—");
    setText("dash-azahar-region", data.region || "Desconocido");
    setText("dash-azahar-pid", data.process_id != null ? data.process_id : "—");

    // READER
    setDashDot("dash-dot-reader", data.reader_active);
    setDashStatus("dash-reader-status", data.reader_active, "Activo", "Inactivo");
    var teamCount = (data.team || []).filter(function (slot) {
      return slot && !slot.empty;
    }).length;
    setText("dash-reader-team-count", teamCount + " / 6");

    // RUNTIME
    setDashDot("dash-dot-runtime", data.runtime_running);
    setDashStatus("dash-runtime-status", data.runtime_running, "Ejecutándose", "Detenido");
    setText("dash-runtime-uptime", formatUptime(data.uptime_seconds));
    setToggleButton("dash-btn-runtime-toggle", data.runtime_running);

    // HTTP SERVER
    setDashDot("dash-dot-server", data.http_running);
    setDashStatus("dash-server-status", data.http_running, "Activo", "Detenido");
    setToggleButton("dash-btn-server-toggle", data.http_running);
    if (data.http_server) {
      setText(
        "dash-server-address",
        "http://" + data.http_server.host + ":" + data.http_server.port
      );
    }

    renderDashTeam(data.team || [], data.graveyard_nicknames || []);
    renderDashBadges(data.badges);

    if (!overlaysRendered && data.http_server) {
      renderDashOverlays(data.http_server.base_url);
      overlaysRendered = true;
    }

    // Medallas (Bloque 3): reusa exactamente los mismos datos de
    // este poll de 1s (data.badges) -- no hace falta ninguna
    // llamada extra a Python, badges_service.py ya es la fuente de
    // verdad y ya viaja acá en cada ciclo.
    renderMedallasPage(data.badges, data.http_server && data.http_server.base_url);
  }

  function setToggleButton(id, running) {
    var btn = document.getElementById(id);
    if (!btn) {
      return;
    }
    btn.dataset.running = running ? "true" : "false";
    btn.textContent = running ? "Detener" : "Iniciar";
  }

  // Alcanzar el Dashboard implica que en algún momento SÍ hubo
  // conexión (solo se entra acá desde la pantalla "Conectado"),
  // así que `!data.connected` acá siempre es una desconexión real
  // en curso, no un "todavía no conectó" -- pedido explícito del
  // usuario (02/09/2026): avisar si el juego se cerró, y sugerir
  // "Reiniciar" en vez de solo avisar si lo que se detecta es un
  // juego CONOCIDO distinto corriendo (other_game_detected, ver
  // api.py).
  function applyDashboardAlert(data) {
    var alertBox = document.getElementById("dash-alert");
    var alertText = document.getElementById("dash-alert-text");
    var alertBtn = document.getElementById("dash-alert-action");

    if (!alertBox || !alertText || !alertBtn) {
      return;
    }

    if (data.connected) {
      alertBox.hidden = true;
      return;
    }

    alertBox.hidden = false;

    if (data.other_game_detected) {
      alertBox.style.setProperty("--dash-alert-color", "var(--warning)");
      alertText.textContent =
        "Detectamos " + data.other_game_detected +
        " en ejecución en Azahar. Presiona Reiniciar para cargar esta partida.";
      alertBtn.hidden = false;
    } else {
      alertBox.style.setProperty("--dash-alert-color", "var(--danger)");
      alertText.textContent =
        "Se perdió la conexión con el juego. Vuelve a abrirlo en Azahar para seguir viendo datos en tiempo real.";
      alertBtn.hidden = true;
    }
  }

  var dashboardActionsInitialized = false;

  // Botones reales de las tarjetas READER/RUNTIME/HTTP SERVER --
  // se conectan una sola vez (no en cada poll). El estado actual
  // para decidir qué acción disparar cada botón toggle se lee de
  // data-running, que setToggleButton() mantiene al día en cada
  // ciclo de pollMain().
  function initDashboardActions() {
    if (dashboardActionsInitialized) {
      return;
    }
    dashboardActionsInitialized = true;

    var restartBtn = document.getElementById("dash-btn-reader-restart");
    if (restartBtn) {
      restartBtn.addEventListener("click", function () {
        api().restart_reader().then(pollMain);
      });
    }

    var runtimeBtn = document.getElementById("dash-btn-runtime-toggle");
    if (runtimeBtn) {
      runtimeBtn.addEventListener("click", function () {
        var action = runtimeBtn.dataset.running === "true" ? "stop_runtime" : "start_runtime";
        api()[action]().then(pollMain);
      });
    }

    var serverBtn = document.getElementById("dash-btn-server-toggle");
    if (serverBtn) {
      serverBtn.addEventListener("click", function () {
        var action = serverBtn.dataset.running === "true" ? "stop_http_server" : "start_http_server";
        api()[action]().then(pollMain);
      });
    }

    var viewAllBtn = document.getElementById("dash-btn-view-all");
    if (viewAllBtn) {
      viewAllBtn.addEventListener("click", function () {
        switchToPage("pokemon");
      });
    }

    var exitBtn = document.getElementById("btn-exit");
    if (exitBtn) {
      exitBtn.addEventListener("click", onExitClicked);
    }

    var alertActionBtn = document.getElementById("dash-alert-action");
    if (alertActionBtn) {
      alertActionBtn.addEventListener("click", function () {
        api().restart_reader().then(pollMain);
      });
    }
  }

  // "Salir" del sidebar (02/09/2026): misma acción que "Cancelar"
  // en Espera (api().cancel() ya detiene Runtime+HTTPServer) --
  // vuelve a Bienvenida en vez de cerrar la app entera.
  function onExitClicked() {
    if (mainPollTimer) {
      clearInterval(mainPollTimer);
      mainPollTimer = null;
    }

    stopPokemonPoll();

    api()
      .cancel()
      .then(function () {
        showView("view-welcome");
      });
  }

  function setDashDot(id, on) {
    var el = document.getElementById(id);
    if (!el) {
      return;
    }
    el.classList.toggle("on", !!on);
  }

  function setDashStatus(id, on, onText, offText) {
    var el = document.getElementById(id);
    if (!el) {
      return;
    }
    el.textContent = on ? onText : offText;
    el.classList.toggle("on", !!on);
  }

  function setText(id, value) {
    var el = document.getElementById(id);
    if (el) {
      el.textContent = value;
    }
  }

  function formatUptime(seconds) {
    if (seconds == null) {
      return "00:00:00";
    }
    var total = Math.floor(seconds);
    var hours = Math.floor(total / 3600);
    var minutes = Math.floor((total % 3600) / 60);
    var secs = total % 60;
    return pad(hours) + ":" + pad(minutes) + ":" + pad(secs);
  }

  var EMPTY_SLOT_ICON =
    '<svg viewBox="0 0 240 240" xmlns="http://www.w3.org/2000/svg">' +
    '<path fill="currentColor" d="M239.76,112.5C235.87,49.81,183.65,0,120,0S4.13,49.81.24,112.5h-.24v15h.24c3.89,62.69,56.11,112.5,119.76,112.5s115.87-49.81,119.76-112.5h.24v-15h-.24ZM120,15c55.37,0,100.87,43.09,104.74,97.5h-65.55c-3.5-17.88-19.3-31.41-38.19-31.41s-34.68,13.53-38.19,31.41H15.26C19.13,58.09,64.63,15,120,15ZM121,96.09c13.19,0,23.91,10.73,23.91,23.91s-10.73,23.91-23.91,23.91-23.91-10.73-23.91-23.91,10.73-23.91,23.91-23.91ZM120,225c-55.37,0-100.87-43.09-104.74-97.5h67.55c3.5,17.88,19.3,31.41,38.19,31.41s34.68-13.53,38.19-31.41h65.55c-3.86,54.41-49.36,97.5-104.74,97.5Z" />' +
    "</svg>";

  // Estrellita de shiny superpuesta en la esquina del slot (no
  // hay un ícono provisto por el usuario para esto todavía --
  // genérico, en el mismo dorado que ya usan otros indicadores de
  // "especial" en el proyecto).
  var SHINY_BADGE_ICON =
    '<svg class="dash-shiny-badge" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">' +
    '<path fill="currentColor" d="M12 0l2.6 7.9L22.5 8l-6.3 5.1L18.4 21 12 16.3 5.6 21l2.2-7.9L1.5 8l7.9-.1L12 0z" />' +
    "</svg>";

  // Mismos umbrales/colores que overlays/team/app.js (getHpColor
  // inline ahí) -- reutilizados acá para que la barra de HP total
  // del Dashboard hable el mismo idioma visual que el overlay.
  function hpColorFor(percent) {
    if (percent > 50) {
      return "#20C878";
    }
    if (percent > 20) {
      return "#F2C94C";
    }
    return "#E74C3C";
  }

  function renderDashTeam(team, graveyardNicknames) {
    var container = document.getElementById("dash-team");
    if (!container) {
      return;
    }
    container.innerHTML = "";

    var graveyardSet = {};
    (graveyardNicknames || []).forEach(function (nickname) {
      graveyardSet[nickname] = true;
    });

    var totalHp = 0;
    var maxHp = 0;
    var levelSum = 0;
    var filled = 0;

    for (var i = 0; i < 6; i++) {
      var slot = team[i];
      var el = document.createElement("div");
      el.className = "dash-team-slot";

      if (!slot || slot.empty) {
        el.classList.add("empty");
        el.innerHTML = EMPTY_SLOT_ICON;
      } else {
        var spriteUrl = spriteBaseUrl + "/overlay/team/sprites/" + slot.speciesId + ".png";

        // Muerto: HP actual en 0 (estado en vivo) O el nickname ya
        // está en el cementerio del Nuzlocke Tracker (persistente
        // aunque hoy esté sano de nuevo -- mismo criterio que
        // overlays/team/app.js).
        var isDead = (slot.hp || 0) <= 0 || !!graveyardSet[slot.nickname];
        el.classList.toggle("dead", isDead);

        el.innerHTML =
          '<img src="' + spriteUrl + '" alt="' + (slot.species || "") + '" />' +
          '<span class="dash-team-level">Nv. ' + slot.level + "</span>" +
          (slot.shiny ? SHINY_BADGE_ICON : "");

        totalHp += slot.hp || 0;
        maxHp += slot.maxHp || 0;
        levelSum += slot.level || 0;
        filled++;
      }

      container.appendChild(el);
    }

    setText("dash-team-total", filled + " / 6");
    setText("dash-team-avg-level", filled > 0 ? Math.round(levelSum / filled) : "—");
    setText("dash-team-hp", filled > 0 ? totalHp + " / " + maxHp : "—");

    var hpBar = document.getElementById("dash-hp-bar");
    if (hpBar) {
      var hpPercent = maxHp > 0 ? Math.max(0, Math.min(100, (totalHp / maxHp) * 100)) : 0;
      hpBar.style.width = hpPercent + "%";
      hpBar.style.background = hpColorFor(hpPercent);
    }
  }

  function renderDashBadges(badges) {
    var container = document.getElementById("dash-badges");
    if (!container) {
      return;
    }
    container.innerHTML = "";

    var list = (badges && badges.badges) || [false, false, false, false, false, false, false, false];
    var count = (badges && badges.count) || 0;

    setText("dash-badges-count", count + " / 8");

    list.forEach(function (obtained, index) {
      var cell = document.createElement("div");
      cell.className = "dash-badge-cell";

      var img = document.createElement("img");
      img.src = spriteBaseUrl + "/overlay/badges/sprites/" + (index + 1) + ".png";
      if (!obtained) {
        img.className = "pending";
      }

      var label = document.createElement("span");
      label.className = "dash-badge-label" + (obtained ? " on" : "");
      label.textContent = obtained ? "Obtenida" : "Pendiente";

      cell.appendChild(img);
      cell.appendChild(label);
      container.appendChild(cell);
    });
  }

  // ===================== PÁGINA POKÉMON (Bloque 3) =====================

  // Paleta oficial "EP" de 3 tonos por tipo (oscuro/base/claro) e íconos,
  // ambos provistos por el usuario (03/09/2026). "dark" se usa para
  // borde/degradado (le da algo de profundidad en vez de un color plano).
  //
  // CLAVE = nombre del tipo EN INGLÉS (Water, Fire, Electric...), NO en
  // español ni un ID numérico -- historial real de bugs (03/09/2026):
  // 1) matchear por nombre en español solo funcionaba para "Normal" (la
  //    localización es-ES de tipos de PKHeX no es confiable, mismo motivo
  //    por el que existe hoenn_locations_es.py aparte para ubicaciones).
  // 2) una tabla de IDs numéricos armada a mano (0=Normal, 1=Lucha...)
  //    tampoco terminó de coincidir para todos los tipos.
  // Solución: el bridge manda type1Key/type2Key/moves[].typeKey usando
  // el nombre del propio enum MoveType de PKHeX (.ToString()) -- SIEMPRE
  // en inglés por definición del enum, no depende de ningún idioma ni de
  // ninguna tabla escrita a mano (ver Program.cs, TypeKey()).
  var TYPE_ICON_VIEWBOX = "0 0 76.71 76.71";

  var TYPE_INFO = {
    "Normal": { label: "Normal", color: "#9fa19f", colorDark: "#4f504f", colorLight: "#cfd0cf", glyph: "<path d=\"M63.81 26.43c3.12-4.29 2.43-10.33-1.69-13.79-4-3.36-9.82-3.11-13.54.39-3.18-1.21-6.63-1.88-10.23-1.88s-7.05.67-10.23 1.88c-3.71-3.5-9.53-3.74-13.54-.39-4.13 3.46-4.81 9.49-1.69 13.79-2.17 4.05-3.4 8.67-3.4 13.58 0 15.91 12.95 28.86 28.86 28.86s28.86-12.95 28.86-28.86c0-4.91-1.23-9.53-3.4-13.58zM38.35 60.87c-11.5 0-20.86-9.36-20.86-20.86s9.36-20.86 20.86-20.86 20.86 9.36 20.86 20.86-9.36 20.86-20.86 20.86z\" fill=\"#fff\"/>" },
    "Fire": { label: "Fuego", color: "#e62829", colorDark: "#731414", colorLight: "#f29394", glyph: "<path d=\"M55.78 38.1c-5.32-5.15-3.66-9.14-1.21-11.26 0 0-6.53-.79-8.85 4.53-2.33 5.32 2.16 8.06 2.16 8.06s-6.48-2.58-4.66-8.9c1.61-5.56 4.57-8.48 3.24-14.38-1.5-6.67-10.97-9.49-15.55-7.74 3.2 1.08 5.51 4.09 5.51 7.66 0 4.16-3.29 6.92-7.71 11.39-5.11 5.15-10.32 10.97-10.32 20.31 0 10.78 6.65 17.45 14.62 19.87-4.04-1.93-12.45-7.99-11.4-19.65 1.1-12.3 12.89-20.7 12.89-20.7s-2.54 4.26-1.43 11.16c.62 3.88 3.4 8.65 6.05 10.72 3.72 2.91 8.64 5.93 7.93 11.45-.67 5.18-7.55 7.5-11.02 7.71 1.58.26 3.19.37 4.78.32 11.81 0 20.58-8.78 20.58-18.12 0-7.39-3.54-10.43-5.62-12.43z\" fill=\"#fff\"/>" },
    "Water": { label: "Agua", color: "#2980ef", colorDark: "#144077", colorLight: "#94bff7", glyph: "<path d=\"M54 41.57s-3.96-6.86-5.85-9.78c-1.97-3.07-3.82-6.73-5.26-12.61-1.44-5.87-2.22-11.53-4.54-11.53s-3.1 5.65-4.54 11.53c-1.44 5.87-3.29 9.53-5.26 12.61-1.88 2.93-5.85 9.78-5.85 9.78a18.018 18.018 0 00-2.58 9.32c0 10.03 8.2 18.17 18.23 18.17s18.23-8.13 18.23-18.17c0-3.41-.95-6.59-2.58-9.32zM38.35 64.96c-8.18 0-14.61-6.1-14.61-10.5 0-2.91 6.43 2.52 14.61 2.52s14.61-5.43 14.61-2.52c0 4.41-6.43 10.5-14.61 10.5z\" fill=\"#fff\"/>" },
    "Electric": { label: "Eléctrico", color: "#fac000", colorDark: "#7d6000", colorLight: "#fcdf7f", glyph: "<path d=\"M37.97 6.94c2.5 1.14 12.84 6.04 19.84 12.22.31.27.34.75.07 1.06-1.55 1.8-6.66 7.75-12.82 14.99-.27.32-.24.8.07 1.08 1.8 1.59 7.48 6.69 10.91 10.43.28.3.26.77-.04 1.06-2.98 2.87-17.73 17.06-23.45 21.97-.3.26-.76-.02-.67-.41.74-3.02 2.8-11.05 4.99-16.89.12-.31.02-.66-.25-.86-2.15-1.64-11.56-8.86-17.74-14.4a.746.746 0 01-.16-.91c1.36-2.62 7.8-14.72 18.32-29.07.21-.29.6-.4.92-.25z\" fill=\"#fff\"/>" },
    "Grass": { label: "Planta", color: "#3fa129", colorDark: "#1f5014", colorLight: "#9fd094", glyph: "<path d=\"M11.47 66.62H29.1s4.82-44.39 2.33-44.39-19.96 44.39-19.96 44.39zm29.6 0h17.62S67 22.23 64.51 22.23 41.07 66.62 41.07 66.62zm-5.99 0l12.8-25.44s4.66-30.26 2.49-30.26-13.14 26.94-13.14 26.94l-2.16 28.76z\" fill=\"#fff\"/>" },
    "Ice": { label: "Hielo", color: "#3fd8ff", colorDark: "#1f6c7f", colorLight: "#9febff", glyph: "<path fill=\"#fff\" transform=\"rotate(-45 38.354 11.743)\" d=\"M33.44 6.82h9.83v9.83h-9.83z\"/><path fill=\"#fff\" d=\"M11.49 48.24h9.83v9.83h-9.83z\"/><path fill=\"#fff\" transform=\"rotate(-45 38.353 64.974)\" d=\"M33.44 60.05h9.83v9.83h-9.83z\"/><path fill=\"#fff\" d=\"M55.38 18.75v9.77l-17.03-9.83-17.03 9.83v-9.77h-9.83v9.83h9.83v19.6l17.03 9.83 17.03-9.83v-19.6h9.83v-9.83h-9.83zM31.14 34.32v9.62h-5.11v-12.6h.05l10.86-6.27 2.55 4.42-8.36 4.83zm24.24 13.92h9.83v9.83h-9.83z\"/>" },
    "Fighting": { label: "Lucha", color: "#ff8000", colorDark: "#7f4000", colorLight: "#ffbf7f", glyph: "<path d=\"M40.72 34.03h21.8v9.88h-21.8v-9.88zm13.33-22v17.66h8.47V12.03h-8.47zm-4.86 0h-8.47v17.66h8.47V12.03zm-13.2 0h-8.47v23.22h8.47V12.03zm-13.33 0h-8.47v23.22h8.47V12.03zm14.03 31.43h-22.5v12.97l14.41 9.42 33.92-10.46v-7.38H36.69v-4.54z\" fill=\"#fff\"/>" },
    "Poison": { label: "Veneno", color: "#9141cb", colorDark: "#482065", colorLight: "#c8a0e5", glyph: "<path fill=\"#fff\" d=\"M47.7 56.75c-.55-4.68-4.52-8.31-9.35-8.31s-8.8 3.63-9.35 8.31c-11.51.84-19.8 3.18-19.8 5.93 0 3.46 13.05 6.26 29.15 6.26s29.15-2.8 29.15-6.26c0-2.76-8.29-5.09-19.8-5.93z\"/><circle fill=\"#fff\" cx=\"28.31\" cy=\"23.22\" r=\"11.2\"/><circle fill=\"#fff\" cx=\"51.28\" cy=\"37.57\" r=\"6.64\"/>" },
    "Ground": { label: "Tierra", color: "#915121", colorDark: "#482810", colorLight: "#c8a890", glyph: "<path fill=\"#fff\" d=\"M52.29 16.07h8.31v8.31h-8.31zm-24.44 6.49h6.48v6.48h-6.48zM13.55 8.92h10.81v10.81H13.55zm53.89 39.29V46.1L38.35 34.49 9.26 46.1v2.11l29.09 11.6 29.09-11.6z\"/><path fill=\"#fff\" d=\"M67.52 53.52L38.35 65.3 9.19 53.52l-1.47 3.64 30.63 12.38 30.64-12.38-1.47-3.64z\"/>" },
    "Flying": { label: "Volador", color: "#81b9ef", colorDark: "#405c77", colorLight: "#c0dcf7", glyph: "<path d=\"M23.78 27.7c-1.94 4.43-7.5 23.12-8.81 33.15-.67 5.09-1.31 6.86 0 7.25 1.66.5 8.65-10.31 11.14-14.47 0 0 15.92 2.39 24.09-7.79.19-.24-.02-.59-.32-.53-3.22.55-14.81 2.34-19.94.35 0 0 20.89.81 30.38-14.67.13-.2-.08-.46-.3-.38-3.29 1.19-17.5 5.86-26.01 3.66 0 0 13.83-.81 24.28-10.31S69.6 9.66 68.85 8.91c-1.42-1.42-8.65 2.16-14.47 3.99s-13.14 3.99-17.96 4.99-8.81 1.08-12.64 9.81z\" fill=\"#fff\"/>" },
    "Psychic": { label: "Psíquico", color: "#ef4179", colorDark: "#77203c", colorLight: "#f7a0bc", glyph: "<path d=\"M38.35 16.28c.29 0 .59.16.72.48 2.62 6.29 8.79 10.32 15.47 10.32.71 0 1.43-.05 2.15-.14h.11c.63 0 1.01.73.61 1.26-4.58 5.98-4.58 14.34-.02 20.33.4.52.01 1.25-.61 1.25h-.11c-.72-.09-1.43-.14-2.14-.14-6.68 0-12.85 4.02-15.47 10.32-.13.32-.43.48-.72.48s-.59-.16-.72-.48C35 53.67 28.83 49.64 22.15 49.64c-.71 0-1.43.05-2.15.14h-.11c-.63 0-1.01-.73-.61-1.26 4.58-5.98 4.58-14.34.02-20.33-.4-.52-.01-1.25.61-1.25h.11c.72.09 1.43.14 2.14.14 6.68 0 12.85-4.02 15.47-10.32.13-.32.43-.48.72-.48m0-8.7c-3.84 0-7.28 2.29-8.75 5.84-1.23 2.96-4.22 4.96-7.44 4.96-.34 0-.68-.02-1.02-.07-.4-.05-.81-.08-1.22-.08-3.62 0-6.88 2.02-8.49 5.27a9.42 9.42 0 00.95 9.95c2.19 2.88 2.19 6.9 0 9.77a9.417 9.417 0 00-.97 9.96 9.407 9.407 0 008.49 5.28c.41 0 .82-.03 1.23-.08.34-.04.69-.07 1.03-.07 3.22 0 6.21 1.99 7.44 4.96 1.48 3.55 4.91 5.84 8.75 5.84s7.28-2.29 8.75-5.84c1.23-2.96 4.22-4.96 7.44-4.96.34 0 .68.02 1.02.07.4.05.81.08 1.22.08 3.62 0 6.88-2.02 8.49-5.27a9.42 9.42 0 00-.95-9.95c-2.19-2.88-2.19-6.9 0-9.77 2.21-2.89 2.58-6.7.97-9.96a9.407 9.407 0 00-8.49-5.28c-.41 0-.82.03-1.23.08-.34.04-.69.07-1.03.07-3.22 0-6.21-1.99-7.44-4.96a9.443 9.443 0 00-8.75-5.84z\" fill=\"#fff\"/>" },
    "Bug": { label: "Bicho", color: "#91a119", colorDark: "#48500c", colorLight: "#c8d08c", glyph: "<path d=\"M38.35 28.23c8.1 0 15.19-3.44 19.07-8.57-3.88-6.28-10.97-10.49-19.07-10.49s-15.19 4.21-19.07 10.49c3.88 5.13 10.97 8.57 19.07 8.57zm22.84-4.26c-4.56 5.02-11.7 8.47-19.88 9.14l10.93 34.42c8.67-5.52 14.42-15.13 14.42-26.08 0-6.49-2.02-12.5-5.47-17.48zm-45.67 0c4.56 5.02 11.7 8.47 19.88 9.14L24.47 67.53C15.8 62.01 10.05 52.4 10.05 41.45c0-6.49 2.02-12.5 5.47-17.48zm22.83 30.75c1.66 0 3.31-.37 4.83-1.09l-1.3-4.74a6.554 6.554 0 01-7.07 0l-1.3 4.74c1.53.72 3.18 1.09 4.83 1.09zm0 9.14c2.53 0 4.98-.48 7.27-1.36l-1.33-4.85c-1.85.79-3.86 1.21-5.94 1.21s-4.08-.42-5.94-1.21l-1.33 4.85c2.29.88 4.74 1.36 7.27 1.36z\" fill=\"#fff\"/>" },
    "Rock": { label: "Roca", color: "#afa981", colorDark: "#575440", colorLight: "#d7d4c0", glyph: "<path fill=\"#fff\" d=\"M58.71 18l2.67 11.72-14.39-14.39L58.71 18l-8.43-8.43H26.43L9.57 26.43v23.85l8.23 8.23-4.49-19.72L37.52 63 17.8 58.51l8.63 8.63h23.85l8.43-8.43-19.72 4.49L63.2 38.99l-4.49 19.72 8.43-8.43V26.43L58.71 18z\"/>" },
    "Ghost": { label: "Fantasma", color: "#704170", colorDark: "#382038", colorLight: "#b7a0b7", glyph: "<path d=\"M64.73 37.52c-2.45-.58-4.47.48-5.75 1.48.49-2.06.77-4.09.77-6.02 0-11.82-9.58-21.4-21.4-21.4s-21.4 9.58-21.4 21.4c0 1.93.28 3.96.77 6.02-1.28-.99-3.31-2.06-5.75-1.48-3.51.83-6.4 5.88-6.57 10.24-.03.9 1.07 1.36 1.67.69.97-1.09 2.24-2.21 3.12-1.84 2.88 1.22 3.1 6.32 5.87 6.32 2.43 0 4.52-2.43 5.54-3.86 4.66 8.79 11.84 16.06 16.74 16.06s12.07-7.26 16.74-16.06c1.02 1.43 3.11 3.86 5.54 3.86 2.77 0 2.99-5.1 5.87-6.32.88-.37 2.15.74 3.12 1.84.6.67 1.71.21 1.67-.69-.17-4.36-3.06-9.41-6.57-10.24zm-31.59-2.74c-1.78.83-4.48-1.18-6.03-4.5-1.55-3.32-1.35-6.68.43-7.51 1.78-.83 4.48 1.18 6.03 4.5 1.55 3.32 1.36 6.68-.43 7.51zm16.45-4.5c-1.55 3.32-4.25 5.33-6.03 4.5-1.78-.83-1.98-4.2-.43-7.51 1.55-3.32 4.25-5.33 6.03-4.5 1.78.83 1.98 4.2.43 7.51z\" fill=\"#fff\"/>" },
    "Dragon": { label: "Dragón", color: "#5060e1", colorDark: "#283070", colorLight: "#a7aff0", glyph: "<path d=\"M12.39 23.98c-8.41 11.05-7.23 26.81 3.02 36.47 1.09-3.6 3.14-6.95 6.1-9.6a20.91 20.91 0 01-4.04-10.48c-5.13-3.92-7-10.56-5.08-16.4zm51.92 0c1.92 5.84.05 12.48-5.08 16.4-.38 3.88-1.82 7.47-4.04 10.48 2.96 2.65 5.01 5.99 6.1 9.6 10.25-9.65 11.43-25.42 3.02-36.47zm-12.95 1.33c-1.12-7.41-3.63-15.73-4.89-19.64-.22-.68-1.26-.66-1.44.03-1.17 4.28-2.6 11.09-3.24 14.2-1.07-.2-2.29-.32-3.42-.32s-2.35.11-3.42.32c-.64-3.11-2.07-9.91-3.24-14.2-.19-.69-1.22-.72-1.44-.03-1.26 3.91-3.78 12.22-4.89 19.64-2.67 2.99-4.3 6.93-4.3 11.33 0 6.35 3.37 13.85 8.39 18.21l1.38 12.27c0 1.8 3.37 4.41 7.53 4.41s7.53-2.62 7.53-4.41l1.38-12.27c5.02-4.36 8.39-11.86 8.39-18.21 0-4.4-1.63-8.34-4.3-11.33zM29.81 48.82c-2.98-.92-5.06-3.61-5.15-6.73-.12-3.67.07-7.59.07-7.59l9.2 15.41c-1.61-.37-2.97-.74-4.12-1.09zm17.1 0c-1.14.35-2.51.73-4.12 1.09l9.2-15.41s.19 3.92.07 7.59a7.285 7.285 0 01-5.15 6.73z\" fill=\"#fff\"/>" },
    "Dark": { label: "Siniestro", color: "#50413f", colorDark: "#28201f", colorLight: "#a7a09f", glyph: "<path fill=\"#fff\" d=\"M60.1 20.73s-3.25 4.41-10.78 6.74c.84 2.28 1.32 4.93 1.32 7.9 0 10.15-5.5 18.39-12.28 18.39s-12.28-7.27-12.28-18.39c0-2.95.58-5.58 1.52-7.84-7.67-2.32-10.98-6.8-10.98-6.8s-7.54 8.04-6.83 17.19c.42 5.33 3.3 11.6 10.35 17.38 0 0 7.54 6.66 18.22 6.66s18.22-6.66 18.22-6.66c7.05-5.78 9.93-12.04 10.35-17.38.72-9.15-6.83-17.19-6.83-17.19z\"/><path fill=\"#fff\" d=\"M35.54 28.85c-.96 2-1.58 4.89-1.58 7.72 0 5.08 1.97 9.19 4.39 9.19s4.39-4.12 4.39-9.19c0-2.84-.61-5.73-1.58-7.72-.9.04-1.84.05-2.81.02-.97.03-1.91.02-2.81-.02z\"/>" },
    "Steel": { label: "Acero", color: "#60a1b8", colorDark: "#30505c", colorLight: "#afd0db", glyph: "<path fill=\"#fff\" d=\"M41 27.35l9.18 32.02 17.37-12.62-8.03-24.71L41 27.35zM52.3 37.6c-2.52 0-4.56-2.04-4.56-4.56s2.04-4.56 4.56-4.56 4.56 2.04 4.56 4.56-2.04 4.56-4.56 4.56z\"/><path fill=\"#fff\" d=\"M37.9 38.21l-4.29-14.95 24.07-6.9-1.28-3.93H20.3L9.15 46.75l28.75-8.54zM26.03 15.23c1.87 0 3.38 1.51 3.38 3.38s-1.51 3.38-3.38 3.38-3.38-1.51-3.38-3.38 1.51-3.38 3.38-3.38zm13.01 26.95l-25.69 7.63 25 18.17 6.69-4.87-6-20.93z\"/>" },
    "Fairy": { label: "Hada", color: "#ef70ef", colorDark: "#773877", colorLight: "#f7b7f7", glyph: "<path d=\"M66.36 12.08c-2.18-2.18-15.61-3.16-24.65 5.88-1.55 1.55-2.63 3.4-3.25 5.35-.62-1.96-1.7-3.8-3.25-5.35-9.04-9.04-22.47-8.06-24.65-5.88S7.4 27.69 16.44 36.73c1.91 1.91 4.26 3.11 6.73 3.61-5 4.33-5.57 11.18-4.61 12.52 1.02 1.42 8.4 3.21 14.31-.94-.27.79-.53 1.6-.79 2.44-2.47 8.08-3.39 14.96-2.07 15.36 1.33.41 4.41-5.81 6.88-13.89.62-2.03 1.15-3.99 1.56-5.79.41 1.8.94 3.76 1.56 5.79 2.47 8.08 5.55 14.3 6.88 13.89 1.33-.41.4-7.29-2.07-15.36-.26-.84-.52-1.65-.79-2.44 5.91 4.15 13.3 2.36 14.31.94.96-1.34.39-8.18-4.61-12.52 2.47-.5 4.82-1.7 6.73-3.61 9.04-9.04 8.06-22.47 5.88-24.65zm-27.9 28.05c-4.31 0-8.04-2.45-9.9-6.03 5.01-.02 9.15-3.74 9.81-8.57.02-.12.17-.12.18 0 .66 4.83 4.8 8.56 9.81 8.57-1.86 3.58-5.59 6.03-9.9 6.03z\" fill=\"#fff\"/>" },
  };

  function typeInfo(typeKey) {
    return TYPE_INFO[typeKey] || null;
  }

  function typeColor(typeKey) {
    var info = typeInfo(typeKey);
    return info ? info.color : "#4a5568";
  }

  // Ícono de tipo como SVG inline, coloreado con la paleta de arriba --
  // "size" en px. Devuelve string vacío si la clave no se pudo resolver.
  function typeIconSvg(typeKey, size) {
    var info = typeInfo(typeKey);
    if (!info) { return ""; }
    return '<svg class="type-icon" viewBox="' + TYPE_ICON_VIEWBOX + '" width="' + size + '" height="' + size + '" xmlns="http://www.w3.org/2000/svg">' + info.glyph + '</svg>';
  }

  // Variables CSS --type-color/--type-dark para el degradado + borde de
  // la insignia (ver .pokemon-type-badge/.pokemon-move-type en
  // style.css). Devuelve "" si la clave no se pudo resolver.
  function typeStyleVars(typeKey) {
    var info = typeInfo(typeKey);
    if (!info) { return ""; }
    return "--type-color:" + info.color + ";--type-dark:" + info.colorDark + ";--type-light:" + info.colorLight + ";";
  }

  // Íconos de sexo provistos por el usuario (03/09/2026) -- fill="currentColor"
  // para heredar color por CSS (.pokemon-card-gender.male/.female), mismo
  // criterio que los íconos del sidebar.
  var MALE_ICON_SVG = '<svg viewBox="0 0 215.1 216.4" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M169.77,28.89l-33.23,33.23c-33.49-24.9-81.12-22.16-111.5,8.22-33.39,33.39-33.39,87.62,0,121.01,33.39,33.39,87.62,33.39,121.01,0,30.38-30.38,33.12-78,8.22-111.5l32.33-32.33c1.26-1.26,3.41-.37,3.41,1.41v24.83c0,2.21,1.79,4,4,4h17.08c2.21,0,4-1.79,4-4V4C215.1,1.78,213.29-.02,211.07,0l-69.99.65c-2.21.02-3.98,1.83-3.96,4.04l.16,17.08c.02,2.21,1.83,3.98,4.04,3.96l27.03-.25c1.79-.02,2.7,2.15,1.43,3.41ZM42.78,173.62c-23.61-23.61-23.61-61.94,0-85.54,23.61-23.61,61.94-23.61,85.54,0,23.61,23.61,23.61,61.93,0,85.54-23.61,23.61-61.94,23.61-85.54,0"/></svg>';
  var FEMALE_ICON_SVG = '<svg viewBox="0 0 169.6 249.65" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M72.37,168.69v22.29h-29.81c-2.21,0-4,1.79-4,4v16.86c0,2.21,1.79,4,4,4h29.81v29.81c0,2.21,1.79,4,4,4h16.85c2.21,0,4-1.79,4-4v-29.81h29.81c2.21,0,4-1.79,4-4v-16.86c0-2.21-1.79-4-4-4h-29.81v-22.29c41.25-6.07,72.88-41.89,72.37-84.93C169.06,39.34,133.75,2.47,89.39.12,40.51-2.46,0,36.47,0,84.8c0,42.58,31.45,77.87,72.37,83.89ZM84.8,24.85c34.03,0,61.48,28.42,59.88,62.8-1.43,30.7-26.35,55.6-57.04,57.02-34.37,1.59-62.78-25.85-62.78-59.88s26.86-59.94,59.94-59.94"/></svg>';

  // Orden y claves tal como las devuelve
  // pokemon_detail_resolver.py (natureIncreasedStat/
  // natureDecreasedStat) -- deben coincidir exactamente con
  // Ícono provisto por el usuario (04/09/2026) para el título
  // "Estadísticas" de cada tarjeta -- SVG generado por potrace,
  // viewBox y transform originales tal cual (fill cambiado a
  // currentColor para heredar color por CSS).
  var STATS_TITLE_ICON =
    '<svg viewBox="0 0 1280 685" xmlns="http://www.w3.org/2000/svg">' +
    '<g transform="translate(0,685) scale(0.1,-0.1)" fill="currentColor" stroke="none">' +
    '<path d="M2730 3445 l0 -3405 1000 0 1000 0 0 3405 0 3405 -1000 0 -1000 0 0-3405z"/>' +
    '<path d="M10790 3330 l0 -3290 1005 0 1005 0 0 3290 0 3290 -1005 0 -1005 0 0-3290z"/>' +
    '<path d="M5418 2535 l2 -2535 1000 0 1000 0 0 2535 0 2535 -1002 0 -1003 0 3-2535z"/>' +
    '<path d="M0 1590 l0 -1550 1005 0 1005 0 0 1550 0 1550 -1005 0 -1005 0 0-1550z"/>' +
    '<path d="M8100 1495 l0 -1495 1005 0 1005 0 0 1495 0 1495 -1005 0 -1005 0 0-1495z"/>' +
    "</g></svg>";

  // natureStatOrder de Program.cs. "hp" no tiene natureKey (la
  // naturaleza nunca afecta la Salud), y su valor sale de
  // slot.hp/maxHp (dato de party ya existente), no de
  // details.stats -- se maneja aparte al armar statsHtml.
  // Íconos de estadísticas provistos por el usuario (03/09/2026,
  // Atq/Def/Atq.Esp/Def.Esp/Vel) + corazón para Hp (no vino en el pack,
  // glifo estándar). fill="currentColor" -- el color va por CSS
  // (.pokemon-stat-icon), un tono vivo DISTINTO por stat a pedido del
  // usuario, no el mismo color para todos.
  var STAT_ROWS = [
    { key: "attack", label: "Atq", natureKey: "Ataque", color: "#ff5252", iconViewBox: "0 0 207.12 207.12", icon: "<path fill=\"currentColor\" d=\"M198.2.56l-43.64,5.42c-2.67.33-4.95.44-7.02,2.41l-72.44,99.59,8.27,8.18,77.02-77.02c2.45-2.46,5.97-2.09,7.97.31,1.97,2.36,1.77,5.54-.99,7.88l-76.41,76.41,8.18,8.27,99.59-72.44c1.97-2.07,2.08-4.35,2.41-7.02l5.42-43.64c.6-4.84-3.51-8.96-8.35-8.35Z\"/><path fill=\"currentColor\" d=\"M25.31,159.53c11.25,2.72,19.51,11.06,22.29,22.24l15.53-15.47-22.31-22.31-15.51,15.54Z\"/><path fill=\"currentColor\" d=\"M23.83,170.28c-6.38-1.73-13.2.08-17.89,4.75-7.23,7.2-7.26,18.9-.06,26.14,7.19,7.24,18.89,7.28,26.14.09,4.69-4.66,6.55-11.46,4.86-17.86-1.69-6.39-6.66-11.4-13.05-13.12Z\"/><path fill=\"currentColor\" d=\"M120.08,149.96c-1.5,1.43-3.43,2.59-5.32,3.17-4.89,1.5-9.61-.06-13.27-3.33-.97-.87-1.58-1.72-2.5-2.64l-24.06-24.15-16.87-16.71c-3.83-3.79-5.71-8.6-4.04-14.09.53-1.76,1.78-3.73,3.13-5.16,3.23-3.41,3.16-8.12-.2-11.11-3.38-3.01-8.07-2.31-11.01,1.26-1.09,1.32-2.05,2.24-3.01,3.79-6.07,9.84-6.03,22.84,1.39,32.24l12.21,12.52,1.16,1.6-9.3,9.07,22.31,22.31,8.63-8.99c.69-.24,1.1-.06,1.79.62l13.01,12.63c9.02,6.96,21.35,7.24,30.88,1.86,1.99-1.13,3.28-2.24,4.93-3.66,3.5-3,4.28-7.61,1.24-11.03-2.97-3.34-7.7-3.43-11.1-.19Z\"/>" },
    { key: "spAttack", label: "Atq. Esp", natureKey: "AtaqueEsp", color: "#ab47bc", iconViewBox: "0 0 195.83 195.38", icon: "<path fill=\"currentColor\" d=\"M34.73,175.67c-14.35,13.63-24.59,23.49-31.65,18.31-3.41-2.5-4.52-9.6-.56-13.69,9.48-9.78,18.15-19.23,27.57-29.15l35.64-37.54,26.2-42.15,30.52-22.73c8.49-6.32,3.72-20.71,6.96-29.71L147.66,0l47,.91,1.17,47.97c-17.03,10.66-35.46,17.55-54.81,23.69-23.51,7.46-33.82,41.16-68.7,67.4l-37.58,35.69ZM178.75,36.15l-.35-18.92c-7.06-.56-12.31-.64-19.29.03-.19,8.46-2.08,13.87-3.64,22.59l23.27-3.7Z\"/>" },
    { key: "defense", label: "Def", natureKey: "Defensa", color: "#42a5f5", iconViewBox: "0 0 192.93 225.8", icon: "<path fill=\"currentColor\" d=\"M99.1,225.3h-6.14c-7.06-.87-13.72-3.27-19.98-7.22C33.09,194.8,3.41,152.88.5,105.33l.02-69.88c.64-3.21,2.39-4.56,5.2-5.88L91.02,1.13c3.34-.87,7.72-.83,11.05.04l85.15,28.41c2.9,1.33,4.56,2.7,5.21,5.98l-.02,69.85c-2.33,42.62-26.13,80.27-59.94,104.19-9.81,6.94-21.36,14.1-33.37,15.7ZM162.17,57.28c0-2.35-2.17-4.65-3.79-5.2l-19.36-6.59-12.23-4.07-30.33-9.64.02,162.12c5.89-1.02,10.13-3.7,14.86-6.42,18.01-11.84,32.66-28.4,41.6-48.17,5.39-11.93,9.03-24.29,9.07-37.39l.15-44.63Z\"/>" },
    { key: "spDefense", label: "Def. Esp", natureKey: "DefensaEsp", color: "#26c6da", iconViewBox: "0 0 199.94 236.21", icon: "<path fill=\"currentColor\" d=\"M102.28,236.21h-4.61c-17.8-6.1-34.17-15.54-48.66-27.83l-5-4.69c-1.87-1.76-3.31-3.25-5.09-5.12C16.02,174.51,2.48,143.41.01,110.14V36.66c-.01-2.27,2.9-4.7,4.86-5.36L97.75.32c1.85-.62,3.66-.27,5.46.33l91.85,30.65c1.97.66,4.88,3.09,4.88,5.36v73.48c-4.45,58.62-42.56,107.36-97.67,126.08ZM151.1,186.32c19.4-21.06,30.84-47.93,33.14-76.63l.14-65.56-84.41-28.12L15.56,44.13l.14,65.56c2.25,28.69,13.78,55.55,33.12,76.63,2.53,2.98,4.87,5.39,7.91,7.87,12.45,11.55,27.1,20.22,43.28,26.04,19.44-7.03,37.27-18.62,51.08-33.92Z\"/><path fill=\"currentColor\" d=\"M103.76,202.41c-2.9,1.33-4.74,1.28-7.33.1-37.81-17.21-63.55-53.84-65.65-95.45l-.32-6.42v-39.49c0-3.58,2.33-6.72,5.65-7.82l61.48-20.5c1.71-.57,3.09-.56,4.8,0l61.14,20.36c3.46,1.15,5.98,4.15,5.98,7.97v39.88s-.31,5.56-.31,5.56c-2.28,41.64-27.51,78.39-65.42,95.81ZM153.55,106.08c-.56-2.14.33-3.42.33-5.03v-34.65s-46.03-15.31-46.03-15.31l-.23,40.25c-.02,4.2-5.17,6.83-8.76,6.46-3.1-1-6.56-3.04-6.57-6.48l-.2-40.12c-2.69,1.07-5.32,1.72-8.09,2.64l-37.98,12.7v34.97c.53,1.77.59,3.27.4,5.17,2.13,31.2,19.03,59.38,45.68,75.85l.17-32.06c.02-3.99,4.31-6.89,7.88-6.79s7.51,2.92,7.53,6.79l.17,32.06c26.77-16.56,43.75-44.89,45.71-76.45Z\"/>" },
    { key: "speed", label: "Vel", natureKey: "Velocidad", color: "#ffca28", iconViewBox: "0 0 204.4 176.93", icon: "<path fill=\"currentColor\" d=\"M194.5.04L188.89,0c-.66,0-1.12.29-1.18.77-.35-.41-.71-.74-1.06-.74-32.9-.02-69.74,3.25-102.52,13.16-16.69,5.05-33.45,13.24-48.95,22.39-9.95,5.87-22.54,13.33-31.25,21.26-3.78,3.44-4.75,4.37-3.22,10.43,5.49,21.01,9.67,42.4,12.82,64.04.39,2.71.55,5.46.5,8.21l-.23,11.13c-.47,8.4-3.01,16.35-6.31,23.7l.23,2.58h.62c4.93-6,13.77-22.09,15.77-29.43l3.37-12.35c.41-1.51.84-3.11.95-4.62l.9-12.55c.16-1.73.02-12.89.05-16.89l-.04-.21c0-7.86-1.09-12.16-2.53-20.54l14.88-11.75c11.15-8.8,22.83-15.53,35.53-20.46l13.64-5.3c25.28-9.03,50.65-15.87,76.45-22.58,11.65-3.03,21.82-3.78,31.85-12.49,1.93-1.68,3.21-4.35,5.26-5.48V.04h-9.9Z\"/><path fill=\"currentColor\" d=\"M173.61,27.72c-1.78-1.24-5.85-1.25-7.33-.04l-11.45,1.54c-33.23,6.51-79.82,22.8-108.41,43.65-5.24,3.82-10.36,7.68-14.33,13.27-.99,2.15-.07,5.32-.04,8.07l.5,6.4c.04,3.03.08,5.23.36,8.98l26.04-19.29c4.65-3.45,9.07-5.43,14.6-10.03,2.77-2.3,6.92-3,9.41-5.74,2.13-2.34,4.36-2.56,6.76-3.99,11.54-6.84,23.09-12.74,35.27-17.76l15.25-6.29,21.91-10.08c4.5-2.07,12.11-6.05,12.48-7.62.08-.34-.7-1.06-1.02-1.06Z\"/><path fill=\"currentColor\" d=\"M120.45,62.96c-9.37,4.01-18.03,8.33-27.01,13.76-20.37,12.3-39.76,25.87-59,40.52-.37,7.82-1.38,14.84-2.67,22.54l72.44-54.74,3.76-2.86,17.68-12.99c3.2-2.35,6.44-4.18,9.36-7.66-1.9-3.62-9.02-.93-14.55,1.44Z\"/><path fill=\"currentColor\" d=\"M88.71,104.52c-9.15,5.81-17.25,12.65-25.98,19.4l-32.35,25c-1.75,8.14-4.42,15.26-8.71,22.39,2.11.34,3.32-1.65,4.86-3l21.45-18.92,23.31-19.98,16.16-12.89c2.95-2.36,5.67-4.48,8.52-6.98l4.28-3.77c2.68-2.36,6.43-6.29,6.14-8.11-6.7.57-12.17,3.37-17.68,6.86Z\"/>" },
  ];

  function renderPokemonPage(pages) {
    var container = document.getElementById("pokemon-grid");
    if (!container) {
      return;
    }
    container.innerHTML = "";

    (pages || []).forEach(function (slot) {
      var card = document.createElement("div");
      card.className = "pokemon-card";

      if (!slot || slot.empty) {
        card.classList.add("empty");
        card.innerHTML = EMPTY_SLOT_ICON + "<span>Vacío</span>";
        container.appendChild(card);
        return;
      }

      var details = slot.details || {};
      var stats = details.stats || {};
      // Sprites propios de esta página (03/09/2026, provistos por
      // el usuario) -- carpeta separada de
      // overlays/team/sprites/, servida en /sprites/pokemon/ (ver
      // http_server.py). El Dashboard y el Team Overlay siguen
      // usando el set viejo, sin tocar.
      var spriteUrl = spriteBaseUrl + "/sprites/pokemon/" + slot.speciesId + ".png";

      var genderHtml = "";
      if (details.genderId === 0) {
        genderHtml = '<span class="pokemon-card-gender male">' + MALE_ICON_SVG + "</span>";
      } else if (details.genderId === 1) {
        genderHtml = '<span class="pokemon-card-gender female">' + FEMALE_ICON_SVG + "</span>";
      }

      // Texto del tipo: se usa el "label" en español de TYPE_INFO
      // (nuestra propia tabla, confiable) en vez de details.type1/
      // type2 -- bug real (03/09/2026): esos campos vienen de
      // GameInfo.Strings.Types del lado de PKHeX, la misma
      // localización es-ES poco confiable que ya nos había hecho
      // problemas con el color/ícono (a veces devolvía el nombre
      // en inglés). Mismo criterio para el tooltip de movimientos
      // más abajo.
      var typesHtml = "";
      if (details.type1Key) {
        var t1 = typeInfo(details.type1Key);
        typesHtml +=
          '<span class="pokemon-type-badge" style="' + typeStyleVars(details.type1Key) + '">' +
          typeIconSvg(details.type1Key, 14) + "<span>" + (t1 ? t1.label : "") + "</span></span>";
      }
      if (details.type2Key) {
        var t2 = typeInfo(details.type2Key);
        typesHtml +=
          '<span class="pokemon-type-badge" style="' + typeStyleVars(details.type2Key) + '">' +
          typeIconSvg(details.type2Key, 14) + "<span>" + (t2 ? t2.label : "") + "</span></span>";
      }

      // Descripción de habilidad: pendiente a propósito (a
      // resolver más adelante contra una API externa, ver
      // Documento Maestro) -- se muestra solo el nombre por ahora.
      var abilityHtml =
        '<div class="pokemon-card-ability"><div class="ability-name">' +
        (details.abilityName || "—") + "</div></div>";

      // Naturaleza (a pedido del usuario): sin flechas -- el stat
      // que sube/baja se marca coloreando directamente el texto
      // del nombre, en un tono pastel (.stat-name.nature-up/
      // .nature-down en style.css), no con un ícono aparte.
      // Hp va incluido en STAT_ROWS, pero su valor sale de
      // slot.hp/maxHp (dato de party ya existente) en vez de
      // details.stats, y nunca tiene indicador de naturaleza.
      var statsHtml = "";
      STAT_ROWS.forEach(function (stat) {
        var natureClass = "";
        if (stat.natureKey && details.natureIncreasedStat === stat.natureKey) {
          natureClass = " nature-up";
        } else if (stat.natureKey && details.natureDecreasedStat === stat.natureKey) {
          natureClass = " nature-down";
        }

        var value;
        if (stat.key === "hp") {
          value = (slot.hp != null ? slot.hp : "—") + " / " + (slot.maxHp != null ? slot.maxHp : "—");
        } else {
          value = stats[stat.key] != null ? stats[stat.key] : "—";
        }

        statsHtml +=
          '<div class="pokemon-stat-row">' +
          '<span class="stat-name' + natureClass + '">' +
          '<svg class="pokemon-stat-icon" style="color:' + stat.color + '" viewBox="' + stat.iconViewBox + '">' +
          stat.icon + "</svg>" + stat.label + "</span>" +
          '<span class="pokemon-stat-dots"></span>' +
          "<span>" + value + "</span></div>";
      });


      var movesHtml = "";
      var moves = details.moves || [];
      for (var i = 0; i < 4; i++) {
        var move = moves[i];
        if (move) {
          var mt = typeInfo(move.typeKey);
          movesHtml +=
            '<div class="pokemon-move-row"><span class="pokemon-move-name">' + move.name +
            '</span><span class="pokemon-move-type" style="' + typeStyleVars(move.typeKey) +
            '" title="' + (mt ? mt.label : "") + '">' + typeIconSvg(move.typeKey, 20) + "</span></div>";
        } else {
          movesHtml += '<div class="pokemon-move-row empty"><span class="pokemon-move-name">—</span></div>';
        }
      }

      card.innerHTML =
        '<div class="pokemon-card-top">' +
        '<div class="pokemon-card-sprite" style="' + typeStyleVars(details.type1Key) + '">' +
        '<img src="' + spriteUrl + '" alt="" /></div>' +
        '<div class="pokemon-card-info">' +
        '<div class="pokemon-card-name-row"><span>' + (slot.nickname || slot.species || "—") +
        "</span>" + genderHtml + "</div>" +
        '<div class="pokemon-card-species">' + (slot.species || "—") + " · Nv. " + slot.level + "</div>" +
        '<div class="pokemon-card-types">' + typesHtml + "</div>" +
        abilityHtml +
        "</div>" +
        "</div>" +
        '<div class="pokemon-card-bottom">' +
        '<div class="pokemon-card-stats"><div class="dash-card-header-icon-title pokemon-card-stats-title">' + STATS_TITLE_ICON + "<span>Estadísticas</span></div>" +
        statsHtml + "</div>" +
        '<div class="pokemon-card-moves">' + movesHtml + "</div>" +
        "</div>";

      container.appendChild(card);
    });
  }

  // ===================== PÁGINA MEDALLAS (Bloque 3) =====================

  // Nombres tal como están en el mockup (Medallas.png) -- mismo
  // orden que el bitfield de badges_service.py (bit 0 = índice 0).
  var GYM_BADGE_NAMES = [
    "Roca",
    "Cascada",
    "Electro",
    "Llama",
    "Corazón",
    "Alma",
    "Lluvia",
    "Tierra",
  ];

  var medalsActionsInitialized = false;
  var medalsOverlayUrl = "";
  var gymLeaderImagesInitialized = false;

  function renderMedallasPage(badges, baseUrl) {
    var grid = document.getElementById("medals-grid");
    if (!grid) {
      return;
    }

    var list = (badges && badges.badges) || [false, false, false, false, false, false, false, false];
    var count = (badges && badges.count) || 0;
    var value = (badges && badges.value) || 0;

    setText("medals-progress-count", count + " / 8");
    setText("medals-progress-value", "0x" + value.toString(16).toUpperCase().padStart(2, "0"));
    setText("medals-progress-binary", "Valor en memoria");

    setText("medals-stat-obtained", count);
    setText("medals-stat-remaining", 8 - count);
    var percent = Math.round((count / 8) * 100);
    setText("medals-stat-percent", percent + "%");
    var bar = document.getElementById("medals-stat-bar");
    if (bar) {
      bar.style.width = percent + "%";
    }

    grid.innerHTML = "";

    list.forEach(function (obtained, index) {
      var name = GYM_BADGE_NAMES[index] || "Medalla " + (index + 1);

      var card = document.createElement("div");
      card.className = "medals-badge-card";
      card.innerHTML =
        '<span class="medals-badge-number">' + (index + 1) + "</span>" +
        '<img src="' + spriteBaseUrl + "/overlay/badges/sprites/" + (index + 1) + '.png"' +
        (obtained ? "" : ' class="pending"') + " />" +
        '<div class="medals-badge-name">' + name + "</div>" +
        '<div class="medals-badge-status' + (obtained ? " on" : "") + '">' +
        '<span class="dot"></span>' + (obtained ? "Obtenida" : "No obtenida") + "</div>";
      grid.appendChild(card);
    });

    // Retratos de los líderes de gimnasio (04/09/2026): contenido
    // 100% estático (los líderes de Hoenn no cambian), así que se
    // setea el src una sola vez apenas se conoce spriteBaseUrl --
    // no hace falta reconstruir nada en cada poll de 1s.
    if (baseUrl && !gymLeaderImagesInitialized) {
      gymLeaderImagesInitialized = true;

      document.querySelectorAll(".gym-leader-img").forEach(function (img) {
        img.src = baseUrl + "/sprites/gym_leaders/" + img.dataset.leader + ".png";
      });
    }

    if (baseUrl) {
      medalsOverlayUrl = baseUrl + "/overlay/badges";
      setText("medals-overlay-url", medalsOverlayUrl);

      if (!medalsActionsInitialized) {
        medalsActionsInitialized = true;

        var copyBtn = document.getElementById("medals-btn-copy");
        if (copyBtn) {
          copyBtn.addEventListener("click", function () {
            navigator.clipboard.writeText(medalsOverlayUrl);
          });
        }

        var openBtn = document.getElementById("medals-btn-open");
        if (openBtn) {
          openBtn.addEventListener("click", function () {
            api().open_external(medalsOverlayUrl);
          });
        }
      }
    }
  }

  var OVERLAY_DEFS = [
    { name: "Team", path: "/overlay/team" },
    { name: "Badges", path: "/overlay/badges" },
    { name: "Nuzlocke", path: "/overlay/nuzlocke" },
  ];

  function renderDashOverlays(baseUrl) {
    var container = document.getElementById("dash-overlay-list");
    if (!container) {
      return;
    }
    container.innerHTML = "";

    OVERLAY_DEFS.forEach(function (overlay) {
      var url = baseUrl + overlay.path;

      var item = document.createElement("div");
      item.className = "dash-overlay-item";
      item.innerHTML =
        '<span class="dash-overlay-name">' + overlay.name + "</span>" +
        '<span class="dash-overlay-url">' + url + "</span>" +
        '<div class="dash-overlay-actions">' +
        '<button data-action="copy">Copiar</button>' +
        '<button data-action="open">Abrir</button>' +
        "</div>";

      item.querySelector('[data-action="copy"]').addEventListener("click", function () {
        navigator.clipboard.writeText(url);
      });
      item.querySelector('[data-action="open"]').addEventListener("click", function () {
        api().open_external(url);
      });

      container.appendChild(item);
    });
  }

  function setDot(id, on) {
    var el = document.getElementById(id);
    if (on) {
      el.classList.add("on");
    } else {
      el.classList.remove("on");
    }
  }

  // ===================== ARRANQUE =====================

  window.addEventListener("pywebviewready", function () {
    initWelcome();
    resumeIfAlreadyRunning();
  });

  // Si Application ya estaba corriendo y conectada -- típicamente
  // porque el modo desarrollo recargó la página sola al detectar
  // un cambio en web/ (ver app/gui_web/window.py), no porque el
  // usuario haya vuelto a abrir DexRelay -- saltar directo al
  // shell principal en vez de pedir de nuevo la versión del
  // juego. Sin esto, cada guardado de un archivo durante el
  // desarrollo te mandaría de vuelta a Bienvenida.
  function resumeIfAlreadyRunning() {
    api()
      .get_connection_status()
      .then(function (status) {
        if (!status.running || !status.connected) {
          return;
        }

        applyConnectionInfo(status);

        showView("view-main");
        initSidebarNav();
        initDashboardActions();
        startMainPoll();
      });
  }
})();
