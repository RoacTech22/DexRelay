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

  var waitingPollTimer = null;
  var mainPollTimer = null;
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
        document.querySelectorAll(".nav-item").forEach(function (el) {
          el.classList.remove("active");
        });
        item.classList.add("active");

        var page = item.dataset.page;
        document.querySelectorAll(".page").forEach(function (el) {
          el.classList.remove("active");
        });
        document.getElementById("page-" + page).classList.add("active");
      });
    });
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
    setText("dash-reader-team-count", teamCount + "/6");

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

    setText("dash-team-total", filled + "/6");
    setText("dash-team-avg-level", filled > 0 ? Math.round(levelSum / filled) : "—");
    setText("dash-team-hp", filled > 0 ? totalHp + "/" + maxHp : "—");

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

    setText("dash-badges-count", count + "/8");

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
