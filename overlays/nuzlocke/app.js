const NUZLOCKE_API_URL = "/api/nuzlocke";
const BADGES_API_URL = "/api/badges";

const graveyardElement =
    document.getElementById("graveyard");

/* Sprites reutilizados del Team Overlay via ruta relativa --
   evita duplicar assets; el navegador resuelve "../team/sprites/"
   contra la URL actual (/overlay/nuzlocke/), que el HTTP server
   ya sirve en /overlay/team/sprites/. */
const TEAM_SPRITES_PATH = "../team/sprites";

/* Nicknames ya renderizados en el cementerio, para no volver a
   crear el mismo elemento en cada ciclo de polling (las muertes
   son permanentes: el cementerio solo crece, nunca hace falta
   reconstruirlo ni quitar nada). */
const renderedGraves = new Set();

let loadInProgress = false;


/* =========================================
   CARGAR DATOS
========================================= */

async function loadNuzlocke() {

    if (loadInProgress) {
        return;
    }

    loadInProgress = true;

    try {

        const [nuzlockeResponse, badgesResponse] =
            await Promise.all([
                fetch(
                    NUZLOCKE_API_URL,
                    { cache: "no-store" }
                ),
                fetch(
                    BADGES_API_URL,
                    { cache: "no-store" }
                )
            ]);

        if (!nuzlockeResponse.ok) {
            throw new Error(
                `HTTP ${nuzlockeResponse.status}`
            );
        }

        const nuzlocke =
            await nuzlockeResponse.json();

        let badges = {
            count: 0
        };

        if (badgesResponse.ok) {

            badges =
                await badgesResponse.json();
        }

        render(nuzlocke, badges);

    } catch (error) {

        console.error(
            "Error cargando el Nuzlocke Tracker:",
            error
        );

    } finally {

        loadInProgress = false;

    }
}


/* =========================================
   RENDER
========================================= */

function render(nuzlocke, badges) {

    const roster =
        Array.isArray(nuzlocke.roster)
            ? nuzlocke.roster
            : [];

    const graveyard =
        Array.isArray(nuzlocke.graveyard)
            ? nuzlocke.graveyard
            : [];

    renderStats(
        roster,
        graveyard,
        badges
    );

    renderGraveyard(
        graveyard
    );
}


function renderStats(
    roster,
    graveyard,
    badges
) {

    const caught =
        roster.length + graveyard.length;

    setText(
        "stat-caught",
        caught
    );

    setText(
        "stat-alive",
        roster.length
    );

    setText(
        "stat-dead",
        graveyard.length
    );

    const badgeCount =
        Number(badges.count) || 0;

    setText(
        "stat-badges",
        `${badgeCount}/8`
    );
}


function setText(
    elementId,
    value
) {

    const element =
        document.getElementById(
            elementId
        );

    if (element) {

        element.textContent =
            String(value);
    }
}


function renderGraveyard(graveyard) {

    for (const grave of graveyard) {

        const nickname =
            grave.nickname;

        if (!nickname) {
            continue;
        }

        if (renderedGraves.has(nickname)) {
            continue;
        }

        renderedGraves.add(nickname);

        graveyardElement.appendChild(
            createGraveElement(grave)
        );
    }
}


function createGraveElement(grave) {

    const wrapper =
        document.createElement("div");

    wrapper.className =
        "grave grave-enter";

    const sprite =
        document.createElement("img");

    sprite.className =
        "grave-sprite";

    sprite.alt =
        escapeHTML(
            grave.species || ""
        );

    sprite.src =
        `${TEAM_SPRITES_PATH}/${grave.speciesId}.png`;

    const nickname =
        document.createElement("div");

    nickname.className =
        "grave-nickname";

    nickname.textContent =
        grave.nickname || "";

    const level =
        document.createElement("div");

    level.className =
        "grave-level";

    level.textContent =
        `Nv. ${grave.level ?? "?"}`;

    wrapper.appendChild(sprite);
    wrapper.appendChild(nickname);
    wrapper.appendChild(level);

    return wrapper;
}


/* =========================================
   ESCAPAR HTML
========================================= */

function escapeHTML(value) {

    const div =
        document.createElement(
            "div"
        );

    div.textContent =
        value ?? "";

    return div.innerHTML;
}


/* =========================================
   INICIO
========================================= */

loadNuzlocke();

setInterval(
    loadNuzlocke,
    200
);
