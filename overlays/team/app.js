const API_URL = "/api/team";
const COMBAT_API_URL = "/api/combat";
const NUZLOCKE_API_URL = "/api/nuzlocke";

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

// Delay de revelación al nacer un huevo (29/08/2026, a pedido
// del usuario): sin esto, el overlay mostraba al Pokémon real en
// el instante exacto en que el juego terminaba de escribir la
// memoria -- que puede ser ANTES de que termine la animación de
// eclosión en pantalla, adelantando el spoiler. `hatchReveals`
// guarda, por slot, un "congelado" del estado de huevo (nickname
// "Huevo", sprite genérico, todo) para seguir mostrándolo un rato
// más después de detectar que ya nació de verdad, y recién ahí
// revelar. No se toca nada del lado del backend/memoria -- es
// puramente un retraso visual en este archivo.
const HATCH_REVEAL_DELAY_MS = 9000;

let hatchReveals = [
    null,
    null,
    null,
    null,
    null,
    null
];

let loadInProgress = false;

/* =========================================
   HP DE COMBATE EN TIEMPO REAL -- DESACTIVADO
   TEMPORALMENTE (24/08/2026)

   Se comenta (no se borra) porque, sin la
   detección real de qué Pokémon está en
   combate, el overlay asumía siempre el slot 1
   -- y eso estaba afectando visualizaciones que
   ya funcionaban bien: si el Pokémon que en
   verdad estaba peleando no era el del slot 1,
   la barra de un Pokémon sano se mostraba en 0
   (o cualquier valor incorrecto) por aplicarle
   el HP de otro.

   Para reactivar esto cuando se resuelva la
   detección real del slot en combate: descomentar
   esta constante, el fetch de COMBAT_API_URL en
   loadTeam(), el parámetro `combat` en
   renderTeam()/renderSlot(), y el bloque de
   cálculo de `hp`/`inCombat` en renderSlot()
   (todos marcados con el mismo comentario).

   const COMBAT_SLOT_INDEX = 0;
========================================= */


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
   CARGAR TEAM + NUZLOCKE

   El fetch de COMBAT_API_URL queda comentado
   junto con el resto del HP de combate en
   tiempo real (ver nota arriba).
========================================= */

