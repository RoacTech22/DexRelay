const API_URL = "/api/team";
const COMBAT_API_URL = "/api/combat";

const teamElement =
    document.getElementById("team");

let previousTeam = [
    null,
    null,
    null,
    null,
    null,
    null
];

let loadInProgress = false;

/* =========================================
   SLOT QUE SE CONSIDERA "EN COMBATE"

   Por ahora se asume siempre el slot 1
   (el líder del equipo). El backend todavía
   no identifica qué Pokémon fue el enviado
   a combate (queda pendiente como bloque
   aparte: "detección del Pokémon enviado a
   combate"). Cuando eso exista, este índice
   dejará de ser fijo.
========================================= */

const COMBAT_SLOT_INDEX = 0;


/* =========================================
   CREAR LOS 6 SLOTS UNA SOLA VEZ
========================================= */

for (let index = 0; index < 6; index++) {

    const slot =
        document.createElement("div");

    slot.id =
        `slot-${index + 1}`;

    slot.className =
        "slot empty";

    teamElement.appendChild(slot);
}


/* =========================================
   CARGAR TEAM + COMBATE

   Las dos peticiones van en el mismo ciclo
   de 200ms para que la barra del slot en
   combate se actualice con el mismo ritmo
   que el resto del overlay.
========================================= */

async function loadTeam() {

    if (loadInProgress) {
        return;
    }

    loadInProgress = true;

    try {

        const [teamResponse, combatResponse] =
            await Promise.all([
                fetch(
                    API_URL,
                    { cache: "no-store" }
                ),
                fetch(
                    COMBAT_API_URL,
                    { cache: "no-store" }
                )
            ]);

        if (!teamResponse.ok) {
            throw new Error(
                `HTTP ${teamResponse.status}`
            );
        }

        const team =
            await teamResponse.json();

        let combat = {
            active: false,
            hp: null
        };

        if (combatResponse.ok) {

            combat =
                await combatResponse.json();
        }

        renderTeam(team, combat);

    } catch (error) {

        console.error(
            "Error cargando el equipo:",
            error
        );

    } finally {

        loadInProgress = false;

    }
}


/* =========================================
   NORMALIZAR LOS 6 SLOTS
========================================= */

function normalizeTeam(team) {

    const result = [
        null,
        null,
        null,
        null,
        null,
        null
    ];

    if (!Array.isArray(team)) {
        return result;
    }

    for (const pokemon of team) {

        if (!pokemon) {
            continue;
        }

        const slot =
            Number(pokemon.slot);

        if (
            slot >= 1 &&
            slot <= 6
        ) {

            if (!pokemon.empty) {

                result[slot - 1] =
                    pokemon;

            }
        }
    }

    return result;
}


/* =========================================
   RENDERIZAR TEAM
========================================= */

function renderTeam(team, combat) {

    const currentTeam =
        normalizeTeam(team);

    for (
        let index = 0;
        index < 6;
        index++
    ) {

        renderSlot(
            index,
            currentTeam[index],
            previousTeam[index],
            index === COMBAT_SLOT_INDEX
                ? combat
                : null
        );
    }

    previousTeam =
        currentTeam.map(
            pokemon =>
                pokemon
                    ? { ...pokemon }
                    : null
        );
}


/* =========================================
   RENDER SLOT

   IMPORTANTE: esta función NO reconstruye
   el <img> del sprite en cada ciclo. Solo lo
   recrea cuando el Pokémon del slot cambió
   de verdad (nueva especie, evolución, o
   entra desde vacío). Si es el mismo
   Pokémon que en el ciclo anterior, solo se
   actualizan HP y nivel.

   Por qué importa: reasignar innerHTML con
   un nuevo <img src="..."> cancela cualquier
   descarga de esa imagen que estuviera en
   curso y la reinicia desde cero. Como
   loadTeam() corre cada 200ms, hacerlo en
   cada ciclo (incluso sin cambios reales)
   podía cancelar una y otra vez la descarga
   de los sprites que tardaban más en llegar
   (típicamente los últimos slots), dejándolos
   sin mostrarse de forma intermitente.
========================================= */

