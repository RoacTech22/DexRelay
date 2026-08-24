const API_URL = "/api/badges";

const BADGE_COUNT = 8;

const badgesElement =
    document.getElementById("badges");

/* Igual que en el Team Overlay: se crean los
   8 slots UNA sola vez al cargar la pagina, y
   despues solo se les cambia la clase segun el
   estado. No se reconstruye el DOM en cada
   ciclo de polling (mismo motivo que el fix del
   bug de conexiones en el Team Overlay: menos
   trabajo por ciclo, nada que "parpadee"). */

let previousBadges = new Array(BADGE_COUNT).fill(null);

let loadInProgress = false;


/* =========================================
   CREAR SLOTS (una sola vez)
========================================= */

function createSlots() {

    for (
        let index = 0;
        index < BADGE_COUNT;
        index++
    ) {

        const badgeNumber = index + 1;

        const badge =
            document.createElement("div");

        badge.className = "badge pending";
        badge.dataset.badge = String(badgeNumber);
        badge.id = `badge-${badgeNumber}`;

        badge.style.backgroundImage =
            `url("sprites/${badgeNumber}.png")`;

        badgesElement.appendChild(badge);
    }
}


/* =========================================
   CARGAR MEDALLAS
========================================= */

async function loadBadges() {

    if (loadInProgress) {
        return;
    }

    loadInProgress = true;

    try {

        const response =
            await fetch(
                API_URL,
                { cache: "no-store" }
            );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        const data =
            await response.json();

        renderBadges(data);

    } catch (error) {

        console.error(
            "Error cargando las medallas:",
            error
        );

    } finally {

        loadInProgress = false;

    }
}


/* =========================================
   RENDER
========================================= */

function renderBadges(data) {

    const badges =
        Array.isArray(data.badges)
            ? data.badges
            : [];

    for (
        let index = 0;
        index < BADGE_COUNT;
        index++
    ) {

        const badgeNumber = index + 1;

        const obtained =
            Boolean(badges[index]);

        const wasObtained =
            previousBadges[index];

        const badgeElement =
            document.getElementById(
                `badge-${badgeNumber}`
            );

        if (!badgeElement) {
            continue;
        }

        const justObtained =
            obtained &&
            wasObtained === false;

        badgeElement.className =
            "badge" +
            (obtained ? " obtained" : " pending") +
            (justObtained ? " just-obtained" : "");

        if (justObtained) {

            // Quita la clase de animacion despues
            // de que termine, para que se pueda
            // volver a disparar en el futuro si
            // hiciera falta (ej. tras resetear
            // datos de prueba).
            window.setTimeout(() => {

                badgeElement.classList.remove(
                    "just-obtained"
                );

            }, 650);
        }

        previousBadges[index] = obtained;
    }
}


/* =========================================
   INICIO
========================================= */

createSlots();
loadBadges();

setInterval(loadBadges, 200);
