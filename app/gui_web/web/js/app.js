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

  // Página Nuzlocke (GUI v2, 04/09/2026) -- mismo criterio que la
  // página Pokémon: poll propio, más lento que el Dashboard, y
  // solo mientras la página está realmente abierta. No golpea el
  // bridge PKHeX directo (get_nuzlocke_page_data() lee
  // state.nuzlocke ya calculado por Runtime), pero sí golpea el
  // archivo de guardado en disco para el tiempo de juego
  // (PlaytimeService ya cachea por mtime, así que esto es barato
  // aunque se repita cada 2s).
  var NUZLOCKE_POLL_MS = 2000;

  // Página Logs (Bloque 5, 06/09/2026) -- mismo criterio de poll
  // propio, solo mientras la página está abierta. Más rápido que
  // Pokémon/Nuzlocke (1s en vez de 2s) porque es un buffer en
  // memoria (log_capture.LogBuffer) -- pedirlo entero no toca
  // disco ni el bridge PKHeX, es barato.
  var LOGS_POLL_MS = 1000;

  var waitingPollTimer = null;
  var mainPollTimer = null;
  var pokemonPollTimer = null;
  var nuzlockePollTimer = null;
  var logsPollTimer = null;
  var logsAllEntries = [];
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
    initTabs();
    initDashboardActions();
    initNuzlockeActions();
    initPokemonPageActions();
    initNuzlockeLeadersTabActions();
    initSpeciesModalActions();
    initOverlaysActions();
    initHerramientasActions();
    initConfiguracionActions();
    initLogsActions();
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

      // Pestañas General/Caja (08/09/2026, roadmap 5.1) no tienen
      // poll propio -- se piden bajo demanda. El evento
      // "dexrelay:tabchange" (ver initTabs()) solo dispara con un
      // CLICK en una pestaña, así que al entrar a la página por
      // primera vez (o volver a ella) con "General" ya activa por
      // defecto, hace falta pedir sus datos acá explícitamente, o
      // quedaría vacía hasta que el usuario haga click en algo.
      var activePokemonTab = document.querySelector(
        '.tabs-bar[data-tabs-group="pokemon"] .tab-btn.active'
      );
      var activeTab = activePokemonTab ? activePokemonTab.dataset.tab : "general";

      if (activeTab === "general") {
        loadGeneralTab();
      } else if (activeTab === "caja") {
        loadBoxTab();
      }
    } else {
      stopPokemonPoll();
    }

    if (page === "nuzlocke") {
      startNuzlockePoll();
    } else {
      stopNuzlockePoll();
    }

    // Configuración no tiene poll -- son valores de config.json,
    // no datos en vivo. Se piden de nuevo cada vez que se entra a
    // la página (barato, una sola llamada) para reflejar un guardado
    // hecho en otra pestaña/instancia, en vez de cachear en JS.
    if (page === "herramientas") {
      loadHerramientasPage();
    }

    if (page === "configuracion") {
      loadConfiguracionPage();
    }

    if (page === "logs") {
      startLogsPoll();
    } else {
      stopLogsPoll();
    }
  }

  // ---------- Componente genérico: pestañas de página (06/09/2026,
  // roadmap Fase A pieza de base) ----------
  //
  // Este componente NO sabe nada de Nuzlocke ni de Pokémon en
  // particular -- primer uso real va a ser la reorganización en
  // pestañas de esas dos páginas (roadmap secciones 3.3 y 5.3),
  // pero se resuelve acá UNA sola vez para que ninguna de las dos
  // termine con su propio sistema de tabs que se comporte distinto.
  //
  // Distinto de switchToPage() de más arriba: eso cambia de PÁGINA
  // completa (sidebar). Esto es un nivel más adentro -- subrutas
  // DENTRO de una página que ya está activa. Por eso no reutiliza
  // ".nav-item"/".page": mismo motivo que llevó a un estilo visual
  // distinto en el CSS (ver style.css, sección homónima) -- que el
  // usuario nunca confunda "cambié de página" con "cambié de
  // pestaña interna" porque se ven iguales.
  //
  // Marcado esperado en el HTML (ver ejemplo real cuando se cablee
  // en Nuzlocke/Pokémon):
  //
  //   <div class="tabs-bar" data-tabs-group="ID">
  //     <button class="tab-btn active" data-tab="uno">Uno</button>
  //     <button class="tab-btn" data-tab="dos">Dos</button>
  //   </div>
  //   <div data-tabs-panels="ID">
  //     <div class="tab-panel active" data-tab-panel="uno">...</div>
  //     <div class="tab-panel" data-tab-panel="dos">...</div>
  //   </div>
  //
  // "ID" (data-tabs-group / data-tabs-panels) tiene que coincidir
  // entre la tira de botones y su contenedor de paneles -- así
  // pueden convivir varios grupos de pestañas independientes en la
  // misma página sin pisarse (ej. Nuzlocke y Pokémon, cada una con
  // el suyo).
  //
  // Al cambiar de pestaña, dispara un evento "dexrelay:tabchange"
  // sobre el contenedor de paneles (detail.group / detail.tab) --
  // así cada página reacciona a su manera (pedir datos bajo
  // demanda, arrancar/parar un poll propio de esa sub-vista) sin
  // que este componente tenga que conocer esa lógica. Mismo
  // espíritu que ya usa switchToPage() con el poll de Pokémon/
  // Nuzlocke, un nivel más adentro.
  function initTabs() {
    document
      .querySelectorAll(".tabs-bar[data-tabs-group]")
      .forEach(function (bar) {
        var group = bar.dataset.tabsGroup;

        bar.querySelectorAll(".tab-btn").forEach(function (btn) {
          btn.addEventListener("click", function () {
            switchTab(group, btn.dataset.tab);
          });
        });
      });
  }

  function switchTab(group, tab) {
    var bar = document.querySelector(
      '.tabs-bar[data-tabs-group="' + group + '"]'
    );
    var panelsContainer = document.querySelector(
      '[data-tabs-panels="' + group + '"]'
    );

    // Silencioso si el grupo no existe -- mismo criterio que el
    // resto de la GUI ante marcado incompleto, no tiene sentido
    // tirar una excepción por un data-tabs-group mal tipeado en
    // vez de simplemente no hacer nada.
    if (!bar || !panelsContainer) {
      return;
    }

    bar.querySelectorAll(".tab-btn").forEach(function (btn) {
      btn.classList.toggle("active", btn.dataset.tab === tab);
    });

    panelsContainer.querySelectorAll(".tab-panel").forEach(function (panel) {
      panel.classList.toggle("active", panel.dataset.tabPanel === tab);
    });

    panelsContainer.dispatchEvent(
      new CustomEvent("dexrelay:tabchange", {
        detail: { group: group, tab: tab },
      })
    );
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

  function startNuzlockePoll() {
    stopNuzlockePoll();
    pollNuzlockePage();
    nuzlockePollTimer = setInterval(pollNuzlockePage, NUZLOCKE_POLL_MS);

    // Carga el catálogo de ubicaciones ya al abrir la página (no
    // recién cuando se abre el modal de "Nuevo encuentro") para
    // que el orden de historia esté listo lo antes posible --
    // vuelve a pintar la tabla apenas termina de cargar, en vez de
    // esperar al próximo poll de 2s para que se vea ordenada.
    ensureNuzlockeCatalogs(function () {
      if (lastNuzlockeData) {
        renderNuzlockeEncounters(lastNuzlockeData.encounters || []);
        renderNuzlockeSummaryEncounters(lastNuzlockeData.encounters || []);
      }
    });
  }

  function stopNuzlockePoll() {
    if (nuzlockePollTimer) {
      clearInterval(nuzlockePollTimer);
      nuzlockePollTimer = null;
    }
  }

  function pollNuzlockePage() {
    api()
      .get_nuzlocke_page_data()
      .then(renderNuzlockePage);
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

    // Overlays (Bloque 4, 05/09/2026): mismo criterio -- reusa
    // data.http_server/data.http_running de este mismo poll, no
    // pide nada nuevo a Python.
    renderOverlaysPage(data);
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

    // Mismo botón que el de la tarjeta HTTP SERVER del Dashboard,
    // pero en la página Overlays (05/09/2026) -- data-running lo
    // mantiene al día setToggleButton() en cada ciclo de
    // pollMain() igual que el de arriba, así que la acción a
    // disparar se decide de la misma forma.
    var ovServerBtn = document.getElementById("ov-btn-server-toggle");
    if (ovServerBtn) {
      ovServerBtn.addEventListener("click", function () {
        var action = ovServerBtn.dataset.running === "true" ? "stop_http_server" : "start_http_server";
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
          '<span class="dash-team-level">Nv. ' + slot.level + genderIconHtml(slot.genderId) + "</span>" +
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

  // Traducción al español de los movimientos que aparecen en los
  // equipos de líderes de gimnasio (06/09/2026, a pedido del
  // usuario -- pendiente heredado de Fase A/Fase B: el dataset
  // curado en data/gym_leaders.json trae los nombres en inglés tal
  // cual los dan pokemondb.net/dittobase.com, las fuentes usadas
  // para curarlo). Cubre SOLO los 64 movimientos que realmente
  // aparecen en los 8 equipos -- no la lista completa de
  // movimientos del juego, que son casi 1000 y no hace falta acá.
  // Nombre oficial España (mismo criterio que ya se usó para los
  // nombres de los líderes -- Alana/Petra/etc. son la localización
  // España, no la de Hispanoamérica, que a veces difiere). Si
  // algún nombre no coincide con lo que se ve en el juego real,
  // avisar para corregirlo -- mismo criterio que la corrección de
  // Alana/Petra intercambiadas.
  var MOVE_NAME_ES = {
    "Aerial Ace": "Golpe Aéreo",
    "Air Cutter": "Corte Aéreo",
    "Amnesia": "Amnesia",
    "Aqua Ring": "Anillo Hídrico",
    "Arm Thrust": "Golpe Brazo",
    "Attract": "Atracción",
    "Aurora Beam": "Rayo Aurora",
    "Body Slam": "Golpe Cuerpo",
    "Bulk Up": "Corpulencia",
    "Calm Mind": "Paz Mental",
    "Charge": "Carga",
    "Chip Away": "Erosión",
    "Cotton Guard": "Guardia Algodón",
    "Curse": "Maldición",
    "Defense Curl": "Rizo Defensa",
    "Disarming Voice": "Voz Cautivadora",
    "Double Team": "Doble Equipo",
    "Dragon Breath": "Dragoaliento",
    "Draining Kiss": "Beso Drenaje",
    "Earth Power": "Tierra Viva",
    "Earthquake": "Terremoto",
    "Encore": "Otra Vez",
    "Endeavor": "Esfuerzo",
    "Feint Attack": "Finta",
    "Fury Swipes": "Golpes Furia",
    "Harden": "Fortaleza",
    "Horn Drill": "Perforador",
    "Hydro Pump": "Hidrobomba",
    "Hypnosis": "Hipnosis",
    "Ice Beam": "Rayo Hielo",
    "Karate Chop": "Golpe Kárate",
    "Knock Off": "Desarme",
    "Lava Plume": "Humareda",
    "Leer": "Malicioso",
    "Light Screen": "Pantalla de Luz",
    "Magnet Bomb": "Bomba Magnética",
    "Mud Sport": "Chapoteo Lodo",
    "Overheat": "Sofoco",
    "Protect": "Protección",
    "Psychic": "Psíquico",
    "Quick Attack": "Ataque Rápido",
    "Rain Dance": "Danza Lluvia",
    "Recover": "Recuperación",
    "Retaliate": "Represalia",
    "Rock Slide": "Avalancha",
    "Rock Throw": "Lanzarrocas",
    "Rock Tomb": "Tumba Rocas",
    "Rollout": "Rodar",
    "Roost": "Respiro",
    "Sand Attack": "Ataque Arena",
    "Seismic Toss": "Sísmico",
    "Solar Beam": "Rayo Solar",
    "Steel Wing": "Ala de Acero",
    "Sunny Day": "Día Soleado",
    "Supersonic": "Supersónico",
    "Swagger": "Contoneo",
    "Sweet Kiss": "Beso Dulce",
    "Tackle": "Placaje",
    "Thunder Wave": "Onda Trueno",
    "Volt Switch": "Cambio de Voltios",
    "Water Pulse": "Hidropulso",
    "Waterfall": "Cascada",
    "Yawn": "Bostezo",
    "Zen Headbutt": "Golpe Cabeza Zen",
  };

  function translateMoveName(name) {
    return MOVE_NAME_ES[name] || name;
  }

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
  // Ícono "Pokédex" (07/09/2026, roadmap 4.2 -- botón nuevo en
  // cada tarjeta que abre el modal de detalle de especie) -- ícono
  // estándar de "info" (círculo con "i"), genérico, no un dibujo a
  // medida como el resto de los íconos de esta página.
  // Ícono "Pokédex" (07/09/2026, roadmap 4.2 -- botón nuevo en
  // cada tarjeta que abre el modal de detalle de especie) --
  // reemplazado (08/09/2026, a pedido del usuario) por el ícono
  // real que subió (Pokedex.svg), en vez del genérico de "info".
  // Ícono Pokédex (08/09/2026, reemplazo a pedido del usuario --
  // SVG provisto por Ronald, viewBox original 0 0 150.42 226.12).
  var POKEDEX_ICON_SVG = '<svg viewBox="0 0 150.42 226.12" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M136.63,0H13.79C6.19,0,0,5.9,0,13.16v199.81c0,7.26,6.19,13.16,13.79,13.16h102.7V55.78h-18.23c-5.05,0-9.93,2.01-13.4,5.52l-22.86,23.18c-1.73,1.75-4.17,2.76-6.7,2.76H9.2V13.16c0-2.42,2.06-4.39,4.6-4.39h122.84c2.53,0,4.6,1.97,4.6,4.39v42.62h-15.54v170.35h10.94c7.61,0,13.79-5.9,13.79-13.16V13.16c0-7.26-6.19-13.16-13.79-13.16ZM99.5,194.47c2.56,0,4.63,1.96,4.63,4.39s-2.07,4.39-4.63,4.39h-58.21c-2.56,0-4.63-1.96-4.63-4.39s2.07-4.39,4.63-4.39h58.21ZM21.52,134.17c0-3.7,4.51-5.74,7.51-3.4l11.38,8.88c2.25,1.76,2.25,5.03,0,6.79l-11.38,8.88c-3,2.34-7.51.31-7.51-3.39v-17.76Z"/><path fill="currentColor" d="M19.51,42.14c0,12.35,10.54,22.41,23.49,22.41s23.49-10.05,23.49-22.41-10.54-22.41-23.49-22.41-23.49,10.05-23.49,22.41ZM57.29,42.14c0,7.52-6.41,13.64-14.29,13.64s-14.29-6.12-14.29-13.64,6.41-13.63,14.29-13.63,14.29,6.12,14.29,13.63Z"/><path fill="currentColor" d="M83.93,28.41c0,2.37,2.01,4.29,4.5,4.29s4.5-1.92,4.5-4.29-2.01-4.29-4.5-4.29-4.5,1.92-4.5,4.29Z"/><path fill="currentColor" d="M101.02,28.41c0,2.37,2.01,4.29,4.5,4.29s4.5-1.92,4.5-4.29-2.01-4.29-4.5-4.29-4.5,1.92-4.5,4.29Z"/><path fill="currentColor" d="M121.71,24.12c-2.48,0-4.5,1.92-4.5,4.29s2.01,4.29,4.5,4.29,4.5-1.92,4.5-4.29-2.01-4.29-4.5-4.29Z"/></svg>';

  var MALE_ICON_SVG = '<svg viewBox="0 0 215.1 216.4" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M169.77,28.89l-33.23,33.23c-33.49-24.9-81.12-22.16-111.5,8.22-33.39,33.39-33.39,87.62,0,121.01,33.39,33.39,87.62,33.39,121.01,0,30.38-30.38,33.12-78,8.22-111.5l32.33-32.33c1.26-1.26,3.41-.37,3.41,1.41v24.83c0,2.21,1.79,4,4,4h17.08c2.21,0,4-1.79,4-4V4C215.1,1.78,213.29-.02,211.07,0l-69.99.65c-2.21.02-3.98,1.83-3.96,4.04l.16,17.08c.02,2.21,1.83,3.98,4.04,3.96l27.03-.25c1.79-.02,2.7,2.15,1.43,3.41ZM42.78,173.62c-23.61-23.61-23.61-61.94,0-85.54,23.61-23.61,61.94-23.61,85.54,0,23.61,23.61,23.61,61.93,0,85.54-23.61,23.61-61.94,23.61-85.54,0"/></svg>';
  var FEMALE_ICON_SVG = '<svg viewBox="0 0 169.6 249.65" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M72.37,168.69v22.29h-29.81c-2.21,0-4,1.79-4,4v16.86c0,2.21,1.79,4,4,4h29.81v29.81c0,2.21,1.79,4,4,4h16.85c2.21,0,4-1.79,4-4v-29.81h29.81c2.21,0,4-1.79,4-4v-16.86c0-2.21-1.79-4-4-4h-29.81v-22.29c41.25-6.07,72.88-41.89,72.37-84.93C169.06,39.34,133.75,2.47,89.39.12,40.51-2.46,0,36.47,0,84.8c0,42.58,31.45,77.87,72.37,83.89ZM84.8,24.85c34.03,0,61.48,28.42,59.88,62.8-1.43,30.7-26.35,55.6-57.04,57.02-34.37,1.59-62.78-25.85-62.78-59.88s26.86-59.94,59.94-59.94"/></svg>';

  // Ícono de respaldo (08/09/2026, reportado por el usuario: las
  // celdas de caja "donde no hay pokemon" mostraban el ícono roto
  // típico de imagen no encontrada) -- se muestra en vez del
  // sprite cuando la imagen falla al cargar (ver pkmMiniMonHtml()
  // más abajo). El filtro real ya se corrigió del lado del backend
  // (get_boxes_overview()/get_box_page_data() en api.py descartan
  // los slots fantasma con speciesId 0 antes de mandarlos), esto
  // es la red de contención en el frontend para cualquier otro
  // caso de sprite faltante (ej. un speciesId real sin archivo
  // .png todavía).
  var POKEBALL_FALLBACK_ICON_SVG = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2" fill="none"/><line x1="3" y1="12" x2="21" y2="12" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="3" fill="var(--bg-elevated-2)" stroke="currentColor" stroke-width="2"/></svg>';

  // Ícono de género reutilizable (05/09/2026, a pedido del
  // usuario: "al lado del nombre de especie" en TODA la app, no
  // solo en la página Pokémon donde ya existía). genderId: 0 =
  // macho, 1 = hembra, 2 = sin género, null/undefined = no
  // resuelto (bridge caído o dato viejo sin este campo) -- en
  // estos dos últimos casos no se muestra nada, en vez de un
  // ícono roto o "sin género" por defecto.
  function genderIconHtml(genderId) {
    if (genderId === 0) {
      return '<span class="gender-icon-inline male">' + MALE_ICON_SVG + "</span>";
    }
    if (genderId === 1) {
      return '<span class="gender-icon-inline female">' + FEMALE_ICON_SVG + "</span>";
    }
    return "";
  }

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
    // Bug real corregido (05/09/2026, reportado por el usuario):
    // el comentario de renderPokemonPage ya decía "Hp va incluido
    // en STAT_ROWS", pero la fila nunca se había agregado acá --
    // el manejo especial de abajo (stat.key === "hp", que lee
    // slot.hp/maxHp en vez de details.stats) estaba listo desde
    // antes y simplemente no tenía ninguna fila que lo disparara.
    // Mismo ícono de corazón que ya usa el Dashboard para "HP
    // total" (index.html), para no inventar un ícono nuevo.
    { key: "hp", label: "HP", natureKey: null, color: "#ff5c7a", iconViewBox: "0 0 255.84 224.93", icon: "<path fill=\"currentColor\" d=\"M235.18,20.88C221.78,7.48,204.05.16,185.12.16s-36.72,7.38-50.12,20.77l-7,7-7.11-7.11C107.5,7.43,89.66,0,70.73,0S34.06,7.38,20.72,20.72C7.32,34.12-.05,51.91,0,70.84,0,89.76,7.43,107.5,20.83,120.9l101.86,101.86c1.41,1.41,3.31,2.17,5.15,2.17s3.74-.71,5.15-2.12l102.08-101.7c13.4-13.4,20.77-31.19,20.77-50.12.05-18.93-7.27-36.72-20.66-50.12Z\"/>" },
    { key: "attack", label: "ATK", natureKey: "Ataque", color: "#ff5252", iconViewBox: "0 0 207.12 207.12", icon: "<path fill=\"currentColor\" d=\"M198.2.56l-43.64,5.42c-2.67.33-4.95.44-7.02,2.41l-72.44,99.59,8.27,8.18,77.02-77.02c2.45-2.46,5.97-2.09,7.97.31,1.97,2.36,1.77,5.54-.99,7.88l-76.41,76.41,8.18,8.27,99.59-72.44c1.97-2.07,2.08-4.35,2.41-7.02l5.42-43.64c.6-4.84-3.51-8.96-8.35-8.35Z\"/><path fill=\"currentColor\" d=\"M25.31,159.53c11.25,2.72,19.51,11.06,22.29,22.24l15.53-15.47-22.31-22.31-15.51,15.54Z\"/><path fill=\"currentColor\" d=\"M23.83,170.28c-6.38-1.73-13.2.08-17.89,4.75-7.23,7.2-7.26,18.9-.06,26.14,7.19,7.24,18.89,7.28,26.14.09,4.69-4.66,6.55-11.46,4.86-17.86-1.69-6.39-6.66-11.4-13.05-13.12Z\"/><path fill=\"currentColor\" d=\"M120.08,149.96c-1.5,1.43-3.43,2.59-5.32,3.17-4.89,1.5-9.61-.06-13.27-3.33-.97-.87-1.58-1.72-2.5-2.64l-24.06-24.15-16.87-16.71c-3.83-3.79-5.71-8.6-4.04-14.09.53-1.76,1.78-3.73,3.13-5.16,3.23-3.41,3.16-8.12-.2-11.11-3.38-3.01-8.07-2.31-11.01,1.26-1.09,1.32-2.05,2.24-3.01,3.79-6.07,9.84-6.03,22.84,1.39,32.24l12.21,12.52,1.16,1.6-9.3,9.07,22.31,22.31,8.63-8.99c.69-.24,1.1-.06,1.79.62l13.01,12.63c9.02,6.96,21.35,7.24,30.88,1.86,1.99-1.13,3.28-2.24,4.93-3.66,3.5-3,4.28-7.61,1.24-11.03-2.97-3.34-7.7-3.43-11.1-.19Z\"/>" },
    { key: "spAttack", label: "SPA", natureKey: "AtaqueEsp", color: "#ab47bc", iconViewBox: "0 0 195.83 195.38", icon: "<path fill=\"currentColor\" d=\"M34.73,175.67c-14.35,13.63-24.59,23.49-31.65,18.31-3.41-2.5-4.52-9.6-.56-13.69,9.48-9.78,18.15-19.23,27.57-29.15l35.64-37.54,26.2-42.15,30.52-22.73c8.49-6.32,3.72-20.71,6.96-29.71L147.66,0l47,.91,1.17,47.97c-17.03,10.66-35.46,17.55-54.81,23.69-23.51,7.46-33.82,41.16-68.7,67.4l-37.58,35.69ZM178.75,36.15l-.35-18.92c-7.06-.56-12.31-.64-19.29.03-.19,8.46-2.08,13.87-3.64,22.59l23.27-3.7Z\"/>" },
    { key: "defense", label: "DEF", natureKey: "Defensa", color: "#42a5f5", iconViewBox: "0 0 192.93 225.8", icon: "<path fill=\"currentColor\" d=\"M99.1,225.3h-6.14c-7.06-.87-13.72-3.27-19.98-7.22C33.09,194.8,3.41,152.88.5,105.33l.02-69.88c.64-3.21,2.39-4.56,5.2-5.88L91.02,1.13c3.34-.87,7.72-.83,11.05.04l85.15,28.41c2.9,1.33,4.56,2.7,5.21,5.98l-.02,69.85c-2.33,42.62-26.13,80.27-59.94,104.19-9.81,6.94-21.36,14.1-33.37,15.7ZM162.17,57.28c0-2.35-2.17-4.65-3.79-5.2l-19.36-6.59-12.23-4.07-30.33-9.64.02,162.12c5.89-1.02,10.13-3.7,14.86-6.42,18.01-11.84,32.66-28.4,41.6-48.17,5.39-11.93,9.03-24.29,9.07-37.39l.15-44.63Z\"/>" },
    { key: "spDefense", label: "SPD", natureKey: "DefensaEsp", color: "#26c6da", iconViewBox: "0 0 199.94 236.21", icon: "<path fill=\"currentColor\" d=\"M102.28,236.21h-4.61c-17.8-6.1-34.17-15.54-48.66-27.83l-5-4.69c-1.87-1.76-3.31-3.25-5.09-5.12C16.02,174.51,2.48,143.41.01,110.14V36.66c-.01-2.27,2.9-4.7,4.86-5.36L97.75.32c1.85-.62,3.66-.27,5.46.33l91.85,30.65c1.97.66,4.88,3.09,4.88,5.36v73.48c-4.45,58.62-42.56,107.36-97.67,126.08ZM151.1,186.32c19.4-21.06,30.84-47.93,33.14-76.63l.14-65.56-84.41-28.12L15.56,44.13l.14,65.56c2.25,28.69,13.78,55.55,33.12,76.63,2.53,2.98,4.87,5.39,7.91,7.87,12.45,11.55,27.1,20.22,43.28,26.04,19.44-7.03,37.27-18.62,51.08-33.92Z\"/><path fill=\"currentColor\" d=\"M103.76,202.41c-2.9,1.33-4.74,1.28-7.33.1-37.81-17.21-63.55-53.84-65.65-95.45l-.32-6.42v-39.49c0-3.58,2.33-6.72,5.65-7.82l61.48-20.5c1.71-.57,3.09-.56,4.8,0l61.14,20.36c3.46,1.15,5.98,4.15,5.98,7.97v39.88s-.31,5.56-.31,5.56c-2.28,41.64-27.51,78.39-65.42,95.81ZM153.55,106.08c-.56-2.14.33-3.42.33-5.03v-34.65s-46.03-15.31-46.03-15.31l-.23,40.25c-.02,4.2-5.17,6.83-8.76,6.46-3.1-1-6.56-3.04-6.57-6.48l-.2-40.12c-2.69,1.07-5.32,1.72-8.09,2.64l-37.98,12.7v34.97c.53,1.77.59,3.27.4,5.17,2.13,31.2,19.03,59.38,45.68,75.85l.17-32.06c.02-3.99,4.31-6.89,7.88-6.79s7.51,2.92,7.53,6.79l.17,32.06c26.77-16.56,43.75-44.89,45.71-76.45Z\"/>" },
    { key: "speed", label: "SPE", natureKey: "Velocidad", color: "#ffca28", iconViewBox: "0 0 204.4 176.93", icon: "<path fill=\"currentColor\" d=\"M194.5.04L188.89,0c-.66,0-1.12.29-1.18.77-.35-.41-.71-.74-1.06-.74-32.9-.02-69.74,3.25-102.52,13.16-16.69,5.05-33.45,13.24-48.95,22.39-9.95,5.87-22.54,13.33-31.25,21.26-3.78,3.44-4.75,4.37-3.22,10.43,5.49,21.01,9.67,42.4,12.82,64.04.39,2.71.55,5.46.5,8.21l-.23,11.13c-.47,8.4-3.01,16.35-6.31,23.7l.23,2.58h.62c4.93-6,13.77-22.09,15.77-29.43l3.37-12.35c.41-1.51.84-3.11.95-4.62l.9-12.55c.16-1.73.02-12.89.05-16.89l-.04-.21c0-7.86-1.09-12.16-2.53-20.54l14.88-11.75c11.15-8.8,22.83-15.53,35.53-20.46l13.64-5.3c25.28-9.03,50.65-15.87,76.45-22.58,11.65-3.03,21.82-3.78,31.85-12.49,1.93-1.68,3.21-4.35,5.26-5.48V.04h-9.9Z\"/><path fill=\"currentColor\" d=\"M173.61,27.72c-1.78-1.24-5.85-1.25-7.33-.04l-11.45,1.54c-33.23,6.51-79.82,22.8-108.41,43.65-5.24,3.82-10.36,7.68-14.33,13.27-.99,2.15-.07,5.32-.04,8.07l.5,6.4c.04,3.03.08,5.23.36,8.98l26.04-19.29c4.65-3.45,9.07-5.43,14.6-10.03,2.77-2.3,6.92-3,9.41-5.74,2.13-2.34,4.36-2.56,6.76-3.99,11.54-6.84,23.09-12.74,35.27-17.76l15.25-6.29,21.91-10.08c4.5-2.07,12.11-6.05,12.48-7.62.08-.34-.7-1.06-1.02-1.06Z\"/><path fill=\"currentColor\" d=\"M120.45,62.96c-9.37,4.01-18.03,8.33-27.01,13.76-20.37,12.3-39.76,25.87-59,40.52-.37,7.82-1.38,14.84-2.67,22.54l72.44-54.74,3.76-2.86,17.68-12.99c3.2-2.35,6.44-4.18,9.36-7.66-1.9-3.62-9.02-.93-14.55,1.44Z\"/><path fill=\"currentColor\" d=\"M88.71,104.52c-9.15,5.81-17.25,12.65-25.98,19.4l-32.35,25c-1.75,8.14-4.42,15.26-8.71,22.39,2.11.34,3.32-1.65,4.86-3l21.45-18.92,23.31-19.98,16.16-12.89c2.95-2.36,5.67-4.48,8.52-6.98l4.28-3.77c2.68-2.36,6.43-6.29,6.14-8.11-6.7.57-12.17,3.37-17.68,6.86Z\"/>" },
  ];

  function renderPokemonPage(pages) {
    renderPokemonGrid("pokemon-grid", pages, { showEmptySlots: true });
  }

  // Extraído de renderPokemonPage() (08/09/2026, roadmap 5.3 --
  // pestaña "Caja") para reusar exactamente la misma tarjeta
  // (sprite/tipos/habilidad/stats/movimientos, con los mismos
  // modales clickeables) tanto en la grilla de Equipo (6 slots
  // fijos, incluye vacíos) como en la de Caja (hasta 30 slots,
  // pero solo se listan los ocupados -- ver `showEmptySlots`).
  // Estado de tarjetas desplegadas, persistido por afuera del
  // render (08/09/2026, bug real corregido: "a lo que despliego la
  // segunda fila se cierra enseguida, solo sucede en la pestaña de
  // equipo"). Causa: el poll de 2s de Equipo llama a
  // renderPokemonGrid() de nuevo cada vez (container.innerHTML =
  // ""), reconstruyendo las tarjetas desde cero y perdiendo
  // cualquier clase "expanded" que tuvieran -- no pasaba en Caja
  // porque esa pestaña no tiene poll de fondo, se pide una sola vez
  // al entrar. Clave por containerId+slot (no alcanza con el slot
  // solo: Equipo y Caja son grids distintos con su propia
  // numeración de slot).
  var expandedCardSlots = {};

  function isCardExpanded(containerId, slot) {
    return !!(expandedCardSlots[containerId] && expandedCardSlots[containerId][slot]);
  }

  function setCardExpanded(containerId, slot, expanded) {
    if (!expandedCardSlots[containerId]) {
      expandedCardSlots[containerId] = {};
    }
    if (expanded) {
      expandedCardSlots[containerId][slot] = true;
    } else {
      delete expandedCardSlots[containerId][slot];
    }
  }

  function renderPokemonGrid(containerId, pages, options) {
    var container = document.getElementById(containerId);
    if (!container) {
      return;
    }

    var showEmptySlots = !!(options && options.showEmptySlots);

    container.innerHTML = "";

    (pages || []).forEach(function (slot) {
      if ((!slot || slot.empty) && !showEmptySlots) {
        return;
      }

      var card = document.createElement("div");
      card.className = "pokemon-card";

      if (!slot || slot.empty) {
        card.classList.add("empty");
        card.innerHTML = EMPTY_SLOT_ICON + "<span>Vacío</span>";
        container.appendChild(card);
        return;
      }

      card.dataset.slot = slot.slot;
      if (isCardExpanded(containerId, slot.slot)) {
        card.classList.add("expanded");
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

      // Descripción de habilidad: ahora sí se pide (roadmap
      // 07/09/2026, sección 4.1) -- clickeable, abre el modal de
      // habilidad (ver initPokemonPageActions()). Se agrega
      // data-ability-id/data-ability-name solo si la habilidad se
      // pudo resolver (abilityId != null) -- un guión "—" sin
      // habilidad conocida no debería ser clickeable.
      var abilityAttrs = "";
      if (details.abilityId != null) {
        abilityAttrs =
          ' data-ability-id="' + details.abilityId + '"' +
          ' data-ability-name="' + escapeHtml(details.abilityName || "") + '"';
      }
      var abilityHtml =
        '<div class="pokemon-card-ability"><div class="ability-name"' +
        abilityAttrs + ">" +
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
          // Caja PC: bug real corregido (08/09/2026, reportado por
          // el usuario -- "el hp no está apareciendo" en la
          // pestaña Caja). Un Pokémon guardado no tiene HP actual/
          // máximo real en memoria (slot.hp/slot.maxHp vienen 0 --
          // el juego lo recalcula recién al retirarlo, ver
          // Pokemon6.hp()/.max_hp() en structures.py, que leen un
          // offset que solo existe en el bloque extra de la
          // party). El bridge SÍ puede calcular el HP máximo real
          // a partir de IVs/EVs/naturaleza/nivel (Program.cs,
          // stats.hpMax = pk.Stat_HPMax) -- se usa ese como
          // respaldo cuando slot.maxHp no vino, mostrando el
          // actual igual al máximo (un Pokémon guardado siempre
          // "sale con la vida llena", misma convención que ya
          // aplica el propio bridge).
          if (slot.maxHp) {
            value = (slot.hp != null ? slot.hp : "—") + " / " + slot.maxHp;
          } else if (stats.hpMax) {
            value = stats.hpMax + " / " + stats.hpMax;
          } else {
            value = "—";
          }
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
            '<div class="pokemon-move-row" data-move-id="' + move.id + '">' +
            '<span class="pokemon-move-name">' + move.name +
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
        '<div class="pokemon-card-species" data-species-id="' + slot.speciesId + '" title="Ver Pokédex de la especie">' +
        (slot.species || "—") + " · Nv. " + slot.level +
        "</div>" +
        '<div class="pokemon-card-types">' + typesHtml + "</div>" +
        abilityHtml +
        "</div>" +
        "</div>" +
        // Desplegable (08/09/2026, a pedido del usuario): la
        // "segunda fila" (stats + movimientos) arranca oculta --
        // ver .pokemon-card-bottom en style.css -- y este botón
        // alterna la clase "expanded" en la tarjeta (ver
        // initPokemonPageActions()). Sprite/nickname/especie/
        // habilidad (arriba) quedan siempre visibles.
        '<button class="pokemon-card-toggle" type="button">' +
        "<span>Ver detalle</span>" +
        '<svg class="pokemon-card-toggle-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">' +
        '<polyline points="6,9 12,15 18,9" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
        "</button>" +
        '<div class="pokemon-card-bottom">' +
        '<div class="pokemon-card-stats"><div class="dash-card-header-icon-title pokemon-card-stats-title">' + STATS_TITLE_ICON + "<span>Estadísticas</span></div>" +
        statsHtml + "</div>" +
        '<div class="pokemon-card-moves">' + movesHtml + "</div>" +
        "</div>";

      container.appendChild(card);
    });
  }

  // ===================== MODALES DE MOVIMIENTO / HABILIDAD (roadmap 07/09/2026, sección 4.1) =====================

  // Nombre legible en español por categoryKey (physical/special/status,
  // ver merge_move_details() en move_data.py -- viene en inglés porque
  // es la clave estable del enum de PKHeX, mismo criterio que typeKey).
  var MOVE_CATEGORY_LABELS = {
    Physical: "Físico",
    Special: "Especial",
    Status: "Estado",
  };

  function initPokemonPageActions() {
    // Delegación de eventos (07/09/2026): el grid se reconstruye
    // entero en cada poll de 2s (ver renderPokemonPage(),
    // container.innerHTML = ""), así que atar un listener por fila
    // en cada render implicaría rearmarlos todo el tiempo. Un solo
    // listener acá, sobre el contenedor que SÍ persiste entre
    // renders, alcanza -- mismo patrón que ya usa
    // initNuzlockeActions() para los botones "cerrar modal".
    //
    // Extendido (08/09/2026, pestaña "Caja") a #pkm-box-grid --
    // misma tarjeta, mismos modales (Pokédex/movimiento/habilidad),
    // un solo handler compartido en vez de reimplementarlo.
    function handlePokemonGridClick(event) {
      // Toggle de detalle (08/09/2026) -- alterna la clase
      // "expanded" en la tarjeta contenedora, que muestra/oculta
      // .pokemon-card-bottom vía CSS (ver style.css).
      var toggleBtn = event.target.closest(".pokemon-card-toggle");
      if (toggleBtn) {
        var card = toggleBtn.closest(".pokemon-card");
        if (card) {
          var nowExpanded = card.classList.toggle("expanded");
          setCardExpanded(event.currentTarget.id, card.dataset.slot, nowExpanded);
        }
        return;
      }

      // Modal Pokédex (08/09/2026, a pedido del usuario: "quitale
      // el icono de la pokedex y que lo abra la especie") -- ya no
      // hay un botón dedicado, se abre haciendo click en el texto
      // de la especie.
      var speciesEl = event.target.closest(".pokemon-card-species[data-species-id]");
      if (speciesEl) {
        openSpeciesModal(Number(speciesEl.dataset.speciesId));
        return;
      }

      var moveRow = event.target.closest(".pokemon-move-row[data-move-id]");
      if (moveRow) {
        openMoveModal(Number(moveRow.dataset.moveId));
        return;
      }

      var abilityEl = event.target.closest(".ability-name[data-ability-id]");
      if (abilityEl) {
        openAbilityModal(
          Number(abilityEl.dataset.abilityId),
          abilityEl.dataset.abilityName || ""
        );
      }
    }

    ["pokemon-grid", "pkm-box-grid"].forEach(function (id) {
      var grid = document.getElementById(id);
      if (grid) {
        grid.addEventListener("click", handlePokemonGridClick);
      }
    });

    // Íconos mini de "Equipo actual"/"Cajas PC" en la pestaña
    // General (08/09/2026) -- abren el mismo modal Pokédex que el
    // botón dedicado de las otras pestañas.
    ["pkm-general-team", "pkm-general-boxes"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) {
        el.addEventListener("click", function (event) {
          var mon = event.target.closest(".pkm-mini-mon[data-species-id]");
          if (mon) {
            openSpeciesModal(Number(mon.dataset.speciesId));
          }
        });
      }
    });

    initPokemonTabsBehavior();
  }

  // ===================== PESTAÑA "GENERAL" (roadmap 08/09/2026, sección 5.1/5.2) =====================

  function pkmMiniMonHtml(mon) {
    var spriteUrl = spriteBaseUrl + "/sprites/pokemon/" + mon.speciesId + ".png";
    var title = (mon.nickname || mon.species || "—") + " · Nv. " + mon.level;
    return (
      '<div class="pkm-mini-mon" data-species-id="' + mon.speciesId + '" title="' + escapeHtml(title) + '">' +
      '<img src="' + spriteUrl + '" alt="" onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'flex\';" />' +
      '<span class="pkm-mini-mon-fallback">' + POKEBALL_FALLBACK_ICON_SVG + "</span>" +
      "<span>Nv. " + mon.level + "</span>" +
      "</div>"
    );
  }

  // Celda de "no hay Pokémon acá" (08/09/2026, a pedido del
  // usuario -- reemplaza el texto plano "Vacía" que había antes)
  // -- mismo ícono de pokebola que ya usa pkmMiniMonHtml() como
  // respaldo cuando un sprite no carga, reusado acá a propósito
  // (una sola fuente visual para "no hay nada que mostrar", no dos
  // convenciones distintas conviviendo).
  function pkmEmptyBoxCellHtml() {
    return (
      '<div class="pkm-mini-mon-empty" title="Vacía">' +
      POKEBALL_FALLBACK_ICON_SVG +
      "</div>"
    );
  }

  function renderGeneralTab(data) {
    var teamContainer = document.getElementById("pkm-general-team");
    var boxesContainer = document.getElementById("pkm-general-boxes");
    if (!teamContainer || !boxesContainer) {
      return;
    }

    // Sin conexión con el emulador (08/09/2026): NUNCA se muestra
    // "Vacía"/"Equipo vacío" en este caso -- eso afirmaría un
    // estado del juego que en realidad no se pudo leer, mismo
    // criterio de "nunca mostrar un valor sin fuente confirmada"
    // que el resto del proyecto (ver Documento Maestro).
    if (data && data.connected === false) {
      var disconnectedMsg = '<span class="pkm-modal-stat-label">Sin conexión con el emulador.</span>';
      teamContainer.innerHTML = disconnectedMsg;
      boxesContainer.innerHTML = disconnectedMsg;
      return;
    }

    var team = (data && data.team) || [];
    var occupiedTeam = team.filter(function (entry) {
      return entry && !entry.empty;
    });

    teamContainer.innerHTML = occupiedTeam.length
      ? occupiedTeam.map(pkmMiniMonHtml).join("")
      : pkmEmptyBoxCellHtml();

    var boxes = (data && data.boxes) || [];

    boxesContainer.innerHTML = boxes.map(function (box) {
      var mons = box.pokemon || [];
      var monsHtml = mons.length
        ? mons.map(pkmMiniMonHtml).join("")
        : pkmEmptyBoxCellHtml();

      return (
        '<div class="pkm-general-box-row">' +
        '<span class="pkm-general-box-label">Caja ' + box.boxIndex + "</span>" +
        '<div class="pkm-general-box-mons">' + monsHtml + "</div>" +
        "</div>"
      );
    }).join("");
  }

  function loadGeneralTab() {
    api()
      .get_boxes_overview()
      .then(renderGeneralTab);
  }

  // ===================== PESTAÑA "CAJA" (roadmap 08/09/2026, sección 5.1/5.3) =====================

  var BOX_COUNT = 31;
  var currentBoxIndex = 1;
  var boxSelectorBuilt = false;

  function buildBoxSelector() {
    var selector = document.getElementById("pkm-box-selector");
    if (!selector || boxSelectorBuilt) {
      return;
    }

    var html = "";
    for (var boxIndex = 1; boxIndex <= BOX_COUNT; boxIndex++) {
      html +=
        '<button class="pkm-box-selector-btn' + (boxIndex === currentBoxIndex ? " active" : "") +
        '" data-box-index="' + boxIndex + '">' + boxIndex + "</button>";
    }
    selector.innerHTML = html;
    boxSelectorBuilt = true;

    selector.addEventListener("click", function (event) {
      var btn = event.target.closest(".pkm-box-selector-btn[data-box-index]");
      if (!btn) {
        return;
      }

      var boxIndex = Number(btn.dataset.boxIndex);
      if (boxIndex === currentBoxIndex) {
        return;
      }

      currentBoxIndex = boxIndex;

      selector.querySelectorAll(".pkm-box-selector-btn").forEach(function (el) {
        el.classList.toggle("active", Number(el.dataset.boxIndex) === boxIndex);
      });

      loadBoxTab();
    });
  }

  function renderBoxTab(data) {
    var title = document.getElementById("pkm-box-title");
    if (title) {
      title.textContent = "Caja " + ((data && data.boxIndex) || currentBoxIndex);
    }

    var grid = document.getElementById("pkm-box-grid");

    // Sin conexión (08/09/2026): mismo criterio que renderGeneralTab()
    // -- nunca decir "vacía" cuando en realidad no se pudo leer.
    if (data && data.connected === false) {
      renderPokemonGrid("pkm-box-grid", [], { showEmptySlots: false });
      if (grid) {
        grid.innerHTML = '<span class="pkm-modal-stat-label">Sin conexión con el emulador.</span>';
      }
      return;
    }

    var slots = (data && data.slots) || [];
    var occupiedCount = slots.filter(function (slot) {
      return slot && !slot.empty;
    }).length;

    if (grid && !occupiedCount) {
      renderPokemonGrid("pkm-box-grid", [], { showEmptySlots: false });
      grid.innerHTML = '<span class="pkm-modal-stat-label">Esta caja está vacía.</span>';
      return;
    }

    renderPokemonGrid("pkm-box-grid", slots, { showEmptySlots: false });
  }

  function loadBoxTab() {
    api()
      .get_box_page_data(currentBoxIndex)
      .then(renderBoxTab);
  }

  // ===================== Reacción a cambio de pestaña (General/Equipo/Caja) =====================

  function initPokemonTabsBehavior() {
    var panelsContainer = document.querySelector('[data-tabs-panels="pokemon"]');
    if (!panelsContainer) {
      return;
    }

    buildBoxSelector();

    panelsContainer.addEventListener("dexrelay:tabchange", function (event) {
      if (event.detail.tab === "general") {
        loadGeneralTab();
      } else if (event.detail.tab === "caja") {
        loadBoxTab();
      }
    });
  }

  // Pestaña Líderes del Nuzlocke Tracker (07/09/2026, a pedido del
  // usuario: "también faltó la pestaña de líderes") -- mismos
  // modales, pero acá los datos salen de data/gym_leaders.json
  // (curado a mano, solo nombre en inglés, sin id) igual que la
  // ventana de detalle de equipo -- por eso usa las variantes
  // "ByName" (ver más abajo), no las de id directo.
  function initNuzlockeLeadersTabActions() {
    var container = document.getElementById("nz-leaders-list");
    if (!container) {
      return;
    }

    container.addEventListener("click", function (event) {
      // Pokédex de especie (08/09/2026, a pedido del usuario:
      // "extiende el modal de pokedex a los pokes de los lideres
      // de gimnasio") -- mismo modal que ya usan las tarjetas de
      // Equipo/Caja de la página Pokémon (openSpeciesModal() más
      // abajo), acá clickeando el nombre de la especie.
      var speciesEl = event.target.closest(".nz-leader-mon-name[data-species-id]");
      if (speciesEl) {
        openSpeciesModal(Number(speciesEl.dataset.speciesId));
        return;
      }

      var moveEl = event.target.closest(".nz-leader-mon-move-line[data-move-name]");
      if (moveEl) {
        openMoveModalByName(moveEl.dataset.moveName);
        return;
      }

      var abilityEl = event.target.closest(".nz-leader-mon-ability[data-ability-name]");
      if (abilityEl) {
        openAbilityModalByName(abilityEl.dataset.abilityName, abilityEl.textContent);
      }
    });
  }

  function openMoveModal(moveId) {
    _openMoveModalCommon(api().get_move_modal_data(moveId));
  }

  function openMoveModalByName(name) {
    _openMoveModalCommon(api().get_move_modal_data_by_name(name));
  }

  function _openMoveModalCommon(dataPromise) {
    document.getElementById("pkm-move-modal-title").textContent = "Cargando...";
    document.getElementById("pkm-move-modal-type").textContent = "";
    document.getElementById("pkm-move-modal-type").style.cssText = "";
    document.getElementById("pkm-move-modal-category").textContent = "";
    document.getElementById("pkm-move-modal-power").textContent = "—";
    document.getElementById("pkm-move-modal-accuracy").textContent = "—";
    document.getElementById("pkm-move-modal-pp").textContent = "—";
    document.getElementById("pkm-move-modal-description").textContent = "";

    openModal("pkm-modal-move");

    dataPromise.then(function (data) {
      if (!data || data.error) {
        document.getElementById("pkm-move-modal-title").textContent = "No se pudo cargar";
        document.getElementById("pkm-move-modal-description").textContent =
          "No se pudo obtener el detalle de este movimiento.";
        return;
      }

      document.getElementById("pkm-move-modal-title").textContent = data.name || "—";

      var typeEl = document.getElementById("pkm-move-modal-type");
      var ti = typeInfo(data.typeKey);
      typeEl.style.cssText = typeStyleVars(data.typeKey);
      typeEl.innerHTML = typeIconSvg(data.typeKey, 14) + "<span>" + (ti ? ti.label : data.type || "") + "</span>";

      document.getElementById("pkm-move-modal-category").textContent =
        MOVE_CATEGORY_LABELS[data.categoryKey] || data.categoryKey || "—";

      document.getElementById("pkm-move-modal-power").textContent =
        data.power != null ? data.power : "—";
      document.getElementById("pkm-move-modal-accuracy").textContent =
        data.accuracy != null ? data.accuracy + "%" : "—";
      document.getElementById("pkm-move-modal-pp").textContent =
        data.basePP != null ? data.basePP : "—";

      document.getElementById("pkm-move-modal-description").textContent =
        data.descriptionEs || "Descripción no disponible.";
    });
  }

  function openAbilityModal(abilityId, abilityName) {
    _openAbilityModalCommon(
      api().get_ability_modal_data(abilityId),
      abilityName
    );
  }

  function openAbilityModalByName(name, displayedText) {
    _openAbilityModalCommon(
      api().get_ability_modal_data_by_name(name),
      displayedText
    );
  }

  function _openAbilityModalCommon(dataPromise, titleText) {
    document.getElementById("pkm-ability-modal-title").textContent = titleText || "Cargando...";
    document.getElementById("pkm-ability-modal-description").textContent = "";

    openModal("pkm-modal-ability");

    dataPromise.then(function (data) {
      document.getElementById("pkm-ability-modal-description").textContent =
        (data && data.descriptionEs) || "Descripción no disponible.";
    });
  }

  // ===================== MODAL POKÉDEX DE ESPECIE (roadmap 4.2, 07/09/2026) =====================

  // Multiplicador -> color de fondo del badge (rojo más fuerte
  // cuanto más débil, azul más fuerte cuanto más resiste, gris
  // para inmunidad) -- puramente informativo, no hay un color
  // "oficial" del juego para esto.
  function formatMultiplier(multiplier) {
    if (multiplier === 0) { return "0×"; }
    if (multiplier === 0.25) { return "¼×"; }
    if (multiplier === 0.5) { return "½×"; }
    return multiplier + "×";
  }

  function renderTypeEffectGrid(containerId, entries) {
    var container = document.getElementById(containerId);

    if (!entries || !entries.length) {
      container.innerHTML = '<span class="pkm-modal-stat-label">Ninguna</span>';
      return;
    }

    container.innerHTML = entries.map(function (entry) {
      var info = typeInfo(entry.typeKey);
      return (
        '<span class="pokemon-type-badge" style="' + typeStyleVars(entry.typeKey) + '">' +
        typeIconSvg(entry.typeKey, 14) +
        "<span>" + (info ? info.label : entry.typeKey) + " " + formatMultiplier(entry.multiplier) + "</span>" +
        "</span>"
      );
    }).join("");
  }

  // Colores de barra por stat -- distintos de los ya usados en
  // STAT_ROWS (esos son para la tarjeta de un Pokémon individual
  // de la página Pokémon) porque acá el contexto es "stats BASE de
  // la especie" en el modal Pokédex, mismo criterio de paleta que
  // el mockup (HP verde, ATK rojo, DEF ámbar, SPA azul, SPD
  // violeta, SPE cian).
  var BASE_STAT_BAR_COLORS = {
    hp: "#22c55e",
    attack: "#ef4444",
    defense: "#f59e0b",
    spAttack: "#3b82f6",
    spDefense: "#a855f7",
    speed: "#22d3ee",
  };

  // Máximo teórico de un stat base en el juego (255, ej. la
  // Velocidad de Blissey en Salud/HP) -- se usa solo para la
  // proporción visual de la barra, no es un dato que límite nada.
  var BASE_STAT_BAR_MAX = 255;

  function openSpeciesModal(speciesId) {
    document.getElementById("pkm-species-modal-name").textContent = "Cargando...";
    document.getElementById("pkm-species-modal-dexnum").textContent = "";
    document.getElementById("pkm-species-modal-artwork").src = "";
    document.getElementById("pkm-species-modal-gender").innerHTML = "";
    document.getElementById("pkm-species-modal-types").innerHTML = "";
    document.getElementById("pkm-species-modal-description").textContent = "";
    document.getElementById("pkm-species-modal-height").textContent = "—";
    document.getElementById("pkm-species-modal-weight").textContent = "—";
    document.getElementById("pkm-species-modal-genus").textContent = "—";
    document.getElementById("pkm-species-modal-ability1").textContent = "—";
    document.getElementById("pkm-species-modal-ability1").removeAttribute("data-ability-id");
    var ability2ResetEl = document.getElementById("pkm-species-modal-ability2");
    ability2ResetEl.textContent = "";
    ability2ResetEl.hidden = true;
    ability2ResetEl.removeAttribute("data-ability-id");
    document.getElementById("pkm-species-modal-abilityhidden").textContent = "—";
    document.getElementById("pkm-species-modal-abilityhidden").removeAttribute("data-ability-id");
    document.getElementById("pkm-species-modal-stats").innerHTML = "";
    document.getElementById("pkm-species-modal-evolutions").innerHTML = "";
    document.getElementById("pkm-species-modal-weaknesses").innerHTML = "";
    document.getElementById("pkm-species-modal-resistances").innerHTML = "";
    document.getElementById("pkm-species-modal-immunities").innerHTML = "";

    openModal("pkm-modal-species");

    api().get_species_modal_data(speciesId).then(function (data) {
      if (!data || data.error) {
        document.getElementById("pkm-species-modal-name").textContent = "No se pudo cargar";
        return;
      }

      document.getElementById("pkm-species-modal-name").textContent = data.name || "—";
      document.getElementById("pkm-species-modal-dexnum").textContent = "#" + String(speciesId).padStart(3, "0");
      document.getElementById("pkm-species-modal-artwork").src =
        spriteBaseUrl + "/sprites/species_artwork/" + speciesId + ".png";

      var genderHtml = "";
      // Nota: species_details() es dato de ESPECIE, no de un
      // individuo puntual -- no trae género (una especie no tiene
      // "un" género fijo, salvo las de género único). Se deja el
      // contenedor vacío a propósito, sin inventar un ícono.

      document.getElementById("pkm-species-modal-gender").innerHTML = genderHtml;

      var typesHtml = "";
      if (data.type1Key) {
        var t1 = typeInfo(data.type1Key);
        typesHtml += '<span class="pokemon-type-badge" style="' + typeStyleVars(data.type1Key) + '">' +
          typeIconSvg(data.type1Key, 14) + "<span>" + (t1 ? t1.label : "") + "</span></span>";
      }
      if (data.type2Key) {
        var t2 = typeInfo(data.type2Key);
        typesHtml += '<span class="pokemon-type-badge" style="' + typeStyleVars(data.type2Key) + '">' +
          typeIconSvg(data.type2Key, 14) + "<span>" + (t2 ? t2.label : "") + "</span></span>";
      }
      document.getElementById("pkm-species-modal-types").innerHTML = typesHtml;

      document.getElementById("pkm-species-modal-description").textContent =
        data.description || "Descripción no disponible.";

      document.getElementById("pkm-species-modal-height").textContent =
        data.heightM != null ? data.heightM + " m" : "—";
      document.getElementById("pkm-species-modal-weight").textContent =
        data.weightKg != null ? data.weightKg + " kg" : "—";
      document.getElementById("pkm-species-modal-genus").textContent = data.genus || "—";

      // Habilidades (08/09/2026 -- ahora ambas habilidades normales
      // se muestran acá, una arriba y otra abajo, en vez de en la
      // sección aparte de la derecha que quedó eliminada por estar
      // duplicada). data.ability2Id puede repetir data.ability1Id
      // en especies que solo tienen una habilidad normal -- en ese
      // caso el segundo renglón queda oculto, mismo criterio que
      // ya usaba la lista de abajo eliminada.
      var ability1El = document.getElementById("pkm-species-modal-ability1");
      ability1El.textContent = data.ability1Name || "—";
      if (data.ability1Id != null) {
        ability1El.dataset.abilityId = data.ability1Id;
        ability1El.dataset.abilityName = data.ability1Name || "";
      } else {
        delete ability1El.dataset.abilityId;
        delete ability1El.dataset.abilityName;
      }

      var ability2El = document.getElementById("pkm-species-modal-ability2");
      var hasAbility2 = data.ability2Id != null && data.ability2Id !== data.ability1Id;
      ability2El.hidden = !hasAbility2;
      if (hasAbility2) {
        ability2El.textContent = data.ability2Name || "—";
        ability2El.dataset.abilityId = data.ability2Id;
        ability2El.dataset.abilityName = data.ability2Name || "";
      } else {
        ability2El.textContent = "";
        delete ability2El.dataset.abilityId;
        delete ability2El.dataset.abilityName;
      }

      var abilityHiddenEl = document.getElementById("pkm-species-modal-abilityhidden");
      abilityHiddenEl.textContent = data.abilityHiddenName || "—";
      if (data.abilityHiddenId != null) {
        abilityHiddenEl.dataset.abilityId = data.abilityHiddenId;
        abilityHiddenEl.dataset.abilityName = data.abilityHiddenName || "";
      } else {
        delete abilityHiddenEl.dataset.abilityId;
        delete abilityHiddenEl.dataset.abilityName;
      }

      var stats = data.baseStats || {};
      var statsOrder = [
        { key: "hp", label: "HP" }, { key: "attack", label: "ATK" }, { key: "spAttack", label: "SPA" }, { key: "defense", label: "DEF" }, { key: "spDefense", label: "SPD" }, { key: "speed", label: "SPE" },
      ];
      document.getElementById("pkm-species-modal-stats").innerHTML = statsOrder.map(function (s) {
        var value = stats[s.key] != null ? stats[s.key] : 0;
        var barPercent = Math.min(100, (value / BASE_STAT_BAR_MAX) * 100);
        var barColor = BASE_STAT_BAR_COLORS[s.key];
        return (
          '<div class="pkm-species-stat-card">' +
          '<span class="pkm-species-stat-card-value">' + (stats[s.key] != null ? stats[s.key] : "—") + "</span>" +
          '<span class="pkm-species-stat-card-label">' + s.label + "</span>" +
          '<div class="pkm-species-stat-bar-track"><div class="pkm-species-stat-bar-fill" style="width:' + barPercent + "%;background:" + barColor + ';"></div></div>' +
          "</div>"
        );
      }).join("");

      // Cadena de evolución completa (07/09/2026, a pedido del
      // usuario: "haz que en la evolución siempre salgan las tres
      // etapas") -- ya viene armada del lado de Python
      // (_build_evolution_chain() en api.py), acá solo se
      // renderiza.
      //
      // Actualizado 08/09/2026: bug real corregido (reportado por
      // el usuario -- "Wurmple tiene dos ramas evolutivas y la app
      // solo muestra una", Silcoon/Cascoon -> Beautifly/Dustox).
      // La forma de los datos cambió de una lista plana a
      // {ancestors: [...], current: <nodo>} -- ver docstring de
      // _build_evolution_chain() en api.py. Los ancestros siguen
      // siendo un camino único (un Pokémon evoluciona siempre desde
      // una sola pre-evolución), pero desde la especie actual hacia
      // adelante ahora es un ÁRBOL: cada nodo puede tener varios
      // hijos (una rama por cada evolución posible), no solo el
      // primero.
      var evolutionData = data.evolutionChain || null;
      var ancestors = (evolutionData && evolutionData.ancestors) || [];
      var currentNode = evolutionData && evolutionData.current;

      function stageHtml(stage) {
        var spriteUrl = spriteBaseUrl + "/sprites/pokemon/" + stage.speciesId + ".png";
        return (
          '<div class="pkm-species-evolution-stage' + (stage.isCurrent ? " current" : "") + '" data-species-id="' + stage.speciesId + '">' +
          '<img src="' + spriteUrl + '" alt="" />' +
          '<span class="pkm-species-evolution-stage-name">' + escapeHtml(stage.name || "—") + "</span>" +
          "</div>"
        );
      }

      // Conector entre etapas (07/09/2026, a pedido del usuario:
      // "remplaza las flechas por el nivel necesario para
      // evolucionar (o el objeto/movimiento de ser el caso)") --
      // en vez de una flecha genérica siempre igual, se muestra el
      // requisito concreto: nivel, objeto (con sprite), movimiento
      // o compañero. Cuando el método no tiene ninguno de esos
      // (ej. intercambio simple, amistad, belleza -- condiciones
      // sin un valor puntual que mostrar compacto) se cae a una
      // flecha simple, con la descripción completa como tooltip en
      // cualquier caso.
      function connectorHtml(transition) {
        if (!transition) {
          return (
            '<span class="pkm-species-evolution-connector">' +
            '<svg class="pkm-species-evolution-arrow" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">' +
            '<line x1="4" y1="12" x2="18" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>' +
            '<polyline points="13,7 18,12 13,17" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
            "</span>"
          );
        }

        var innerHtml;

        // Bug real corregido (08/09/2026): `transition.level` viene
        // en 0 para los métodos sin nivel real (amistad,
        // intercambio, belleza, etc.) -- `if (transition.level)`
        // trataba 0 igual que "sin nivel" (0 es falsy en JS) y
        // caía a la flecha genérica sin decir nada de la condición
        // real. Chequeo explícito de "> 0" en vez de solo
        // verdadero/falso.
        if (transition.level != null && transition.level > 0) {
          innerHtml = '<span class="pkm-species-evolution-connector-label">Nv. ' + transition.level + "</span>";
        } else if (transition.itemId != null) {
          innerHtml = '<img class="pkm-species-evolution-item-sprite" src="' + spriteBaseUrl + "/sprites/items/" + transition.itemId + '.png" alt="" onerror="this.style.display=\'none\'" />';
        } else if (transition.moveName) {
          innerHtml = '<span class="pkm-species-evolution-connector-label">' + escapeHtml(transition.moveName) + "</span>";
        } else if (transition.teammateName) {
          innerHtml = '<span class="pkm-species-evolution-connector-label">' + escapeHtml(transition.teammateName) + "</span>";
        } else if (transition.conditionLabel) {
          innerHtml = '<span class="pkm-species-evolution-connector-label">' + escapeHtml(transition.conditionLabel) + "</span>";
        } else {
          innerHtml =
            '<svg class="pkm-species-evolution-arrow" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">' +
            '<line x1="4" y1="12" x2="18" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>' +
            '<polyline points="13,7 18,12 13,17" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        }

        return (
          '<span class="pkm-species-evolution-connector" title="' + escapeHtml(transition.description || "") + '">' +
          innerHtml +
          "</span>"
        );
      }

      // Recorre el árbol hacia adelante desde un nodo dado. Caso
      // común (0 o 1 evolución posible): se ve exactamente igual
      // que antes, una fila horizontal simple. Caso con
      // ramificación (2+ evoluciones posibles, ej. Wurmple ->
      // Silcoon/Cascoon): la etapa actual queda seguida de un
      // bloque vertical con una fila por cada rama, cada una
      // arrancando con su propio conector + el resto de su cadena
      // (que a su vez puede volver a ramificarse, aunque en la
      // práctica no hay casos así en ORAS).
      function renderForwardNode(node) {
        var html = stageHtml(node);
        var children = node.children || [];

        if (children.length === 0) {
          return html;
        }

        if (children.length === 1) {
          html += connectorHtml(children[0].transition) + renderForwardNode(children[0].node);
          return html;
        }

        var branchesHtml = children.map(function (child) {
          return (
            '<div class="pkm-species-evolution-branch-row">' +
            connectorHtml(child.transition) + renderForwardNode(child.node) +
            "</div>"
          );
        }).join("");

        html += '<div class="pkm-species-evolution-branches">' + branchesHtml + "</div>";
        return html;
      }

      var stagesHtml = "";

      ancestors.forEach(function (ancestor) {
        stagesHtml += stageHtml(ancestor) + connectorHtml(ancestor.transitionToNext);
      });

      if (currentNode) {
        stagesHtml += renderForwardNode(currentNode);
      }

      var hasChain = ancestors.length > 0 || (currentNode && currentNode.children && currentNode.children.length > 0);

      document.getElementById("pkm-species-modal-evolutions").innerHTML =
        hasChain ? stagesHtml : '<span class="pkm-modal-stat-label">No evoluciona</span>';

      renderTypeEffectGrid("pkm-species-modal-weaknesses", data.weaknesses);
      renderTypeEffectGrid("pkm-species-modal-resistances", data.resistances);
      renderTypeEffectGrid("pkm-species-modal-immunities", data.immunities);
    });
  }

  function initSpeciesModalActions() {
    var modalBody = document.getElementById("pkm-modal-species");
    if (!modalBody) {
      return;
    }

    // Delegación DENTRO del modal (07/09/2026) -- a diferencia de
    // los otros casos, acá el contenido se reconstruye cada vez
    // que se abre el modal (openSpeciesModal()), no en un poll
    // continuo, pero el mismo criterio de "un solo listener en el
    // contenedor persistente" aplica igual.
    modalBody.addEventListener("click", function (event) {
      // Habilidades clickeables (08/09/2026) -- ahora viven en el
      // panel izquierdo (.pkm-species-info-value con
      // data-ability-id) en vez de en la lista de la derecha
      // (.pkm-species-ability-row, que quedó eliminada por estar
      // duplicada); el selector cubre ambas por si algún día vuelve
      // a haber una fila con ese formato.
      var abilityRow = event.target.closest(
        ".pkm-species-ability-row[data-ability-id], .pkm-species-info-value[data-ability-id]"
      );
      if (abilityRow) {
        openAbilityModal(
          Number(abilityRow.dataset.abilityId),
          abilityRow.dataset.abilityName || ""
        );
        return;
      }

      // Etapa de evolución clickeable -- reabre este mismo modal
      // con esa especie (funciona para pre-evolución Y evoluciones
      // hacia adelante, ambas usan el mismo data-species-id). No
      // hay límite de profundidad -- se puede recorrer una cadena
      // completa clickeando varias veces seguidas.
      var stage = event.target.closest(".pkm-species-evolution-stage[data-species-id]");
      if (stage) {
        openSpeciesModal(Number(stage.dataset.speciesId));
      }
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
    {
      id: "team",
      name: "Team Overlay",
      path: "/overlay/team",
      desc: "Muestra tu equipo actual",
      width: 1170,
      height: 210,
      editable: true,
      icon:
        '<svg viewBox="0 0 240 240" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" ' +
        'd="M239.76,112.5C235.87,49.81,183.65,0,120,0S4.13,49.81.24,112.5h-.24v15h.24c3.89,62.69,56.11,112.5,119.76,112.5s115.87-49.81,119.76-112.5h.24v-15h-.24ZM120,15c55.37,0,100.87,43.09,104.74,97.5h-65.55c-3.5-17.88-19.3-31.41-38.19-31.41s-34.68,13.53-38.19,31.41H15.26C19.13,58.09,64.63,15,120,15ZM121,96.09c13.19,0,23.91,10.73,23.91,23.91s-10.73,23.91-23.91,23.91-23.91-10.73-23.91-23.91,10.73-23.91,23.91-23.91ZM120,225c-55.37,0-100.87-43.09-104.74-97.5h67.55c3.5,17.88,19.3,31.41,38.19,31.41s34.68-13.53,38.19-31.41h65.55c-3.86,54.41-49.36,97.5-104.74,97.5Z" /></svg>',
    },
    {
      id: "badges",
      name: "Badges Overlay",
      path: "/overlay/badges",
      desc: "Muestra tus medallas obtenidas",
      width: 656,
      height: 100,
      icon:
        '<svg viewBox="0 0 145.1 220.23" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-miterlimit="10" stroke-width="12">' +
        '<path d="M59.44,6.3l-50.39-.3c-2.28-.01-3.76,2.4-2.71,4.42l32.99,63.56c1.19,2.3,4.53,2.14,5.5-.26l21.98-54.43c.33-.82.29-1.74-.12-2.53l-4.58-8.83c-.52-1-1.55-1.63-2.67-1.63Z" />' +
        '<path d="M94.33,12.62c-1.24,0-2.35.75-2.81,1.89l-29.37,73.01c-.97,2.4,1.19,4.23,3.77,4,4.81-.42,12.52-.81,18.12-.28,7.38.7,11.48,2.54,17.98,5.49,1.58.72,3.44,0,4.09-1.6L139.01,14.3c.31-.77-.25-1.62-1.09-1.62l-43.59-.07Z" />' +
        '<path d="M73.34,185.86c-8.78,0-16.19-5.33-18.55-12.62h-30.45c2.62,23.03,23.99,40.99,49.98,40.99s47.36-17.96,49.98-40.99h-32.4c-2.36,7.3-9.77,12.62-18.55,12.62Z" />' +
        '<path d="M73.34,142.07c8.95,0,16.48,5.62,18.69,13.26h32.26c-2.62-23.37-23.99-41.6-49.98-41.6s-47.36,18.23-49.98,41.6h30.32c2.2-7.63,9.73-13.26,18.69-13.26Z" /></g></svg>',
    },
    {
      id: "nuzlocke",
      name: "Nuzlocke Overlay",
      path: "/overlay/nuzlocke",
      desc: "Tracker Nuzlocke con cementerio y estadísticas",
      width: 376,
      height: 177,
      icon:
        '<svg viewBox="0 0 203.71 233.8" xmlns="http://www.w3.org/2000/svg"><g fill="currentColor">' +
        '<ellipse cx="99.19" cy="193.57" rx="45.58" ry="15.45" /><circle cx="100.76" cy="63.67" r="20.8" />' +
        '<path d="M126.28,160.34l28.1-53.6c2.44-3.89,12.15-22.38,12.87-39.98.7-17.04-5.58-33.37-17.68-45.98C136.89,7.57,119.1,0,100.76,0,64.88,0,35.67,29.1,34.27,66.25c-.6,15.89,10.36,36.52,12.98,40.69l28.06,53.52c-26.73,2.28-48.93,8.27-62.26,16.89h-.11s-2.04,1.46-2.04,1.46c-9.01,6.52-10.9,13.25-10.9,17.75,0,24.44,51.24,37.23,101.86,37.23,45.76,0,82.74-9.16,95.79-23.51l.26.03,2.21-3.11c2.39-3.37,3.6-6.95,3.6-10.65,0-20.86-37.45-32.87-77.43-36.23ZM58.29,100.07c-2.05-3.08-11.47-21.6-11.02-33.33,1.13-30.13,24.63-53.74,53.5-53.74,14.82,0,29.19,6.12,39.43,16.78,9.63,10.03,14.63,22.97,14.07,36.44-.56,13.77-8.77,30.41-10.92,33.64l-.19.28-41.97,80.05-10.54-18.49-32.01-61.07-.35-.58ZM81.89,173.01l6.54,12.47-49.6-5.34c11.86-3.59,26.7-6.08,43.07-7.13ZM101.86,220.8c-24.81,0-48.05-3.09-65.43-8.69-16.18-5.21-23.42-11.56-23.42-15.54,0-1.68,1.27-3.67,3.63-5.73l160.33,18.03c-14.78,6.68-41.03,11.94-75.1,11.94ZM112.53,188.07l7.47-15.16c20.04,1.27,38.24,4.65,51.6,9.61,13.97,5.18,19.01,10.73,19.11,13.96l-78.18-8.41Z" /></g>' +
        '<path fill="none" stroke="currentColor" stroke-miterlimit="10" stroke-width="13" d="M160.76,66.5c1.36-33.11-26.86-60-60-60s-58.75,26.88-60,60c-.52,13.9,9.83,33.75,12.11,37.18l45.23,86.28c1.12,2.14,4.19,2.14,5.31,0l45.33-86.48c2.28-3.42,11.36-21.25,12-36.98Z" /></svg>',
    },
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

  // ===================== PÁGINA OVERLAYS (Bloque 4, 05/09/2026) =====================

  var ovOverlaysBuilt = false;

  function renderOverlaysPage(data) {
    if (!data.http_server) {
      return;
    }

    var baseUrl = data.http_server.base_url;
    var running = !!data.http_running;

    if (!ovOverlaysBuilt) {
      buildOverlaysList(baseUrl);
      ovOverlaysBuilt = true;
    }

    OVERLAY_DEFS.forEach(function (overlay) {
      var url = baseUrl + overlay.path;
      var urlInput = document.getElementById("ov-url-" + overlay.id);
      if (urlInput && urlInput.value !== url) {
        urlInput.value = url;
      }

      var thumb = document.getElementById("ov-thumb-" + overlay.id);
      if (thumb) {
        thumb.classList.toggle("is-unavailable", !running);
      }

      var statusRow = document.getElementById("ov-status-row-" + overlay.id);
      var statusText = document.getElementById("ov-status-text-" + overlay.id);
      if (statusRow && statusText) {
        statusRow.classList.toggle("on", running);
        statusText.textContent = running ? "Disponible" : "No disponible";
      }
      setDashDot("ov-dot-" + overlay.id, running);
    });

    // Tarjeta HTTP SERVER de esta página -- mismos campos que la
    // tarjeta del Dashboard (data.http_running/data.http_server),
    // acá nada más se repite la lectura, no se pide nada nuevo.
    setDashDot("ov-dot-server", running);
    setDashStatus("ov-server-status", running, "Activo", "Detenido");
    setToggleButton("ov-btn-server-toggle", running);
    setText(
      "ov-server-address",
      "http://" + data.http_server.host + ":" + data.http_server.port
    );
    setText(
      "ov-server-clients",
      running ? String(data.http_server.clients || 0) : "—"
    );
  }

  function buildOverlaysList(baseUrl) {
    var container = document.getElementById("ov-overlay-list");
    if (!container) {
      return;
    }
    container.innerHTML = "";

    OVERLAY_DEFS.forEach(function (overlay) {
      var url = baseUrl + overlay.path;

      var item = document.createElement("div");
      item.className = "ov-overlay-item";
      item.innerHTML =
        '<div id="ov-thumb-' + overlay.id + '" class="ov-overlay-thumb"><img id="ov-thumb-img-' + overlay.id + '" class="ov-overlay-thumb-img" alt="' + overlay.name + '" /></div>' +
        '<div class="ov-overlay-details">' +
        '<div class="ov-overlay-name">' + overlay.name + "</div>" +
        '<div class="ov-overlay-desc">' + overlay.desc + "</div>" +
        '<div id="ov-status-row-' + overlay.id + '" class="ov-overlay-status-row">' +
        '<span id="ov-dot-' + overlay.id + '" class="dash-status-dot"></span>' +
        '<span id="ov-status-text-' + overlay.id + '">No disponible</span>' +
        '<span class="ov-tag">HTML</span><span class="ov-tag">' + overlay.width + "x" + overlay.height + "</span>" +
        "</div>" +
        "</div>" +
        '<div class="ov-overlay-url-col">' +
        "<label>URL</label>" +
        '<div class="ov-overlay-url-row">' +
        '<input id="ov-url-' + overlay.id + '" class="ov-overlay-url-input" type="text" readonly value="' + url + '" />' +
        '<button class="ov-icon-btn" data-action="copy" title="Copiar URL"><svg viewBox="0 0 210 240" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M170,60h-30V25c0-13.81-11.19-25-25-25H25C11.19,0,0,11.19,0,25v120c0,13.81,11.19,25,25,25h30v30c0,13.81,11.19,25,25,25h90c13.81,0,25-11.19,25-25v-115c0-13.81-11.19-25-25-25ZM25,150c-2.76,0-5-2.24-5-5V25c0-2.76,2.24-5,5-5h90c2.76,0,5,2.24,5,5v35h-45c-13.81,0-25,11.19-25,25v70h-25ZM175,200c0,2.76-2.24,5-5,5h-90c-2.76,0-5-2.24-5-5v-115c0-2.76,2.24-5,5-5h90c2.76,0,5,2.24,5,5v115Z"/></svg></button>' +
        "</div>" +
        '<div class="ov-overlay-actions-row">' +
        '<button class="dash-btn-action" data-action="open">Abrir overlay</button>' +
        '<button class="dash-btn-sm" data-action="preview">Vista previa</button>' +
        (overlay.editable ? '<button class="dash-btn-sm" data-action="edit">Editar</button>' : "") +
        "</div>" +
        "</div>";

      item.querySelector('[data-action="copy"]').addEventListener("click", function () {
        navigator.clipboard.writeText(document.getElementById("ov-url-" + overlay.id).value);
      });
      item.querySelector('[data-action="open"]').addEventListener("click", function () {
        api().open_external(document.getElementById("ov-url-" + overlay.id).value);
      });
      item.querySelector('[data-action="preview"]').addEventListener("click", function () {
        openOverlayPreview(overlay, document.getElementById("ov-url-" + overlay.id).value);
      });

      var editBtn = item.querySelector('[data-action="edit"]');
      if (editBtn) {
        editBtn.addEventListener("click", function () {
          openTeamEditor(overlay, document.getElementById("ov-url-" + overlay.id).value);
        });
      }

      container.appendChild(item);

      // Miniatura real -- se pide una sola vez acá (no en cada
      // poll, la captura no cambia) vía el bridge de pywebview, no
      // por HTTP -- así se ve incluso con el servidor detenido,
      // mismo criterio que el logo/fondo de la pantalla Bienvenida
      // (ver api.py, _asset_data_uri()).
      api()
        .get_overlay_preview_data_uri(overlay.id)
        .then(function (dataUri) {
          if (!dataUri) {
            return;
          }
          var img = document.getElementById("ov-thumb-img-" + overlay.id);
          if (img) {
            img.src = dataUri;
          }
        });
    });
  }

  // La miniatura de la lista NUNCA abre una conexión real (ver
  // comentario de .ov-overlay-thumb en style.css) -- "Vista
  // previa" es la única vía, y a propósito: setear/limpiar el
  // `src` acá mismo (no dejarlo fijo en el HTML) es lo que hace
  // que la conexión exista solo mientras el modal está abierto,
  // así "Clientes conectados" (HTTPServer.get_active_connections())
  // sigue siendo un número real y no uno inflado por mirar esta
  // página.
  //
  // El frame se muestra al tamaño REAL del overlay (overlay.width
  // x overlay.height, ver OVERLAY_DEFS) -- ya no hay un 16:9/
  // 1920x1080 de referencia único para escalar: cada overlay tiene
  // su propia resolución pensada para OBS (05/09/2026).
  function openOverlayPreview(overlay, url) {
    document.getElementById("ov-preview-title").textContent = "Vista previa — " + overlay.name;

    var wrap = document.querySelector("#ov-modal-preview .ov-preview-frame-wrap");
    if (wrap) {
      wrap.style.width = overlay.width + "px";
      wrap.style.height = overlay.height + "px";
    }

    document.getElementById("ov-preview-iframe").src = url;
    openModal("ov-modal-preview");
  }

  function closeOverlayPreview() {
    closeModal("ov-modal-preview");
    document.getElementById("ov-preview-iframe").src = "";
  }

  function initOverlaysActions() {
    var closeBtn = document.querySelector('[data-close-modal="ov-modal-preview"]');
    if (closeBtn) {
      closeBtn.addEventListener("click", closeOverlayPreview);
    }

    var overlayBg = document.getElementById("ov-modal-preview");
    if (overlayBg) {
      overlayBg.addEventListener("click", function (event) {
        if (event.target === overlayBg) {
          closeOverlayPreview();
        }
      });
    }

    // Editor del Team Overlay (05/09/2026) -- mismo patrón de
    // cierre que el modal de "Vista previa" de arriba (limpiar el
    // `src` del iframe al cerrar, no solo ocultar el modal).
    var editorCloseBtn = document.querySelector('[data-close-modal="ov-modal-team-editor"]');
    if (editorCloseBtn) {
      editorCloseBtn.addEventListener("click", closeTeamEditor);
    }

    var editorBg = document.getElementById("ov-modal-team-editor");
    if (editorBg) {
      editorBg.addEventListener("click", function (event) {
        if (event.target === editorBg) {
          closeTeamEditor();
        }
      });
    }

    // Los 3 checkboxes y el radio de sprite se bindean UNA sola
    // vez acá (el modal es HTML estático, no se reconstruye en
    // cada poll) -- cada cambio guarda de inmediato vía
    // save_team_overlay_settings() (bridge directo, no HTTP,
    // ver api.py), sin botón "Guardar" aparte: la vista previa de
    // arriba ya refleja el cambio sola en su próximo poll de
    // 1.5s (overlays/team/app.js).
    ["ov-editor-show-hp", "ov-editor-show-level", "ov-editor-show-nickname"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) {
        el.addEventListener("change", onTeamEditorSettingChanged);
      }
    });

    document.querySelectorAll('input[name="ov-editor-sprite-set"]').forEach(function (el) {
      el.addEventListener("change", onTeamEditorSettingChanged);
    });
  }

  // La vista previa de este modal es la MISMA idea que "Vista
  // previa" (sección de arriba): el iframe solo conecta mientras
  // el modal está abierto, así que abrir el editor también cuenta
  // como una conexión real en "Clientes conectados" mientras dure.
  function openTeamEditor(overlay, url) {
    var wrap = document.querySelector("#ov-modal-team-editor .ov-preview-frame-wrap");
    if (wrap) {
      wrap.style.width = overlay.width + "px";
      wrap.style.height = overlay.height + "px";
    }

    api()
      .get_team_overlay_settings()
      .then(function (settings) {
        document.getElementById("ov-editor-show-hp").checked = settings.show_hp !== false;
        document.getElementById("ov-editor-show-level").checked = settings.show_level !== false;
        document.getElementById("ov-editor-show-nickname").checked = settings.show_nickname !== false;

        var spriteSet = settings.sprite_set || "team";
        var radio = document.querySelector(
          'input[name="ov-editor-sprite-set"][value="' + spriteSet + '"]'
        );
        if (radio) {
          radio.checked = true;
        }
      });

    document.getElementById("ov-editor-iframe").src = url;
    openModal("ov-modal-team-editor");
  }

  function closeTeamEditor() {
    closeModal("ov-modal-team-editor");
    document.getElementById("ov-editor-iframe").src = "";
  }

  function onTeamEditorSettingChanged() {
    var spriteRadio = document.querySelector('input[name="ov-editor-sprite-set"]:checked');

    api().save_team_overlay_settings({
      show_hp: document.getElementById("ov-editor-show-hp").checked,
      show_level: document.getElementById("ov-editor-show-level").checked,
      show_nickname: document.getElementById("ov-editor-show-nickname").checked,
      sprite_set: spriteRadio ? spriteRadio.value : "team",
    });
  }

  // ===================== PÁGINA CONFIGURACIÓN (Bloque 5, 05/09/2026) =====================
  //
  // Sin poll -- get_settings_page_data() se pide una sola vez cada
  // vez que se entra a la página (ver switchToPage()), no cada
  // 200ms como el Dashboard: son valores de config.json, no datos
  // en vivo del juego.

  var cfgLinksBound = false;

  // ===================== PÁGINA HERRAMIENTAS (07/09/2026) =====================
  //
  // Primera función de ESCRITURA de memoria de la GUI -- todo lo
  // demás en DexRelay es solo lectura. Sin poll propio (igual que
  // Configuración): se pide el estado de conexión una vez al
  // entrar a la página, no todo el tiempo.

  function initHerramientasActions() {
    document
      .getElementById("herr-btn-add-candy")
      .addEventListener("click", onAddRareCandyClicked);
  }

  function loadHerramientasPage() {
    api()
      .get_herramientas_page_data()
      .then(function (data) {
        var note = document.getElementById("herr-connection-note");
        var button = document.getElementById("herr-btn-add-candy");

        setCfgStatus("herr-candy-status", "", null);

        if (!data.connected) {
          note.hidden = false;
          note.textContent =
            "Azahar no está conectado -- conectate desde el Dashboard antes de usar esta herramienta.";
          note.classList.add("error");
          button.disabled = true;
          return;
        }

        button.disabled = false;
        note.classList.remove("error");
        note.hidden = true;
      });
  }

  function onAddRareCandyClicked() {
    var cantidadInput = document.getElementById("herr-candy-cantidad");
    var cantidad = parseInt(cantidadInput.value, 10);

    if (!cantidad || cantidad < 1) {
      setCfgStatus("herr-candy-status", "Ingresá una cantidad válida.", "error");
      return;
    }

    var button = document.getElementById("herr-btn-add-candy");
    button.disabled = true;

    api()
      .add_rare_candy(cantidad)
      .then(function (result) {
        button.disabled = false;

        if (result && result.error) {
          setCfgStatus("herr-candy-status", result.error, "error");
          return;
        }

        setCfgStatus(
          "herr-candy-status",
          "Listo. Ahora tenés " + result.new_quantity + " Caramelo(s) Raro(s) en la bolsa. Confirmalo abriendo la bolsa en el juego.",
          "success"
        );
      });
  }

  function initConfiguracionActions() {
    document.getElementById("cfg-btn-save").addEventListener("click", onSaveConnectionSettingsClicked);
    document.getElementById("cfg-btn-reset").addEventListener("click", onResetConnectionSettingsClicked);
    document.getElementById("cfg-btn-clear-cache").addEventListener("click", onClearCacheClicked);
  }

  function loadConfiguracionPage() {
    api()
      .get_settings_page_data()
      .then(function (data) {
        document.getElementById("cfg-host").value = data.server.host;
        document.getElementById("cfg-port").value = data.server.port;
        document.getElementById("cfg-refresh").value = data.realtime.refresh_ms;
        document.getElementById("cfg-app-version").textContent = data.appVersion;

        setCfgStatus("cfg-connection-status", "", null);
        setCfgStatus("cfg-cache-status", "", null);

        // Los links de "Acerca de" se bindean una sola vez -- el
        // destino (repo real) no cambia entre pedidos, así que no
        // hace falta re-atarlos en cada entrada a la página.
        if (!cfgLinksBound) {
          cfgLinksBound = true;

          document.getElementById("cfg-link-github").addEventListener("click", function (event) {
            event.preventDefault();
            api().open_external(data.githubUrl);
          });

          document.getElementById("cfg-link-issues").addEventListener("click", function (event) {
            event.preventDefault();
            api().open_external(data.issuesUrl);
          });
        }
      });
  }

  function setCfgStatus(elementId, message, kind) {
    var el = document.getElementById(elementId);
    el.textContent = message;
    el.classList.remove("success", "error");
    if (kind) {
      el.classList.add(kind);
    }
  }

  function onSaveConnectionSettingsClicked() {
    var host = document.getElementById("cfg-host").value;
    var port = document.getElementById("cfg-port").value;
    var refreshMs = document.getElementById("cfg-refresh").value;

    api()
      .save_connection_settings(host, port, refreshMs)
      .then(function (result) {
        if (result && result.error) {
          setCfgStatus("cfg-connection-status", result.error, "error");
          return;
        }

        setCfgStatus(
          "cfg-connection-status",
          "Guardado. Reiniciá DexRelay para que tome efecto.",
          "success"
        );
      });
  }

  function onResetConnectionSettingsClicked() {
    api()
      .reset_connection_settings()
      .then(function (defaults) {
        document.getElementById("cfg-host").value = defaults.host;
        document.getElementById("cfg-port").value = defaults.port;
        document.getElementById("cfg-refresh").value = defaults.refresh_ms;

        setCfgStatus(
          "cfg-connection-status",
          "Restablecido a los valores por defecto. Reiniciá DexRelay para que tome efecto.",
          "success"
        );
      });
  }

  function onClearCacheClicked() {
    api()
      .clear_data_cache()
      .then(function (result) {
        var cleared = (result && result.cleared) || [];

        if (cleared.length === 0) {
          setCfgStatus(
            "cfg-cache-status",
            "No había caché en disco para borrar.",
            null
          );
          return;
        }

        setCfgStatus(
          "cfg-cache-status",
          "Caché borrada (" + cleared.join(", ") + "). Se regenera sola la próxima vez que haga falta.",
          "success"
        );
      });
  }

  // ===================== PÁGINA LOGS (Bloque 5, 06/09/2026) =====================
  //
  // Buffer real de stdout/stderr (ver app/core/log_capture.py) --
  // sin Nivel/Fuente por línea, sin filtro por fecha, sin gráfico
  // de niveles. Lo único "calculado" acá es el filtro de texto
  // (client-side, sobre lo que ya se pidió) y qué línea es stderr
  // (coloreada distinto) -- todo lo demás es el dato tal cual
  // viene de Python.

  function initLogsActions() {
    document.getElementById("logs-search").addEventListener("input", renderLogsList);
    document.getElementById("logs-btn-clear").addEventListener("click", onClearLogsClicked);
  }

  function startLogsPoll() {
    stopLogsPoll();
    pollLogsPage();
    logsPollTimer = setInterval(pollLogsPage, LOGS_POLL_MS);
  }

  function stopLogsPoll() {
    if (logsPollTimer) {
      clearInterval(logsPollTimer);
      logsPollTimer = null;
    }
  }

  function pollLogsPage() {
    api()
      .get_logs()
      .then(function (entries) {
        logsAllEntries = entries;
        renderLogsList();
      });
  }

  function renderLogsList() {
    var listEl = document.getElementById("logs-list");
    var emptyEl = document.getElementById("logs-empty");
    var countEl = document.getElementById("logs-count");
    var query = document.getElementById("logs-search").value.trim().toLowerCase();

    var filtered = !query
      ? logsAllEntries
      : logsAllEntries.filter(function (entry) {
        return entry.text.toLowerCase().indexOf(query) !== -1;
      });

    countEl.textContent =
      query && filtered.length !== logsAllEntries.length
        ? filtered.length + " / " + logsAllEntries.length + " líneas"
        : logsAllEntries.length + (logsAllEntries.length === 1 ? " línea" : " líneas");

    if (filtered.length === 0) {
      listEl.innerHTML = "";
      listEl.appendChild(emptyEl);
      emptyEl.textContent = query
        ? "Ninguna línea coincide con la búsqueda."
        : "Todavía no hay nada en el buffer de logs.";
      return;
    }

    var html = "";

    filtered.forEach(function (entry) {
      var lineClass = entry.stream === "stderr" ? "log-line log-line-stderr" : "log-line";

      html +=
        '<div class="' + lineClass + '">' +
        '<span class="log-time">' + escapeHtml(entry.time) + "</span>" +
        '<span class="log-text">' + escapeHtml(entry.text) + "</span>" +
        "</div>";
    });

    listEl.innerHTML = html;

    var autoScroll = document.getElementById("logs-autoscroll").checked;
    if (autoScroll) {
      listEl.scrollTop = listEl.scrollHeight;
    }
  }

  function onClearLogsClicked() {
    api()
      .clear_logs()
      .then(function () {
        pollLogsPage();
      });
  }

  // ===================== PÁGINA NUZLOCKE (04/09/2026) =====================

  // Mismas etiquetas/estados que panels/nuzlocke/app.js
  // (NuzlockeService.VALID_ENCOUNTER_STATUSES/VALID_ORIGINS en el
  // backend) -- se repiten acá porque esta página vive en un
  // documento HTML separado del panel, no porque el significado
  // haya cambiado.
  var NZ_STATUS_LABELS = {
    sin_intentar: "Sin Capturar",
    capturado: "Capturado",
    perdido: "Perdido",
    muerto: "Muerto",
    especial: "Especial",
  };

  var NZ_ORIGIN_LABELS = {
    shiny: "Shiny",
    huevo: "Huevo",
    intercambio: "Intercambio",
    evento: "Evento",
    regalo: "Regalo",
    fosil: "Fósil",
    captura_extra: "Captura Extra",
  };

  // Ícono de tacho para el borrado directo de una fila de la
  // tabla de encuentros (05/09/2026) -- mismo SVG que ya se usa en
  // el botón "Eliminar ruta" (index.html), repetido acá porque
  // esta fila se arma dinámicamente en JS.
  var NZ_TRASH_ICON_SVG =
    '<svg viewBox="0 0 197.55 224.53" xmlns="http://www.w3.org/2000/svg"><g>' +
    '<path fill="currentColor" d="M196.1,38.57c-2.28-5.7-8.17-11.56-15.47-12.05l-35.76-.36-.18-9.41C143.26,7.53,135.31.09,126.56.08L71.23,0c-8.81-.01-16.89,7.4-18.36,16.73l-.18,9.42-35.76.36c-7.19.07-13,6.19-15.34,11.74-4.45,10.58.79,22.81,12.15,26.53-.4,1.94.17,3.59.3,5.29l.42,5.29.43,5.71.44,5.26.44,5.26.44,5.26.44,5.26.44,5.26.44,5.26.44,5.26.44,5.26.44,5.26.44,5.26.44,5.26.44,5.26.43,5.71.44,5.26.44,5.26.44,5.26.44,5.26.44,5.26.44,5.26.44,5.26.43,5.27.42,5.25.49,5.24c-.2,9.7,5.07,18.35,14.48,21.22.68.21,1.47.16,1.83.76h114.94c.36-.6,1.15-.55,1.83-.76,9.42-2.87,14.68-11.52,14.48-21.22l.49-5.24.42-5.25.43-5.27.44-5.26.44-5.26.44-5.26.44-5.26.44-5.26.44-5.26.44-5.26.43-5.71.44-5.26.44-5.26.44-5.26.44-5.26.44-5.26.44-5.26.44-5.26.44-5.26.44-5.26.44-5.26.44-5.26.44-5.26.43-5.71.42-5.29c.13-1.7.69-3.35.3-5.3,11.23-3.68,16.5-15.67,12.28-26.22ZM65.98,19.25c.03-2.99,2.75-6.09,6.2-6.09h53.2c3.45,0,6.17,3.1,6.2,6.09l.05,6.99h-65.71s.06-6.99.06-6.99ZM169.93,71.84l-.42,5.28-.44,5.26-.44,5.26-.44,5.26-.44,5.26-.44,5.26-.43,5.71-.44,5.26-.44,5.26-.44,5.26-.44,5.26-.44,5.26-.44,5.26-.44,5.26-.44,5.26-.44,5.26-.44,5.26-.44,5.26-.44,5.26-.44,5.26-.44,5.26-.43,5.71-.45,5.25c-.29,3.44-.37,7.18-1.04,10.12.51,3.9-1.92,6.64-6.11,7.45l-107.67-.08c-4.1,0-6.87-3.8-6.29-7.24-.68-3.1-.76-6.85-1.05-10.24l-.45-5.25-.43-5.71-.44-5.26-.44-5.26-.44-5.26-.44-5.26-.44-5.26-.44-5.26-.44-5.26-.44-5.26-.44-5.26-.44-5.26-.44-5.26-.44-5.26-.44-5.26-.44-5.26-.43-5.71-.44-5.26-.44-5.26-.44-5.26-.44-5.26-.44-5.26-.42-5.27c-.16-2.02-.74-4-.23-6.13h142.78c.51,2.12-.07,4.1-.23,6.12ZM178.16,52.57l-158.59-.05c-3.63,0-6.13-3.38-6.22-6.36-.09-3.08,2.46-6.7,6.22-6.7h158.42c3.61,0,6.14,3.45,6.21,6.3.08,3.42-2.19,6.07-6.04,6.82Z"/>' +
    '<path fill="currentColor" d="M72.14,184.62l-.45-7.44-.43-7.46-.44-7.01-.44-7.02-.44-7.02-.44-7.02-.44-7.02-.44-7.02-.43-7.46-.44-7.01-.44-7.02-.44-7.02-.44-7.02-.44-7.08c-.25-4.07-3.85-6.73-7.77-6.13-3.81.58-5.88,3.95-5.59,7.92l.41,5.7.46,7.43.43,7.46.44,7.01.44,7.02.44,7.02.44,7.02.44,7.02.44,7.02.43,7.46.44,7.01.44,7.02.44,7.02.44,7.02.44,7.08c.25,4.07,3.85,6.73,7.77,6.13,3.82-.59,5.94-3.92,5.61-8.11l-.43-5.49Z"/>' +
    '<path fill="currentColor" d="M138.93,78.81c-3.73-.37-7.11,2.24-7.36,6.19l-.44,7.07-.44,7.02-.44,7.02-.44,7.02-.44,7.01-.43,7.46-.44,7.02-.44,7.02-.44,7.02-.44,7.02-.44,7.02-.44,7.01-.44,7.46-.46,7.43-.41,5.69c-.3,4.12,1.97,7.58,6,7.97,3.74.36,7.16-2.2,7.4-6.37l.39-6.88.45-7.03.44-7.02.44-7.02.44-7.01.43-7.46.44-7.02.44-7.02.44-7.02.44-7.02.44-7.02.44-7.01.44-7.46.46-7.43.41-5.69c.3-4.13-1.97-7.57-6.01-7.97Z"/>' +
    '<path fill="currentColor" d="M98.56,78.79c-2.56.08-6.31,2.06-6.31,5.42v108.66c0,3.49,3.99,5.52,6.73,5.41,2.61-.1,6.33-1.99,6.33-5.62l-.02-108.45c0-3.5-3.97-5.51-6.73-5.42Z"/>' +
    "</g></svg>";

  var nuzlockeActionsInitialized = false;

  // Catálogos completos de especie/ubicación -- se piden UNA sola
  // vez (son ~700/~90 entradas, no tiene sentido pedirlos en cada
  // poll de 2s) y quedan en memoria mientras dure la sesión de la
  // GUI. Se usan para: 1) el <datalist> de los modales de
  // encuentro, 2) resolver el sprite de una fila "perdido" (que no
  // tiene un Pokémon real capturado del que sacar el speciesId).
  var nuzlockeSpeciesCatalog = null;
  var nuzlockeLocationCatalog = null;
  var nuzlockeSpeciesIdByLowerName = {};
  var nuzlockeCatalogsLoading = false;

  // Ruta/nombre (en minúsculas) -> posición en la lista ya
  // ordenada por progresión de historia que devuelve
  // get_location_catalog() (05/09/2026, a pedido del usuario: la
  // tabla de "Encuentros por Ruta" debe seguir ese mismo orden,
  // no el orden en que se registraron los encuentros). `null`
  // hasta que el catálogo termine de cargar la primera vez.
  var nuzlockeLocationOrderMap = null;

  // Estado de la fila que se está editando en el modal de
  // encuentro -- ELIMINADO (05/09/2026): ya no hay edición de
  // filas existentes, el modal solo crea ("Nuevo encuentro") y
  // cada fila se borra directo con su propio ícono de tacho (ver
  // deleteEncounterRow()).

  // Mapa nickname -> {speciesId, level} de roster+graveyard, para
  // que la tabla de encuentros pueda mostrar sprite y nivel sin
  // tener que volver a pedir nada -- ver renderNuzlockePage().
  var nuzlockeRosterByNickname = {};

  // Copia de trabajo del ruleset mientras el modal de edición está
  // abierto -- se descarta si el usuario cancela, se persiste
  // entera recién al tocar "Guardar" (ver openRulesetModal() /
  // onSaveRulesetClicked()).
  var nuzlockeRulesetDraft = [];
  var nuzlockeRuleIdCounter = 0;

  // Última respuesta completa de get_nuzlocke_page_data() -- los
  // modales (editar encuentro, ¿especial?, reglas) necesitan el
  // objeto completo de una fila/regla puntual, no solo lo que ya
  // quedó pintado en el DOM. Se reemplaza entero en cada poll (ver
  // renderNuzlockePage()), nunca se muta a mano.
  var lastNuzlockeData = null;

  function initNuzlockeActions() {
    if (nuzlockeActionsInitialized) {
      return;
    }
    nuzlockeActionsInitialized = true;

    document.getElementById("nz-btn-new-encounter").addEventListener("click", openNewEncounterModal);
    document.getElementById("nz-encounters-search").addEventListener("input", applyNuzlockeSearchFilter);
    document.getElementById("nz-btn-edit-ruleset").addEventListener("click", openRulesetModal);
    document.getElementById("nz-btn-save-encounter").addEventListener("click", onSaveEncounterClicked);
    document.getElementById("nz-btn-save-special").addEventListener("click", onSaveSpecialClicked);
    document.getElementById("nz-btn-save-ruleset").addEventListener("click", onSaveRulesetClicked);
    document.getElementById("nz-btn-add-rule").addEventListener("click", onAddRuleClicked);
    document.getElementById("nz-form-status").addEventListener("change", onEncounterStatusChanged);
    document.getElementById("nz-btn-reset-run").addEventListener("click", onResetRunClicked);

    // Botón "Ver equipo completo" de la tarjeta de líder siguiente
    // (Seguimiento) -> pestaña Líderes. Se simula un clic sobre el
    // propio botón de la pestaña en vez de llamar a switchTab()
    // directo -- ese helper vive dentro del componente genérico de
    // pestañas (ver initTabs() más arriba) y no está expuesto
    // fuera de su clausura a propósito, mismo criterio de que el
    // componente no sabe nada de Nuzlocke/Pokémon y viceversa.
    var verLiderBtn = document.getElementById("nz-btn-ver-lider");
    if (verLiderBtn) {
      verLiderBtn.addEventListener("click", function () {
        var tabBtn = document.querySelector(
          '.tabs-bar[data-tabs-group="nuzlocke"] .tab-btn[data-tab="lideres"]'
        );
        if (tabBtn) {
          tabBtn.click();
        }
      });
    }

    // Botón "Detalle de equipo" de la tarjeta de líder siguiente
    // (Seguimiento) -> abre la ventana nativa de detalle de equipo
    // (ver openLeaderTeamWindow() más abajo) para el líder
    // siguiente puntual.
    var verDetalleLiderBtn = document.getElementById("nz-btn-ver-detalle-lider");
    if (verDetalleLiderBtn) {
      verDetalleLiderBtn.addEventListener("click", function () {
        if (lastNuzlockeData && lastNuzlockeData.nextLeader) {
          openLeaderTeamWindow(lastNuzlockeData.nextLeader.order);
        }
      });
    }

    // Delegación de eventos para "Detalle de equipo" de cada
    // tarjeta de la pestaña Líderes -- las tarjetas se recrean
    // enteras en cada poll (ver renderNuzlockeLeaders()), así que
    // el listener va en el contenedor fijo, no en cada botón.
    var leadersListEl = document.getElementById("nz-leaders-list");
    if (leadersListEl) {
      leadersListEl.addEventListener("click", function (event) {
        var btn = event.target.closest(".nz-leader-detail-btn");
        if (!btn) {
          return;
        }
        openLeaderTeamWindow(Number(btn.dataset.order));
      });
    }

    document.querySelectorAll("[data-close-modal]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        closeModal(btn.dataset.closeModal);
      });
    });

    // Clic en el fondo oscuro (fuera de la tarjeta del modal)
    // cierra igual que el botón "X" -- patrón estándar de modal,
    // no hace falta que el usuario apunte exacto al botón.
    document.querySelectorAll(".nz-modal-overlay").forEach(function (overlay) {
      overlay.addEventListener("click", function (event) {
        if (event.target === overlay) {
          overlay.hidden = true;
        }
      });
    });

    document.getElementById("nz-new-rule-input").addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        onAddRuleClicked();
      }
    });
  }

  function openModal(id) {
    document.getElementById(id).hidden = false;
  }

  function closeModal(id) {
    document.getElementById(id).hidden = true;
  }

  function escapeHtml(value) {
    var div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function ensureNuzlockeCatalogs(callback) {
    if (nuzlockeSpeciesCatalog && nuzlockeLocationCatalog) {
      callback();
      return;
    }

    if (nuzlockeCatalogsLoading) {
      setTimeout(function () {
        ensureNuzlockeCatalogs(callback);
      }, 250);
      return;
    }

    nuzlockeCatalogsLoading = true;

    Promise.all([
      api().get_species_catalog(),
      api().get_location_catalog(),
    ])
      .then(function (results) {
        nuzlockeSpeciesCatalog = results[0] || [];
        nuzlockeLocationCatalog = results[1] || [];

        nuzlockeSpeciesIdByLowerName = {};
        nuzlockeSpeciesCatalog.forEach(function (species) {
          nuzlockeSpeciesIdByLowerName[(species.name || "").toLowerCase()] = species.id;
        });

        populateDatalist(
          "nz-species-options",
          nuzlockeSpeciesCatalog.map(function (species) {
            return species.name;
          })
        );

        populateDatalist(
          "nz-location-options",
          ["Inicial"].concat(
            nuzlockeLocationCatalog.map(function (location) {
              return location.name;
            })
          )
        );

        nuzlockeLocationOrderMap = {};
        nuzlockeLocationCatalog.forEach(function (location, index) {
          nuzlockeLocationOrderMap[(location.name || "").toLowerCase()] = index;
        });

        nuzlockeCatalogsLoading = false;
        callback();
      })
      .catch(function (error) {
        console.error("Error cargando catálogos de Nuzlocke:", error);
        nuzlockeCatalogsLoading = false;
        callback();
      });
  }

  function populateDatalist(id, values) {
    var el = document.getElementById(id);
    if (!el) {
      return;
    }
    el.innerHTML = "";
    values.forEach(function (value) {
      var option = document.createElement("option");
      option.value = value;
      el.appendChild(option);
    });
  }

  // 3 dígitos con cero a la izquierda (05/09/2026) -- así vienen
  // nombrados los sprites estilo Shuffle (ver
  // _serve_pokemon_shuffle_sprite() en http_server.py). No
  // reutiliza pad() de arriba porque ese rellena a 2 dígitos
  // (horas/minutos), acá hacen falta 3 (species ID hasta 802).
  function padSpeciesId(value) {
    return String(value).padStart(3, "0");
  }

  function speciesSpriteIdFor(entry) {
    // Prioridad 1: el Pokémon está/estuvo realmente en el equipo
    // (roster/graveyard) -- ahí siempre hay speciesId real, sin
    // depender de que el catálogo ya haya cargado.
    var known = nuzlockeRosterByNickname[entry.nickname];
    if (known && known.speciesId) {
      return known.speciesId;
    }

    // Prioridad 2 (filas "perdido", que nunca tuvieron un Pokémon
    // capturado real): buscar por nombre de especie en el
    // catálogo, si ya está cargado.
    if (entry.species) {
      var id = nuzlockeSpeciesIdByLowerName[entry.species.toLowerCase()];
      if (id) {
        return id;
      }
    }

    return null;
  }

  function renderNuzlockePage(data) {
    data = data || {};
    lastNuzlockeData = data;

    var roster = data.roster || [];
    var graveyard = data.graveyard || [];

    nuzlockeRosterByNickname = {};
    roster.concat(graveyard).forEach(function (entry) {
      if (entry.nickname) {
        nuzlockeRosterByNickname[entry.nickname] = entry;
      }
    });

    renderNuzlockeSummary(data.stats);
    renderNuzlockeTeam(
      data.team || [],
      graveyard.map(function (entry) {
        return entry.nickname;
      })
    );
    renderNuzlockeEncounters(data.encounters || []);
    renderNuzlockeSummaryEncounters(data.encounters || []);
    renderNuzlockePending(data.pendingEncounters || []);
    renderNuzlockeGraveyard(graveyard);
    renderNuzlockeRuleset(data.ruleset || []);
    renderNuzlockeStats(data.stats, data.playtime, data.nextLeader || null);
    renderNuzlockeNextLeader(data.nextLeader || null);
    renderNuzlockeLeaders(data.gymLeaders || []);
  }

  function setBarWidth(id, percent) {
    var el = document.getElementById(id);
    if (el) {
      el.style.width = Math.max(0, Math.min(100, percent || 0)) + "%";
    }
  }

  function renderNuzlockeSummary(stats) {
    stats = stats || {};

    var alive = stats.alive || 0;
    var dead = stats.dead || 0;
    var encountersCount = stats.encountersCount || 0;
    var total = alive + dead;

    setText("nz-stat-alive", alive);
    setText("nz-stat-dead", dead);
    setText("nz-stat-encounters", encountersCount);

    setBarWidth("nz-stat-alive-bar", total > 0 ? (alive / total) * 100 : 0);
    setBarWidth("nz-stat-dead-bar", total > 0 ? (dead / total) * 100 : 0);

    var denom = Math.max(total, encountersCount, 1);
    setBarWidth("nz-stat-encounters-bar", (encountersCount / denom) * 100);
  }

  function renderNuzlockeTeam(team, graveyardNicknames) {
    var container = document.getElementById("nz-team");
    if (!container) {
      return;
    }
    container.innerHTML = "";

    var graveyardSet = {};
    (graveyardNicknames || []).forEach(function (nickname) {
      if (nickname) {
        graveyardSet[nickname] = true;
      }
    });

    for (var i = 0; i < 6; i++) {
      var slot = team[i];
      var el = document.createElement("div");
      el.className = "dash-team-slot";

      if (!slot || slot.empty) {
        el.classList.add("empty");
        el.innerHTML = EMPTY_SLOT_ICON;
      } else {
        var spriteUrl = spriteBaseUrl + "/overlay/team/sprites/" + slot.speciesId + ".png";
        var isDead = (slot.hp || 0) <= 0 || !!graveyardSet[slot.nickname];
        el.classList.toggle("dead", isDead);

        el.innerHTML =
          '<img src="' + spriteUrl + '" alt="' + (slot.species || "") + '" />' +
          '<span class="dash-team-level">Nv. ' + slot.level + genderIconHtml(slot.genderId) + "</span>" +
          (slot.shiny ? SHINY_BADGE_ICON : "");
      }

      container.appendChild(el);
    }
  }

  function nuzlockeStatusLabel(entry) {
    if (entry.status === "especial" && entry.origin) {
      return "Especial/" + (NZ_ORIGIN_LABELS[entry.origin] || entry.origin);
    }
    if (entry.extraCapture) {
      return "Captura Extra";
    }
    return NZ_STATUS_LABELS[entry.status] || entry.status || "—";
  }

  // Posición de orden para una fila de la tabla (05/09/2026):
  // "Inicial" siempre primero; una ruta real usa su posición en
  // el catálogo (progresión de historia); un pseudo-lugar
  // "especial" con ancla conocida (huevo/intercambio/fósil
  // reubicado bajo su ruta real) se ubica justo después de esa
  // ruta; cualquier cosa sin match conocido (o mientras el
  // catálogo todavía no cargó) se manda al final, en vez de
  // desordenar lo que sí se pudo resolver.
  function encounterSortKey(entry, fallbackIndex) {
    if (entry.location === "Inicial") {
      return -1;
    }

    var map = nuzlockeLocationOrderMap;
    if (!map) {
      return fallbackIndex;
    }

    var direct = map[(entry.location || "").toLowerCase()];
    if (direct != null) {
      return direct;
    }

    if (entry.anchorLocation) {
      var anchorIdx = map[entry.anchorLocation.toLowerCase()];
      if (anchorIdx != null) {
        return anchorIdx + 0.5;
      }
    }

    return 100000 + fallbackIndex;
  }

  // ---------- Tabla "Encuentros por Ruta": todas las rutas, no solo las registradas ----------
  // A pedido del usuario (06/09/2026): la tabla de Seguimiento debe
  // mostrar TODAS las rutas del catálogo (con y sin captura), no
  // solo las que ya tienen un encuentro guardado. Se arma una fila
  // "placeholder" (sin_intentar, sin Pokémon) para cada ubicación
  // del catálogo que todavía no tiene un encuentro real -- el
  // encuentro real, si existe, siempre tiene prioridad sobre el
  // placeholder de esa misma ruta.
  function buildFullRouteEncounters(encounters) {
    if (!nuzlockeLocationCatalog) {
      // Catálogo todavía no cargó -- se muestra lo que hay
      // (comportamiento de antes de este cambio) en vez de nada;
      // ensureNuzlockeCatalogs() ya dispara un re-render apenas
      // termine de cargar (ver startNuzlockePoll()).
      return encounters;
    }

    function placeholderFor(locationName) {
      return {
        location: locationName,
        species: null,
        nickname: null,
        level: null,
        status: "sin_intentar",
        isPlaceholder: true,
      };
    }

    var byLocation = {};
    encounters.forEach(function (entry) {
      var key = (entry.location || "").toLowerCase();
      if (!byLocation[key]) {
        byLocation[key] = entry;
      }
    });

    var result = [];
    var seen = {};

    // "Inicial" siempre primero (mismo criterio que
    // encounterSortKey()), con o sin encuentro registrado.
    result.push(byLocation["inicial"] || placeholderFor("Inicial"));
    seen["inicial"] = true;

    nuzlockeLocationCatalog.forEach(function (location) {
      var key = (location.name || "").toLowerCase();
      if (seen[key]) {
        return;
      }
      seen[key] = true;
      result.push(byLocation[key] || placeholderFor(location.name));
    });

    // Cualquier encuentro registrado en una ubicación que no está
    // en el catálogo (ruta especial ancla, o algo tipeado a mano)
    // se agrega al final en vez de perderse.
    encounters.forEach(function (entry) {
      var key = (entry.location || "").toLowerCase();
      if (!seen[key]) {
        seen[key] = true;
        result.push(entry);
      }
    });

    return result;
  }

  function buildEncounterRow(entry, displayIndex, options) {
    var row = document.createElement("tr");

    var searchKey = (
      (entry.location || "") + " " + (entry.species || "") + " " + (entry.nickname || "")
    ).toLowerCase();
    row.dataset.search = searchKey;

    var known = nuzlockeRosterByNickname[entry.nickname];
    var level =
      known && known.level != null
        ? known.level
        : entry.level != null
          ? entry.level
          : null;
    var spriteId = speciesSpriteIdFor(entry);

    // A pedido del usuario (05/09/2026): sprites estilo Pokémon
    // Shuffle SOLO en esta tabla -- el resto de la app
    // (Dashboard, página Pokémon, overlays) sigue usando los
    // sets de siempre, sin tocar. Nombre de archivo con 3
    // dígitos y cero a la izquierda (ver
    // http_server.py:_serve_pokemon_shuffle_sprite()).
    var spriteHtml = spriteId
      ? '<img src="' + spriteBaseUrl + "/sprites/pokemon_shuffle/" + padSpeciesId(spriteId) + '.png" alt="" />'
      : "";

    var deleteCell = "";
    if (options.showDelete) {
      deleteCell =
        entry.location === "Inicial" || entry.isPlaceholder
          ? "<td></td>"
          : '<td><button class="nz-row-delete-btn" data-delete-location="' +
          escapeHtml(entry.location || "") +
          '" title="Eliminar ruta">' +
          NZ_TRASH_ICON_SVG +
          "</button></td>";
    }

    row.innerHTML =
      "<td>" + (displayIndex + 1) + "</td>" +
      "<td>" + escapeHtml(entry.location || "") + "</td>" +
      '<td><span class="nz-row-species">' +
      spriteHtml +
      escapeHtml(entry.species || "—") +
      (entry.shiny ? " ✨" : "") +
      "</span></td>" +
      "<td>" + escapeHtml(entry.nickname || "—") + "</td>" +
      "<td>" + (level != null ? level : "—") + "</td>" +
      '<td><span class="nz-status-pill nz-status-' + (entry.status || "sin_intentar") + '">' +
      escapeHtml(nuzlockeStatusLabel(entry)) +
      "</span></td>" +
      deleteCell;

    return row;
  }

  // Renderizador compartido entre la tabla completa/interactiva de
  // Seguimiento (`options.showDelete=true`, con buscador) y la
  // versión de solo lectura de Resumen (sin buscador ni botón de
  // borrado) -- mismo armado de fila, distinto `bodyId`/`options`.
  function renderEncountersTable(bodyId, emptyNoteId, encounters, options) {
    options = options || {};
    var body = document.getElementById(bodyId);
    var emptyNote = document.getElementById(emptyNoteId);
    if (!body) {
      return;
    }
    body.innerHTML = "";

    if (!encounters.length) {
      if (emptyNote) {
        emptyNote.hidden = false;
      }
      return;
    }
    if (emptyNote) {
      emptyNote.hidden = true;
    }

    var sorted = encounters
      .map(function (entry, index) {
        return { entry: entry, index: index };
      })
      .sort(function (a, b) {
        return (
          encounterSortKey(a.entry, a.index) -
          encounterSortKey(b.entry, b.index)
        );
      })
      .map(function (wrapped) {
        return wrapped.entry;
      });

    sorted.forEach(function (entry, index) {
      body.appendChild(buildEncounterRow(entry, index, options));
    });

    if (options.showDelete) {
      body.querySelectorAll("[data-delete-location]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          deleteEncounterRow(btn.dataset.deleteLocation);
        });
      });
    }

    if (options.applySearch) {
      applyNuzlockeSearchFilter();
    }
  }

  function renderNuzlockeEncounters(encounters) {
    renderEncountersTable(
      "nz-encounters-body",
      "nz-encounters-empty",
      buildFullRouteEncounters(encounters || []),
      { showDelete: true, applySearch: true }
    );
  }

  // Versión de solo lectura para Resumen (06/09/2026, a pedido del
  // usuario): SIN mezclar con el catálogo completo de rutas --
  // solo lo que ya se registró de verdad, sin buscador ni botón de
  // borrado. La tabla completa con todas las rutas (con y sin
  // captura) vive en Seguimiento (ver renderNuzlockeEncounters()).
  function renderNuzlockeSummaryEncounters(encounters) {
    renderEncountersTable(
      "nz-encounters-resumen-body",
      "nz-encounters-resumen-empty",
      encounters || [],
      { showDelete: false, applySearch: false }
    );
  }

  function applyNuzlockeSearchFilter() {
    var input = document.getElementById("nz-encounters-search");
    var query = (input.value || "").trim().toLowerCase();

    document.querySelectorAll("#nz-encounters-body tr").forEach(function (row) {
      var matches = !query || (row.dataset.search || "").indexOf(query) !== -1;
      row.classList.toggle("nz-row-hidden", !matches);
    });
  }

  function renderNuzlockePending(pending) {
    var card = document.getElementById("nz-pending-card");
    var list = document.getElementById("nz-pending-list");
    var countEl = document.getElementById("nz-pending-count");
    if (!card || !list) {
      return;
    }

    card.hidden = pending.length === 0;
    setText("nz-pending-count", pending.length);
    list.innerHTML = "";

    pending.forEach(function (entry) {
      var item = document.createElement("div");
      item.className = "nz-pending-item";

      var spriteUrl = spriteBaseUrl + "/overlay/team/sprites/" + entry.speciesId + ".png";
      var subParts = [];
      if (entry.metLocation) {
        subParts.push(entry.metLocation);
      }
      subParts.push(entry.shiny ? "✨ Shiny" : "Sin ruta detectada");

      item.innerHTML =
        '<img src="' + spriteUrl + '" alt="" />' +
        '<div class="nz-pending-info">' +
        '<span class="nz-pending-name">' + escapeHtml(entry.nickname || entry.species || "") + "</span>" +
        '<span class="nz-pending-sub">' + escapeHtml(subParts.join(" · ")) + "</span>" +
        "</div>" +
        '<div class="nz-pending-actions">' +
        '<button class="dash-btn-sm" data-assign="' + escapeHtml(entry.nickname || "") + '">Asignar</button>' +
        '<button class="dash-btn-sm" data-discard="' + escapeHtml(entry.nickname || "") + '">Descartar</button>' +
        "</div>";

      list.appendChild(item);
    });

    list.querySelectorAll("[data-assign]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        openSpecialModal(btn.dataset.assign);
      });
    });

    list.querySelectorAll("[data-discard]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (!window.confirm("¿Descartar esta captura de los encuentros por ruta? El Pokémon se queda en tu equipo igual, solo deja de contar para el tracker.")) {
          return;
        }
        api()
          .nuzlocke_discard_pending(btn.dataset.discard)
          .then(pollNuzlockePage);
      });
    });
  }

  function renderNuzlockeGraveyard(graveyard) {
    var list = document.getElementById("nz-graveyard-list");
    var emptyNote = document.getElementById("nz-graveyard-empty");
    if (!list) {
      return;
    }

    setText("nz-graveyard-count", graveyard.length);
    list.innerHTML = "";

    if (!graveyard.length) {
      emptyNote.hidden = false;
      return;
    }
    emptyNote.hidden = true;

    graveyard.forEach(function (entry) {
      var item = document.createElement("div");
      item.className = "nz-graveyard-item";

      var spriteUrl = spriteBaseUrl + "/overlay/team/sprites/" + entry.speciesId + ".png";

      item.innerHTML =
        '<img src="' + spriteUrl + '" alt="" />' +
        '<div class="nz-graveyard-info">' +
        '<span class="nz-graveyard-name">' + escapeHtml(entry.nickname || "") + "</span>" +
        '<span class="nz-graveyard-sub">' + escapeHtml(entry.species || "") + " · Nv. " + (entry.level != null ? entry.level : "—") + "</span>" +
        "</div>";

      list.appendChild(item);
    });
  }

  function renderNuzlockeRuleset(ruleset) {
    var list = document.getElementById("nz-ruleset-list");
    if (!list) {
      return;
    }
    list.innerHTML = "";

    // A pedido del usuario (05/09/2026): las reglas desactivadas
    // ya NO se muestran tachadas -- directamente no aparecen en la
    // tarjeta (siguen existiendo y son editables desde el modal
    // "Editar", que sí las lista a todas con su checkbox).
    var activeRules = ruleset.filter(function (rule) {
      return rule.enabled;
    });

    if (!activeRules.length) {
      list.innerHTML = '<p class="nz-empty-note">Sin reglas activas.</p>';
      return;
    }

    activeRules.forEach(function (rule) {
      var row = document.createElement("div");
      row.className = "nz-ruleset-row";
      row.innerHTML =
        '<span class="nz-ruleset-check">✓</span>' +
        "<span>" + escapeHtml(rule.label) + "</span>";
      list.appendChild(row);
    });
  }

  function formatPlaytime(playtime) {
    if (!playtime || !playtime.available) {
      return null;
    }
    // A pedido del usuario (05/09/2026): sin segundos -- el dato
    // ya es "impreciso" en tiempo real (sale del archivo de
    // guardado, no se actualiza hasta el próximo save), así que
    // mostrar segundos exactos da una falsa sensación de
    // precisión.
    return pad(playtime.hours) + ":" + pad(playtime.minutes);
  }

  function renderNuzlockeStats(stats, playtime, nextLeader) {
    stats = stats || {};

    setText("nz-stat-unique", stats.uniqueSpecies || 0);
    setText("nz-stat-captures", stats.captures || 0);
    setText("nz-stat-deaths", stats.dead || 0);
    setText("nz-stat-survival", (stats.survivalRate || 0) + "%");

    // Level cap (Fase B, roadmap 3.2) -- mismo valor que la
    // tarjeta "Líder siguiente" de Seguimiento, a pedido del
    // usuario también visible acá junto al resto de estadísticas.
    // "—" si ya se obtuvieron las 8 medallas (nextLeader es null).
    setText(
      "nz-stat-levelcap",
      nextLeader ? "Nv. " + nextLeader.levelCap : "—"
    );

    var formatted = formatPlaytime(playtime);
    var note = document.getElementById("nz-playtime-note");

    if (formatted) {
      setText("nz-stat-playtime", formatted);
      note.hidden = true;
    } else {
      setText("nz-stat-playtime", "—");
      note.hidden = false;
      note.textContent =
        "El tiempo de juego sale del archivo de guardado, no de la memoria en vivo -- se actualiza recién cuando guardás la partida" +
        (playtime && playtime.reason ? " (" + playtime.reason + ")" : ".");
    }
  }

  // ---------- Pestaña Seguimiento: tarjeta compacta "líder siguiente" (Fase B) ----------
  // Datos ya resueltos enteros por Api.get_nuzlocke_page_data()
  // (ver GymLeaderCatalog, app/services/gym_leaders.py) -- acá solo
  // se arma el HTML, sin ningún cálculo (badges/level cap ya
  // vienen calculados desde Python).
  function renderNuzlockeNextLeader(nextLeader) {
    var body = document.getElementById("nz-next-leader-body");
    var btn = document.getElementById("nz-btn-ver-lider");
    var detailBtn = document.getElementById("nz-btn-ver-detalle-lider");

    if (!body) {
      return;
    }

    if (!nextLeader) {
      // Las 8 medallas ya están obtenidas -- no queda "líder
      // siguiente" que mostrar, no es un error ni un dato faltante.
      body.innerHTML = '<p class="nz-empty-note">¡Ya obtuviste las 8 medallas!</p>';
      if (btn) {
        btn.hidden = true;
      }
      if (detailBtn) {
        detailBtn.hidden = true;
      }
      return;
    }

    if (btn) {
      btn.hidden = false;
    }
    if (detailBtn) {
      detailBtn.hidden = false;
    }

    var portraitUrl = spriteBaseUrl + "/sprites/gym_leaders/" + nextLeader.portraitIndex + ".png";

    var teamHtml = (nextLeader.team || []).map(function (mon) {
      var spriteUrl = spriteBaseUrl + "/sprites/pokemon_shuffle/" + padSpeciesId(mon.speciesId) + ".png";
      return (
        '<div class="nz-next-leader-mon">' +
        '<img src="' + spriteUrl + '" alt="' + escapeHtml(mon.species || "") + '" />' +
        "<span>Nv. " + mon.level + "</span>" +
        "</div>"
      );
    }).join("");

    body.innerHTML =
      '<img class="nz-next-leader-portrait" src="' + portraitUrl + '" alt="" />' +
      '<div class="nz-next-leader-info">' +
      '<span class="nz-next-leader-name">' + escapeHtml(nextLeader.nameEs || nextLeader.name || "") + "</span>" +
      '<span class="nz-next-leader-badge">' + escapeHtml(nextLeader.badgeNameEs || nextLeader.badgeName || "") + "</span>" +
      '<span class="nz-next-leader-location">' + escapeHtml(nextLeader.gymLocationEs || nextLeader.gymLocation || "") + "</span>" +
      "</div>" +
      '<div class="nz-next-leader-team">' + teamHtml + "</div>" +
      '<div class="nz-next-leader-cap">' +
      '<span class="nz-next-leader-cap-value">Nv. ' + nextLeader.levelCap + "</span>" +
      // "Lvl Cap" (06/09/2026, a pedido del usuario -- antes
      // decía "Nivel máximo").
      '<span class="nz-next-leader-cap-label">Lvl Cap</span>' +
      "</div>";
  }

  // ---------- Pestaña Líderes: detalle completo de los 8 equipos (Fase B) ----------
  // Mismo dato que la tarjeta compacta de arriba (data.gymLeaders),
  // pero acá SÍ entran tipos y movimientos -- ver roadmap 3.3
  // ("con el detalle grande que en Seguimiento se muestra
  // resumido"). `leader.earned` ya viene calculado desde Python
  // cruzando el orden del líder contra el bitfield de medallas.
  function renderNuzlockeLeaders(leaders) {
    var container = document.getElementById("nz-leaders-list");
    if (!container) {
      return;
    }
    container.innerHTML = "";

    (leaders || []).forEach(function (leader) {
      var card = document.createElement("div");
      card.className = "nz-leader-card" + (leader.earned ? " earned" : "");

      var portraitUrl = spriteBaseUrl + "/sprites/gym_leaders/" + leader.portraitIndex + ".png";

      var teamHtml = (leader.team || []).map(function (mon) {
        var spriteUrl = spriteBaseUrl + "/sprites/pokemon_shuffle/" + padSpeciesId(mon.speciesId) + ".png";

        var typesHtml = (mon.typeKeys || []).map(function (typeKey) {
          var info = typeInfo(typeKey);
          return (
            '<span class="nz-leader-mon-type" style="' + typeStyleVars(typeKey) + '" title="' + (info ? info.label : "") + '">' +
            typeIconSvg(typeKey, 12) +
            "</span>"
          );
        }).join("");

        // Movimientos apilados (06/09/2026, a pedido del usuario:
        // antes iban unidos con " · " en una sola línea) -- cada
        // uno en su propia fila dentro de .nz-leader-mon-moves
        // (ver style.css, ahora flex-column en vez de texto plano).
        // Clickeables (07/09/2026) -- data-move-name en inglés
        // (name, sin traducir), mismo criterio que
        // leader_team_window.js: get_move_modal_data_by_name()
        // normaliza contra el identifier real de PokéAPI.
        var movesHtml = (mon.moves || []).map(function (name) {
          return '<span class="nz-leader-mon-move-line" data-move-name="' + escapeHtml(name) + '">' +
            escapeHtml(translateMoveName(name)) + "</span>";
        }).join("");

        return (
          '<div class="nz-leader-mon' + (mon.isAce ? " ace" : "") + '">' +
          '<img src="' + spriteUrl + '" alt="' + escapeHtml(mon.species || "") + '" />' +
          '<div class="nz-leader-mon-info">' +
          '<span class="nz-leader-mon-name" data-species-id="' + mon.speciesId + '" title="Ver Pokédex de la especie">' + escapeHtml(mon.species || "") +
          (mon.isAce ? ' <span class="nz-leader-ace-tag">Ace</span>' : "") +
          "</span>" +
          '<span class="nz-leader-mon-level">Nv. ' + mon.level + "</span>" +
          '<span class="nz-leader-mon-types">' + typesHtml + "</span>" +
          // Habilidad (06/09/2026): ahora curada en
          // data/gym_leaders.json (investigada contra
          // Bulbapedia + un playthrough completo de ORAS,
          // ver GYM_ABILITY_NAMES_ES en gym_leaders.py) -- ya
          // no es "No disponible" a diferencia de Naturaleza/
          // IVs/EVs, que sí son imposibles de saber sin el
          // save real del entrenador rival. Clickeable
          // (07/09/2026) solo si mon.ability existe -- mismo
          // criterio que la página Pokémon (un "—" sin
          // habilidad conocida no debería ser clickeable).
          '<span class="nz-leader-mon-ability"' +
          (mon.ability ? ' data-ability-name="' + escapeHtml(mon.ability) + '"' : "") +
          ">Habilidad: <em>" + escapeHtml(mon.abilityEs || mon.ability || "—") + "</em></span>" +
          (movesHtml ? '<div class="nz-leader-mon-moves">' + movesHtml + "</div>" : "") +
          "</div>" +
          "</div>"
        );
      }).join("");

      card.innerHTML =
        '<div class="nz-leader-header">' +
        '<img class="nz-leader-portrait" src="' + portraitUrl + '" alt="" />' +
        '<div class="nz-leader-info">' +
        '<span class="nz-leader-name">' + escapeHtml(leader.nameEs || leader.name || "") + "</span>" +
        '<span class="nz-leader-badge">' + escapeHtml(leader.badgeNameEs || leader.badgeName || "") + "</span>" +
        '<span class="nz-leader-location">' + escapeHtml(leader.gymLocationEs || leader.gymLocation || "") + "</span>" +
        "</div>" +
        '<div class="nz-leader-header-actions">' +
        '<span class="nz-leader-status-pill' + (leader.earned ? " earned" : "") + '">' +
        (leader.earned ? "Obtenida" : "Pendiente") +
        "</span>" +
        // Botón de solo ícono + tooltip (06/09/2026, mismo
        // tratamiento que "Detalle de equipo" de la tarjeta de
        // líder siguiente en Seguimiento -- ver .dash-icon-btn/
        // [data-tooltip] en style.css) -- reemplaza al botón de
        // texto que antes iba en una fila aparte al pie de la
        // tarjeta.
        '<button class="dash-icon-btn nz-leader-detail-btn" data-order="' + leader.order + '" data-tooltip="Detalle de equipo" aria-label="Detalle de equipo">' +
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M9,2v2H5v16h14V4h-4v-2H9ZM7,6h10v12H7V6ZM9,8v2h6v-2h-6ZM9,11v2h6v-2h-6ZM9,14v2h4v-2h-4Z" /></svg>' +
        "</button>" +
        "</div>" +
        "</div>" +
        '<div class="nz-leader-cap-row">' +
        "<span>Nivel máximo permitido</span>" +
        '<span class="nz-leader-cap-value">Nv. ' + leader.levelCap + "</span>" +
        "</div>" +
        '<div class="nz-leader-team">' + teamHtml + "</div>";

      container.appendChild(card);
    });
  }

  // ---------- Ventana nativa: detalle de equipo de un líder (Fase B, 06/09/2026) ----------
  // Reemplaza al modal movible original -- a pedido del usuario,
  // esto ahora abre una ventana de pywebview de verdad
  // (webview.create_window(), ver Api.open_leader_team_window()
  // en api.py) en vez de un <div> superpuesto: se pueden abrir
  // varias a la vez (una por líder) y cada una se puede mover
  // fuera de los límites de la ventana principal, cosa que un
  // modal HTML nunca puede hacer. Toda la lógica de armado de las
  // tarjetas por Pokémon vive en leader_team_window.js, que corre
  // dentro de esa ventana nueva -- acá solo se dispara la apertura.
  function openLeaderTeamWindow(order) {
    if (!order) {
      return;
    }
    api().open_leader_team_window(order);
  }

  // ---------- Modal: Nuevo encuentro / Editar ----------

  function openNewEncounterModal() {
    document.getElementById("nz-encounter-modal-title").textContent = "Nuevo encuentro";
    document.getElementById("nz-form-location").value = "";
    document.getElementById("nz-form-location").disabled = false;
    document.getElementById("nz-form-nickname").value = "";
    document.getElementById("nz-form-species").value = "";
    document.getElementById("nz-form-status").value = "capturado";
    document.getElementById("nz-form-origin").value = "shiny";
    document.getElementById("nz-form-shiny").checked = false;
    hideEncounterError();
    onEncounterStatusChanged();

    ensureNuzlockeCatalogs(function () {
      openModal("nz-modal-encounter");
    });
  }

  function onEncounterStatusChanged() {
    var status = document.getElementById("nz-form-status").value;
    var isEspecial = status === "especial";
    var isLost = status === "perdido";

    // A pedido del usuario (05/09/2026): "perdido" es un combate
    // salvaje que se perdió/del que se huyó -- nunca hubo captura,
    // así que no hay nickname que poner. El campo queda visible
    // (por si el usuario igual quiere anotar algo) pero deja de
    // ser obligatorio -- ver onSaveEncounterClicked(). El campo
    // "Origen" solo aplica a "especial"; para "perdido" además se
    // deshabilita por completo (no solo se oculta), para que quede
    // claro que no corresponde acá.
    document.getElementById("nz-form-origin-field").hidden = !isEspecial;
    document.getElementById("nz-form-origin").disabled = isLost;

    var nicknameInput = document.getElementById("nz-form-nickname");
    nicknameInput.placeholder = isLost ? "Opcional para \"Perdido\"" : "";
  }

  function showEncounterError(message) {
    var el = document.getElementById("nz-encounter-error");
    el.textContent = message;
    el.hidden = false;
  }

  function hideEncounterError() {
    document.getElementById("nz-encounter-error").hidden = true;
  }

  function onSaveEncounterClicked() {
    var location = document.getElementById("nz-form-location").value.trim();
    var nickname = document.getElementById("nz-form-nickname").value.trim();
    var species = document.getElementById("nz-form-species").value.trim();
    var status = document.getElementById("nz-form-status").value;
    var origin = status === "especial" ? document.getElementById("nz-form-origin").value : null;
    var shiny = document.getElementById("nz-form-shiny").checked;

    // "Perdido" (05/09/2026, a pedido del usuario): nunca hubo
    // captura real, así que el nickname no es obligatorio acá --
    // para cualquier otro estado sigue siendo requerido.
    var isLost = status === "perdido";

    if (!location || !species || (!isLost && !nickname)) {
      showEncounterError(
        isLost
          ? "Ruta y especie son obligatorios."
          : "Ruta, nickname y especie son obligatorios."
      );
      return;
    }

    hideEncounterError();

    api()
      .nuzlocke_save_encounter(location, nickname, species, status, origin, shiny)
      .then(function (result) {
        if (result && result.error) {
          showEncounterError(result.error);
          return;
        }
        closeModal("nz-modal-encounter");
        pollNuzlockePage();
      });
  }

  // Botón "Reiniciar partida" del header de la página (06/09/2026,
  // se nos había pasado por alto -- el backend, Api.nuzlocke_reset_all()
  // -> NuzlockeService.reset_all(), ya existía de antes para un panel
  // viejo, ver app/server/http_server.py -- acá solo faltaba
  // conectarlo a un botón real de la GUI v2). Mensaje del confirm
  // detalla EXACTO lo que borra/conserva, calcado del docstring real
  // de reset_all(): roster/cementerio/encuentros/pendientes se
  // vacían, el ruleset (las reglas de la casa que el jugador eligió)
  // NO se toca.
  function onResetRunClicked() {
    if (
      !window.confirm(
        "Esto borra TODO el progreso de este Nuzlocke (equipo, cementerio, encuentros y capturas pendientes) para volver a empezar de cero. Las reglas de la partida no se borran. No se puede deshacer. ¿Continuar?"
      )
    ) {
      return;
    }

    api()
      .nuzlocke_reset_all()
      .then(function () {
        pollNuzlockePage();
      });
  }

  // Borrado directo de fila (05/09/2026, a pedido del usuario):
  // reemplaza el flujo viejo de "abrir modal de edición -> botón
  // Eliminar ruta adentro" -- ya no existe edición de una fila
  // existente, cada fila tiene su propio ícono de tacho que borra
  // directo (con la misma confirmación de antes). "Inicial" ni
  // siquiera recibe el botón (ver renderNuzlockeEncounters()).
  function deleteEncounterRow(location) {
    if (!window.confirm('Esto borra el registro de "' + location + '" Y el Pokémon capturado ahí (roster/cementerio). No se puede deshacer. ¿Continuar?')) {
      return;
    }

    api()
      .nuzlocke_delete_encounter(location)
      .then(function (result) {
        if (result && result.error) {
          window.alert(result.error);
          return;
        }
        pollNuzlockePage();
      });
  }

  // ---------- Modal: ¿Pokémon Especial? ----------

  var nuzlockeSpecialNickname = null;

  function openSpecialModal(nickname) {
    nuzlockeSpecialNickname = nickname;

    var data = (lastNuzlockeData && lastNuzlockeData.pendingEncounters) || [];
    var match = data.find(function (item) {
      return item.nickname === nickname;
    });

    document.getElementById("nz-special-subject").textContent = match
      ? (match.nickname || match.species) + (match.metLocation ? " -- " + match.metLocation : "")
      : nickname;

    document.getElementById("nz-form-special-origin").value = "shiny";
    openModal("nz-modal-special");
  }

  function onSaveSpecialClicked() {
    if (!nuzlockeSpecialNickname) {
      return;
    }

    var origin = document.getElementById("nz-form-special-origin").value;

    api()
      .nuzlocke_assign_special(nuzlockeSpecialNickname, origin)
      .then(function () {
        closeModal("nz-modal-special");
        pollNuzlockePage();
      });
  }

  // ---------- Modal: Editar reglas ----------

  function openRulesetModal() {
    var current = (lastNuzlockeData && lastNuzlockeData.ruleset) || [];

    nuzlockeRulesetDraft = current.map(function (rule) {
      return { id: rule.id, label: rule.label, enabled: !!rule.enabled };
    });

    renderRulesetDraft();
    document.getElementById("nz-new-rule-input").value = "";
    openModal("nz-modal-ruleset");
  }

  function renderRulesetDraft() {
    var list = document.getElementById("nz-ruleset-edit-list");
    list.innerHTML = "";

    nuzlockeRulesetDraft.forEach(function (rule, index) {
      var row = document.createElement("div");
      row.className = "nz-ruleset-edit-row";

      row.innerHTML =
        '<input type="checkbox" ' + (rule.enabled ? "checked" : "") + " />" +
        '<input type="text" value="' + escapeHtml(rule.label) + '" />' +
        '<button class="nz-ruleset-remove-btn" title="Quitar"><svg class="nz-close-icon" viewBox="0 0 150.02 150.04" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M77.38,0c6.07.18,9.99,5.23,11.32,10.77l.1,50.24.21.22h49.19c6.05.83,11.53,4.97,11.82,11.42v4.69c-1.2,5.53-5.61,10-11.46,10.84h-50.33s-.15,50.54-.15,50.54c0,3.31-2.26,6.09-4.49,8.11-4.9,4.46-12.39,4.17-17.3-.08-2.19-2.28-4.36-4.87-4.36-8.26l-.08-50.31H11.33c-4.98-1.07-8.44-3.71-10.48-8.45-1.7-4.6-.84-9.61,2.23-13.27,2.4-2.34,4.97-4.55,8.46-4.55l50.31-.1V11.46c.82-5.87,5.3-10.19,10.83-11.46h4.69Z"/></svg></button>';

      row.querySelector('input[type="checkbox"]').addEventListener("change", function (event) {
        nuzlockeRulesetDraft[index].enabled = event.target.checked;
      });

      row.querySelector('input[type="text"]').addEventListener("input", function (event) {
        nuzlockeRulesetDraft[index].label = event.target.value;
      });

      row.querySelector(".nz-ruleset-remove-btn").addEventListener("click", function () {
        nuzlockeRulesetDraft.splice(index, 1);
        renderRulesetDraft();
      });

      list.appendChild(row);
    });
  }

  function onAddRuleClicked() {
    var input = document.getElementById("nz-new-rule-input");
    var label = input.value.trim();
    if (!label) {
      return;
    }

    nuzlockeRuleIdCounter += 1;
    nuzlockeRulesetDraft.push({
      id: "custom_" + Date.now() + "_" + nuzlockeRuleIdCounter,
      label: label,
      enabled: true,
    });

    input.value = "";
    renderRulesetDraft();
  }

  function onSaveRulesetClicked() {
    api()
      .nuzlocke_save_ruleset(nuzlockeRulesetDraft)
      .then(function (result) {
        if (result && result.error) {
          window.alert(result.error);
          return;
        }
        closeModal("nz-modal-ruleset");
        pollNuzlockePage();
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