function renderSlot(
    index,
    pokemon,
    previous,
    combat
) {

    const slot =
        document.getElementById(
            `slot-${index + 1}`
        );


    if (!slot) {
        return;
    }


    /* ================================
       SLOT VACÍO
    ================================= */

    if (!pokemon) {

        if (slot.className !== "slot empty") {

            slot.className =
                "slot empty";

            slot.innerHTML =
                "";
        }

        return;
    }


    /* ================================
       DATOS

       Fuera de combate, el HP viene de
       /api/team como siempre. Si este
       slot es el que está en combate
       (combat.active === true), se usa
       el HP realtime de /api/combat en
       su lugar para que la barra baje
       en pasos reales (31 → 24 → 18 → 3)
       en vez de saltar directo al valor
       final que reporta la party al
       terminar el combate.

       Importante: esto NO modifica
       pokemon.hp ni el HP "permanente"
       de la party, solo lo que se
       calcula aquí para pintar la barra.
    ================================= */

    const maxHp =
        Number(pokemon.maxHp) || 0;

    const inCombat =
        Boolean(combat) &&
        combat.active === true &&
        combat.hp !== null &&
        combat.hp !== undefined;

    const hp =
        inCombat
            ? Math.max(
                0,
                Math.min(
                    maxHp || Number(combat.hp),
                    Number(combat.hp)
                )
            )
            : Number(pokemon.hp) || 0;


    const hpPercent =
        maxHp > 0
            ? Math.max(
                0,
                Math.min(
                    100,
                    (hp / maxHp) * 100
                )
            )
            : 0;


    let hpColor;

    if (hpPercent > 50) {

        hpColor =
            "#20C878";

    } else if (hpPercent > 20) {

        hpColor =
            "#F2C94C";

    } else {

        hpColor =
            "#E74C3C";
    }


    const critical =
        hpPercent > 0 &&
        hpPercent <= 20;


    /* ================================
       CAMBIOS

       Todas estas comparaciones usan el HP
       "real" de la party (pokemon.hp), no el
       valor de `hp` calculado arriba (que
       puede venir de /api/combat mientras el
       slot está en combate). La muerte es un
       estado de la party, no algo que deba
       depender del HP en vivo de una pelea que
       todavía no terminó de sincronizarse.
    ================================= */

    const samePokemon =
        previous &&
        previous.nickname ===
        pokemon.nickname &&
        previous.speciesId ===
        pokemon.speciesId;


    /* Una evolución cambia speciesId pero
       sigue siendo el mismo Pokémon: por eso
       el nickname tiene que coincidir. Sin
       este chequeo, reordenar el equipo y que
       otro Pokémon (con otro nickname) ocupe
       el slot con una especie distinta se
       confundía con una evolución. */
    const evolved =
        previous &&
        previous.nickname ===
        pokemon.nickname &&
        previous.speciesId !==
        pokemon.speciesId;


    const levelUp =
        samePokemon &&
        Number(pokemon.level) >
        Number(previous.level);


    /* Un Pokémon distinto (otro nickname) pasó a
       ocupar este slot -- típicamente al reordenar
       el equipo en el menú. No es evolución ni
       muerte, pero sigue siendo una entrada real y
       debería animarse igual que cuando el slot
       venía vacío. */
    const changed =
        previous &&
        previous.nickname !==
        pokemon.nickname;


    const isDead =
        Number(pokemon.hp) <= 0;

    const wasDead =
        previous &&
        Number(previous.hp) <= 0;

    /* Debilitarse NO cambia nickname ni
       speciesId, así que `samePokemon` sigue
       siendo true y normalmente no se
       reconstruiría el slot. `died` fuerza esa
       reconstrucción para poder disparar la
       animación en el momento exacto. */
    const died =
        isDead &&
        !wasDead;


    /* ================================
       ¿HACE FALTA RECONSTRUIR EL SPRITE?

       Solo si es un Pokémon distinto al
       que ya estaba en este slot, si el
       slot todavía no tiene la estructura
       montada (primera vez / venía vacío),
       o si el Pokémon se acaba de debilitar
       (para poder disparar la animación de
       muerte).
    ================================= */

    const needsRebuild =
        !samePokemon ||
        died ||
        !slot.querySelector(".sprite");


    if (needsRebuild) {

        const spriteSize =
            getSpriteSize(
                Number(pokemon.speciesId)
            );


        const shinyClass =
            pokemon.shiny
                ? " shiny"
                : "";


        const criticalClass =
            critical
                ? " hp-critical"
                : "";


        const deadClass =
            isDead
                ? " nuzlocke-dead"
                : "";


        let animation = "";

        if (evolved) {

            animation =
                " sprite-wrapper-evolution";

        } else if (died) {

            animation =
                " sprite-wrapper-death";

        } else if (!previous || changed) {

            animation =
                " sprite-wrapper-enter";
        }


        const levelAnimation =
            levelUp
                ? " level-levelup"
                : "";


        slot.className =
            "slot";


        slot.innerHTML = `
            <div class="sprite-wrapper${animation}">
                <img
                    class="sprite ${spriteSize}${shinyClass}${criticalClass}${deadClass}"
                    alt="${escapeHTML(
            pokemon.species || ""
        )}"
                >
            </div>

            <div class="nickname">
                ${escapeHTML(
            pokemon.nickname || ""
        )}
            </div>

            <div class="level${levelAnimation}">
                Lv. ${pokemon.level}
            </div>

            <div class="hp-container">
                <div
                    class="hp-bar"
                    style="
                        width: ${hpPercent}%;
                        background: ${hpColor};
                    "
                ></div>
            </div>
        `;

        const spriteImg =
            slot.querySelector(".sprite");

        loadSpriteWithRetry(
            spriteImg,
            pokemon.speciesId
        );

        return;
    }


    /* ================================
       MISMO POKEMON QUE EN EL CICLO
       ANTERIOR: actualizar solo lo
       dinámico, sin tocar el <img>.
    ================================= */

    const img =
        slot.querySelector(".sprite");

    if (img) {

        img.classList.toggle(
            "hp-critical",
            critical
        );

        img.classList.toggle(
            "nuzlocke-dead",
            isDead
        );
    }


    const levelDiv =
        slot.querySelector(".level");

    if (levelDiv) {

        levelDiv.textContent =
            `Lv. ${pokemon.level}`;

        levelDiv.classList.toggle(
            "level-levelup",
            levelUp
        );
    }


    const hpBar =
        slot.querySelector(".hp-bar");

    if (hpBar) {

        hpBar.style.width =
            `${hpPercent}%`;

        hpBar.style.background =
            hpColor;
    }
}