async function loadTeam() {

    if (loadInProgress) {
        return;
    }

    loadInProgress = true;

    try {

        const [teamResponse, nuzlockeResponse] =
            await Promise.all([
                fetch(
                    API_URL,
                    { cache: "no-store" }
                ),
                // COMBAT_API_URL -- ver nota de
                // desactivación temporal arriba.
                // fetch(
                //     COMBAT_API_URL,
                //     { cache: "no-store" }
                // ),
                fetch(
                    NUZLOCKE_API_URL,
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

        let nuzlocke = {
            graveyard: []
        };

        if (nuzlockeResponse.ok) {

            nuzlocke =
                await nuzlockeResponse.json();
        }

        const deadNicknames = new Set(
            (
                Array.isArray(nuzlocke.graveyard)
                    ? nuzlocke.graveyard
                    : []
            ).map(
                grave => grave.nickname
            )
        );

        renderTeam(team, deadNicknames);

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

function renderTeam(team, deadNicknames) {

    const currentTeam =
        normalizeTeam(team);

    for (
        let index = 0;
        index < 6;
        index++
    ) {

        const previousPokemon =
            previousTeam[index];

        const realPokemon =
            currentTeam[index];

        // ¿Acaba de nacer? (isEgg pasó de true a false en este
        // mismo Pokémon). Se arranca el temporizador UNA sola vez
        // -- si ya había uno corriendo para este slot, no se
        // reinicia por las dudas de que esta detección se repita
        // en el ciclo siguiente por algún motivo.
        const justHatched =
            !hatchReveals[index] &&
            previousPokemon &&
            previousPokemon.isEgg === true &&
            realPokemon &&
            realPokemon.isEgg === false;

        if (justHatched) {

            hatchReveals[index] = {
                revealAt:
                    Date.now() +
                    HATCH_REVEAL_DELAY_MS,
                frozenPokemon: previousPokemon,
                // Nickname YA revelado en el juego en el momento
                // de detectar la eclosión -- si para cuando se
                // cumple el delay el slot pasó a tener otro
                // Pokémon (reordenamiento del equipo, o el que
                // nació se movió de slot), se cancela el congelado
                // en vez de tapar al Pokémon equivocado.
                expectedNickname: realPokemon.nickname
            };
        }

        let displayPokemon = realPokemon;
        let displayPrevious = previousPokemon;

        const pending = hatchReveals[index];

        if (pending) {

            const identityChanged =
                !realPokemon ||
                realPokemon.nickname !==
                pending.expectedNickname;

            if (identityChanged) {

                hatchReveals[index] = null;

            } else if (Date.now() < pending.revealAt) {

                // Todavía dentro de la ventana de espera: se
                // sigue mostrando exactamente el mismo congelado
                // de huevo que ya se estaba mostrando (mismo
                // objeto como `pokemon` Y como `previous`, para
                // que renderSlot() lo trate como "sin cambios" y
                // no dispare ninguna reconstrucción/animación).
                displayPokemon =
                    pending.frozenPokemon;

                displayPrevious =
                    pending.frozenPokemon;

            } else {

                // Se cumplió el delay: se revela de verdad. Se
                // deja `displayPrevious` como el congelado de
                // huevo (no el `previousPokemon` real) para que
                // renderSlot() detecte el cambio de nickname/
                // sprite y dispare la animación de entrada, igual
                // que si hubiera pasado en este instante.
                hatchReveals[index] = null;

                displayPrevious =
                    pending.frozenPokemon;
            }
        }

        renderSlot(
            index,
            displayPokemon,
            displayPrevious,
            deadNicknames
            // COMBAT_SLOT_INDEX / combat -- ver
            // nota de desactivación temporal del
            // HP de combate al inicio del archivo.
            // ,
            // index === COMBAT_SLOT_INDEX
            //     ? combat
            //     : null
        );
    }

    previousTeam =
        currentTeam.map(
            pokemon => {

                if (!pokemon) {
                    return null;
                }

                const dead =
                    Number(pokemon.hp) <= 0 ||
                    (
                        Boolean(deadNicknames) &&
                        deadNicknames.has(
                            pokemon.nickname
                        )
                    );

                return {
                    ...pokemon,
                    _dead: dead
                };
            }
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
    deadNicknames
    // combat -- ver nota de desactivación
    // temporal del HP de combate al inicio
    // del archivo.
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

       HP DE COMBATE EN TIEMPO REAL --
       DESACTIVADO TEMPORALMENTE (24/08/2026).
       Ver nota completa al inicio del archivo.
       Mientras tanto, el HP siempre viene de
       /api/team (el HP "permanente" de la
       party), igual que fuera de combate.

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
    ================================= */

    const maxHp =
        Number(pokemon.maxHp) || 0;

    const hp =
        Number(pokemon.hp) || 0;


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


    /* Muerte visual persistente (24/08/2026): un
       Pokémon se sigue viendo debilitado aunque
       lo cures después, si su nickname ya quedó
       registrado en el cementerio del Nuzlocke
       Tracker (/api/nuzlocke -> graveyard). Antes
       esto dependía solo del HP actual y la
       apariencia de "muerto" desaparecía al curar
       -- igual comportamiento que ya tenía el
       proyecto anterior (PokeOverlay) y que se
       había perdido en esta reescritura. El chequeo
       de HP <= 0 se mantiene además del cementerio
       para que la animación de muerte dispare en
       el instante exacto (el backend tarda hasta
       un ciclo de 200ms en registrar la muerte en
       el cementerio). */

    const isDead =
        Number(pokemon.hp) <= 0 ||
        (
            Boolean(deadNicknames) &&
            deadNicknames.has(pokemon.nickname)
        );

    const wasDead =
        previous &&
        previous._dead === true;

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

        // 29/08/2026, a pedido del usuario: species_id de un
        // huevo sin nacer ya resuelve la especie REAL (el dato
        // vive en el PK6 aunque el nickname diga "Huevo") -- sin
        // esto, el overlay mostraba el sprite de la especie real
        // antes de que naciera (spoiler). sprites/0.png ya es el
        // sprite de huevo genérico (venía incluido en el pack de
        // sprites del usuario, no hizo falta agregar ninguno).
        const displaySpeciesId =
            pokemon.isEgg
                ? 0
                : Number(pokemon.speciesId);

        const spriteSize =
            getSpriteSize(
                displaySpeciesId
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
            "slot" +
            (isDead ? " dead" : "");


        slot.innerHTML = `
            <div class="sprite-wrapper${animation}">
                <img
                    class="sprite ${spriteSize}${shinyClass}${criticalClass}${deadClass}"
                    alt="${escapeHTML(
            pokemon.isEgg
                ? "Huevo"
                : (pokemon.species || "")
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
            displaySpeciesId
        );

        return;
    }


    /* ================================
       MISMO POKEMON QUE EN EL CICLO
       ANTERIOR: actualizar solo lo
       dinámico, sin tocar el <img>.
    ================================= */

    slot.classList.toggle(
        "dead",
        isDead
    );

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