/* =========================================
   CARGA DE SPRITE CON REINTENTOS

   Algunas cargas de imagen fallan de forma
   intermitente (el navegador dispara varias
   peticiones de sprite casi al mismo tiempo,
   y alguna puede no responder a tiempo,
   sobre todo en el navegador embebido de OBS).
   Si el <img> falla, reintentamos unas pocas
   veces con un pequeño retraso antes de darnos
   por vencidos, en vez de dejar el ícono de
   imagen rota hasta el próximo refresh manual.
========================================= */

function loadSpriteWithRetry(
    img,
    speciesId,
    attempt = 0
) {

    if (!img) {
        return;
    }

    const MAX_ATTEMPTS = 4;

    img.onerror = () => {

        if (attempt >= MAX_ATTEMPTS) {

            console.error(
                `No se pudo cargar el sprite ${speciesId} tras ${MAX_ATTEMPTS} intentos.`
            );

            return;
        }

        setTimeout(() => {

            img.src =
                `sprites/${speciesId}.png?retry=${attempt + 1}`;

            loadSpriteWithRetry(
                img,
                speciesId,
                attempt + 1
            );

        }, 250 * (attempt + 1));
    };

    img.src =
        `sprites/${speciesId}.png`;
}


/* =========================================
   TAMAÑOS DE SPRITES
========================================= */

function getSpriteSize(
    speciesId
) {

    const small = [
        172,
        280,
        360,
        447,
        506,
        661,
        396
    ];

    const large = [
        130,
        373,
        376,
        384,
        382
    ];

    const huge = [
        321,
        383
    ];


    if (
        small.includes(speciesId)
    ) {
        return "sprite-small";
    }


    if (
        huge.includes(speciesId)
    ) {
        return "sprite-huge";
    }


    if (
        large.includes(speciesId)
    ) {
        return "sprite-large";
    }


    return "sprite-normal";
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

loadTeam();

setInterval(
    loadTeam,
    200
);