const ENCOUNTERS_API_URL = "/api/nuzlocke/encounters";
const PENDING_API_URL = "/api/nuzlocke/pending-encounters";
const ASSIGN_API_URL = "/api/nuzlocke/encounters/assign";
const SPECIES_API_URL = "/api/species";
const LOCATIONS_API_URL = "/api/locations";

const VALID_STATUSES = [
    "sin_intentar",
    "capturado",
    "perdido",
    "muerto",
    "intercambiado",
    "regalo",
    "shiny"
];

const STATUS_LABELS = {
    sin_intentar: "Sin intentar",
    capturado: "Capturado",
    perdido: "Perdido",
    muerto: "Muerto",
    intercambiado: "Intercambiado",
    regalo: "Regalo",
    shiny: "Shiny"
};

/* Se completa en loadLocationList() con la lista oficial que
   devuelve PKHeX (/api/locations) -- la MISMA fuente que usa la
   detección automática para resolver el lugar de encuentro real,
   así los nombres coinciden siempre y una captura nueva encuentra
   su fila existente en vez de crear una duplicada.

   "Inicial" es una excepción: no es un lugar real del juego, es
   una marca propia de DexRelay para el primer Pokémon obtenido en
   la partida (ver nuzlocke_service.py). Va fija de primera en la
   lista. */
let DEFAULT_LOCATIONS = ["Inicial"];

const tableBody =
    document.getElementById("encounters-body");

const pendingList =
    document.getElementById("pending-list");

// Catálogo completo de especies, cargado una vez al iniciar
// (ver loadSpeciesList()). Usado por el buscador propio de cada
// fila (species-picker) -- reemplaza al <datalist> nativo del
// navegador, que resultaba poco confiable para mostrar
// sugerencias de forma consistente.
let speciesCatalog = [];
let speciesIdByLowerName = new Map();

const newLocationInput =
    document.getElementById("new-location-input");

const addRowButton =
    document.getElementById("add-row-button");


/* =========================================
   BÚSQUEDA DE FILA POR UBICACIÓN (normalizada)

   El lugar de encuentro que devuelve PKHeX podría no coincidir
   caracter por caracter con el texto de DEFAULT_LOCATIONS (ej.
   espacios extra, mayúsculas distintas). Comparar normalizado
   (minúsculas + sin espacios de más) evita crear una fila
   duplicada para lo que en realidad es la misma ruta.
========================================= */

function normalizeLocation(text) {

    return (text || "")
        .trim()
        .toLowerCase()
        .replace(/\s+/g, " ");
}


function findRowByLocation(location) {

    const targetKey =
        normalizeLocation(location);

    return Array.from(
        tableBody.children
    ).find(
        row =>
            normalizeLocation(
                row.dataset.location
            ) === targetKey
    ) || null;
}


/* =========================================
   BUSCADOR DE ESPECIE (sprite + input + lista
   de sugerencias propia)

   Reemplaza al <datalist> nativo del navegador -- resultó poco
   confiable para mostrar sugerencias de forma consistente.
   Reutiliza los sprites que ya existen en overlays/team/sprites/
   (ruta absoluta /overlay/team/sprites/{id}.png) en vez de pedir
   un set de imágenes aparte para el panel.
========================================= */

function createSpeciesPicker(initialValue) {

    const wrapper =
        document.createElement("div");

    wrapper.className = "species-picker";

    const sprite =
        document.createElement("img");

    sprite.className = "species-sprite";
    sprite.alt = "";

    sprite.addEventListener("error", () => {
        sprite.classList.remove("visible");
    });

    const input =
        document.createElement("input");

    input.type = "text";
    input.className = "species-input";
    input.placeholder = "Especie...";
    input.autocomplete = "off";
    input.value = initialValue;

    const suggestions =
        document.createElement("div");

    suggestions.className =
        "species-suggestions";

    wrapper.appendChild(sprite);
    wrapper.appendChild(input);
    wrapper.appendChild(suggestions);

    function updateSprite(name) {

        const speciesId =
            speciesIdByLowerName.get(
                (name || "").trim().toLowerCase()
            );

        if (speciesId) {

            sprite.src =
                `/overlay/team/sprites/${speciesId}.png`;

            sprite.classList.add("visible");

        } else {

            sprite.classList.remove("visible");
            sprite.removeAttribute("src");
        }
    }

    function renderSuggestions(query) {

        suggestions.innerHTML = "";

        const trimmed =
            query.trim().toLowerCase();

        if (!trimmed) {
            suggestions.classList.remove(
                "visible"
            );
            return;
        }

        const matches = speciesCatalog
            .filter(
                entry =>
                    entry.name
                        .toLowerCase()
                        .includes(trimmed)
            )
            .slice(0, 8);

        if (matches.length === 0) {
            suggestions.classList.remove(
                "visible"
            );
            return;
        }

        for (const entry of matches) {

            const item =
                document.createElement("div");

            item.className =
                "species-suggestion-item";

            item.textContent = entry.name;

            // "mousedown", no "click": se dispara ANTES de que
            // el input pierda el foco, asi la seleccion se
            // procesa antes de que la lista se oculte por el
            // blur. preventDefault() evita que el click le robe
            // el foco al input a mitad de camino; el blur()
            // explicito de abajo sigue disparando el guardado
            // normal (el listener de "blur" que ya tiene el
            // input en addRow).
            item.addEventListener(
                "mousedown",
                event => {

                    event.preventDefault();

                    input.value = entry.name;

                    updateSprite(entry.name);

                    suggestions.classList.remove(
                        "visible"
                    );

                    input.blur();
                }
            );

            suggestions.appendChild(item);
        }

        suggestions.classList.add("visible");
    }

    input.addEventListener("input", () => {
        renderSuggestions(input.value);
        updateSprite(input.value);
    });

    input.addEventListener("focus", () => {

        if (input.value.trim()) {
            renderSuggestions(input.value);
        }
    });

    input.addEventListener("blur", () => {

        // Pequeño margen para no ocultar la lista justo antes
        // de que el mousedown de una sugerencia llegue a
        // procesarse.
        setTimeout(() => {
            suggestions.classList.remove(
                "visible"
            );
        }, 100);
    });

    updateSprite(initialValue);

    return {
        wrapper,
        input,
        spriteImg: sprite
    };
}


/* =========================================
   INICIO
========================================= */

async function init() {

    await loadSpeciesList();
    await loadLocationList();

    const existing =
        await loadEncounters();

    const existingByLocation = new Map(
        existing.map(
            entry => [entry.location, entry]
        )
    );

    const renderedLocations = new Set();

    for (const location of DEFAULT_LOCATIONS) {

        addRow(
            location,
            existingByLocation.get(location)
        );

        renderedLocations.add(location);
    }

    // Ubicaciones guardadas que no están en la lista por
    // defecto (agregadas a mano en una sesión anterior).
    for (const entry of existing) {

        if (renderedLocations.has(entry.location)) {
            continue;
        }

        addRow(entry.location, entry);

        renderedLocations.add(entry.location);
    }

    await refreshPending();

    // La mayoría de las capturas ahora se completan solas
    // (especie + nickname + ruta + shiny, vía PKHeX). Este
    // refresh solo importa para el puñado de casos que no se
    // pudieron resolver automático (huevos, regalos,
    // intercambios). Se refresca cada 3s sin que haga falta
    // recargar la página.
    setInterval(refreshPending, 3000);

    // Las filas de la tabla también pueden llenarse solas
    // (captura automática con ruta ya resuelta) mientras el
    // panel está abierto -- se refrescan igual, sin pisar lo
    // que el usuario esté editando en ese momento.
    setInterval(refreshEncounters, 3000);
}


async function loadSpeciesList() {

    try {

        const response =
            await fetch(
                SPECIES_API_URL,
                { cache: "no-store" }
            );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        const data =
            await response.json();

        speciesCatalog =
            Array.isArray(data.species)
                ? data.species
                : [];

        speciesIdByLowerName = new Map(
            speciesCatalog.map(
                entry => [
                    entry.name.toLowerCase(),
                    entry.id
                ]
            )
        );

    } catch (error) {

        console.error(
            "Error cargando el catálogo de especies:",
            error
        );
    }
}


async function loadLocationList() {

    try {

        const response =
            await fetch(
                LOCATIONS_API_URL,
                { cache: "no-store" }
            );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        const data =
            await response.json();

        const fetched =
            Array.isArray(data.locations)
                ? data.locations
                    .map(entry => entry.name)
                    .filter(Boolean)
                : [];

        // "Inicial" siempre primero, después la lista oficial
        // que devuelve PKHeX. Si el bridge todavía no respondió
        // (arrancando) o falló, se queda solo con "Inicial" --
        // igual se puede usar el botón "Agregar" mientras tanto.
        DEFAULT_LOCATIONS = [
            "Inicial",
            ...fetched
        ];

    } catch (error) {

        console.error(
            "Error cargando el catálogo de ubicaciones:",
            error
        );
    }
}


async function loadEncounters() {

    try {

        const response =
            await fetch(
                ENCOUNTERS_API_URL,
                { cache: "no-store" }
            );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        const data =
            await response.json();

        return Array.isArray(data.encounters)
            ? data.encounters
            : [];

    } catch (error) {

        console.error(
            "Error cargando encuentros:",
            error
        );

        return [];
    }
}


async function refreshEncounters() {

    // Evita pisar un <input> que el usuario tenga enfocado
    // justo cuando cae el refresh automático.
    if (
        document.activeElement &&
        (
            document.activeElement.classList.contains(
                "species-input"
            ) ||
            document.activeElement.classList.contains(
                "nickname-input"
            )
        )
    ) {
        return;
    }

    const encounters =
        await loadEncounters();

    for (const entry of encounters) {

        updateRowFromAssignment(
            entry.location,
            { encounters: [entry] }
        );
    }
}


/* =========================================
   FILAS DE LA TABLA
========================================= */

function addRow(location, existingEntry) {

    const row =
        document.createElement("tr");

    row.dataset.location = location;

    const locationCell =
        document.createElement("td");

    locationCell.className =
        "location-cell";

    const locationLabel =
        document.createElement("div");

    locationLabel.className =
        "location-label";

    locationLabel.textContent =
        location;

    locationCell.appendChild(locationLabel);

    const resetButton =
        document.createElement("button");

    resetButton.type = "button";
    resetButton.className = "reset-button";
    resetButton.title =
        "Eliminar este encuentro y el Pokémon " +
        "capturado ahí";
    resetButton.textContent = "✕";

    resetButton.addEventListener(
        "click",
        () => resetLocation(location, row)
    );

    locationCell.appendChild(resetButton);


    const nicknameCell =
        document.createElement("td");

    const nicknameInput =
        document.createElement("input");

    nicknameInput.type = "text";
    nicknameInput.className = "nickname-input";
    nicknameInput.placeholder = "Nickname...";

    nicknameInput.value =
        existingEntry?.nickname || "";

    nicknameCell.appendChild(nicknameInput);


    const speciesCell =
        document.createElement("td");

    const speciesPicker =
        createSpeciesPicker(
            existingEntry?.species || ""
        );

    speciesCell.appendChild(
        speciesPicker.wrapper
    );

    const speciesInput =
        speciesPicker.input;


    const statusCell =
        document.createElement("td");

    const statusSelect =
        document.createElement("select");

    statusSelect.className =
        "status-select";

    for (const value of VALID_STATUSES) {

        const option =
            document.createElement("option");

        option.value = value;
        option.textContent = STATUS_LABELS[value];

        statusSelect.appendChild(option);
    }

    statusSelect.value =
        existingEntry?.status || "sin_intentar";

    applyStatusClass(
        statusSelect,
        statusSelect.value
    );

    statusCell.appendChild(statusSelect);


    row.appendChild(locationCell);
    row.appendChild(nicknameCell);
    row.appendChild(speciesCell);
    row.appendChild(statusCell);

    tableBody.appendChild(row);


    /* ================================
       AUTOGUARDADO
    ================================= */

    nicknameInput.addEventListener(
        "blur",
        () => saveRow(
            row,
            location,
            nicknameInput,
            speciesInput,
            statusSelect
        )
    );

    speciesInput.addEventListener(
        "blur",
        () => saveRow(
            row,
            location,
            nicknameInput,
            speciesInput,
            statusSelect
        )
    );

    statusSelect.addEventListener(
        "change",
        () => {

            applyStatusClass(
                statusSelect,
                statusSelect.value
            );

            saveRow(
                row,
                location,
                nicknameInput,
                speciesInput,
                statusSelect
            );
        }
    );
}


function applyStatusClass(
    selectElement,
    status
) {

    for (const value of VALID_STATUSES) {

        selectElement.classList.remove(
            `status-${value}`
        );
    }

    selectElement.classList.add(
        `status-${status}`
    );
}


async function saveRow(
    row,
    location,
    nicknameInput,
    speciesInput,
    statusSelect
) {

    // Solo se guarda cuando hay nickname Y especie -- antes
    // cualquier click en un input vacío (foco + blur, sin
    // escribir nada) creaba un registro "fantasma" con los
    // campos en blanco. El estado siempre tiene un valor por
    // defecto (sin_intentar), así que no cuenta como "campo
    // lleno" a los efectos de esta validación.
    if (
        !nicknameInput.value.trim() ||
        !speciesInput.value.trim()
    ) {
        return;
    }

    try {

        const response =
            await fetch(
                ENCOUNTERS_API_URL,
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    body: JSON.stringify({
                        location,
                        nickname: nicknameInput.value,
                        species: speciesInput.value,
                        status: statusSelect.value
                    })
                }
            );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        flashSaved(row);

    } catch (error) {

        console.error(
            "Error guardando encuentro:",
            error
        );
    }
}


function flashSaved(row) {

    row.classList.remove("saved-flash");

    // Fuerza un reflow para poder retriggerear la
    // animación si se guarda dos veces seguidas.
    void row.offsetWidth;

    row.classList.add("saved-flash");
}


/* =========================================
   RESETEAR UNA RUTA

   Borra el encuentro Y el Pokémon capturado ahí (roster/
   cementerio incluidos, ver NuzlockeService.delete_encounter).
   La fila NO se elimina de la tabla -- es una ruta real del
   juego, sigue disponible para una futura captura -- solo se
   limpia de vuelta a "sin_intentar".
========================================= */

async function resetLocation(location, row) {

    const confirmed = window.confirm(
        `¿Eliminar el encuentro de "${location}" y el ` +
        `Pokémon capturado ahí? Esta acción no se puede ` +
        `deshacer.`
    );

    if (!confirmed) {
        return;
    }

    try {

        const response =
            await fetch(
                "/api/nuzlocke/encounters/delete",
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    body: JSON.stringify({ location })
                }
            );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        const nicknameInput =
            row.querySelector(".nickname-input");

        const speciesInput =
            row.querySelector(".species-input");

        const spriteImg =
            row.querySelector(".species-sprite");

        const statusSelect =
            row.querySelector(".status-select");

        if (nicknameInput) {
            nicknameInput.value = "";
        }

        if (speciesInput) {
            speciesInput.value = "";
        }

        if (spriteImg) {
            spriteImg.classList.remove("visible");
            spriteImg.removeAttribute("src");
        }

        if (statusSelect) {
            statusSelect.value = "sin_intentar";
            applyStatusClass(
                statusSelect,
                "sin_intentar"
            );
        }

        flashSaved(row);

    } catch (error) {

        console.error(
            "Error eliminando encuentro:",
            error
        );
    }
}


/* =========================================
   CAPTURAS PENDIENTES DE RUTA

   Solo aparecen acá las que PKHeX NO pudo resolver solas
   (huevos, regalos, intercambios, o si el bridge falló). La
   mayoría de las capturas normales ya se completan directo en
   la tabla, sin pasar por esta sección.
========================================= */

async function refreshPending() {

    const pending =
        await loadPendingEncounters();

    renderPending(pending);
}


async function loadPendingEncounters() {

    try {

        const response =
            await fetch(
                PENDING_API_URL,
                { cache: "no-store" }
            );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        const data =
            await response.json();

        return Array.isArray(
            data.pending_encounters
        )
            ? data.pending_encounters
            : [];

    } catch (error) {

        console.error(
            "Error cargando capturas pendientes:",
            error
        );

        return [];
    }
}


function renderPending(pending) {

    const currentNicknames = new Set(
        pending.map(entry => entry.nickname)
    );

    // No reconstruir tarjetas que ya estaban (evita perder el
    // <select> a medio elegir si el usuario está por confirmar
    // justo cuando cae el refresh de 3s).
    for (const card of Array.from(
        pendingList.children
    )) {

        if (
            !currentNicknames.has(
                card.dataset.nickname
            )
        ) {
            card.remove();
        }
    }

    for (const entry of pending) {

        const alreadyRendered =
            pendingList.querySelector(
                `[data-nickname="${
                    CSS.escape(entry.nickname)
                }"]`
            );

        if (alreadyRendered) {
            continue;
        }

        pendingList.appendChild(
            createPendingCard(entry)
        );
    }
}


function createPendingCard(entry) {

    const card =
        document.createElement("div");

    card.className = "pending-card";
    card.dataset.nickname = entry.nickname;

    const info =
        document.createElement("div");

    info.className = "pending-info";

    const shinyTag =
        entry.shiny
            ? " ✨"
            : "";

    info.innerHTML =
        `<strong>${
            escapeHTML(entry.species || "")
        }</strong> (${
            escapeHTML(entry.nickname || "")
        })${shinyTag} -- no se pudo resolver la ruta sola, ` +
        `¿en qué ruta lo atrapaste?`;

    const select =
        document.createElement("select");

    select.className = "pending-select";

    const blankOption =
        document.createElement("option");

    blankOption.value = "";
    blankOption.textContent = "Elegir ruta...";

    select.appendChild(blankOption);

    for (const location of DEFAULT_LOCATIONS) {

        const option =
            document.createElement("option");

        option.value = location;
        option.textContent = location;

        select.appendChild(option);
    }

    const button =
        document.createElement("button");

    button.type = "button";
    button.className = "pending-assign-button";
    button.textContent = "Asignar";
    button.disabled = true;

    select.addEventListener(
        "change",
        () => {
            button.disabled =
                !select.value;
        }
    );

    button.addEventListener(
        "click",
        () => assignPending(
            entry.nickname,
            select.value,
            card
        )
    );

    card.appendChild(info);
    card.appendChild(select);
    card.appendChild(button);

    return card;
}


async function assignPending(
    nickname,
    location,
    card
) {

    if (!location) {
        return;
    }

    try {

        const response =
            await fetch(
                ASSIGN_API_URL,
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    body: JSON.stringify({
                        nickname,
                        location
                    })
                }
            );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        card.remove();

        // La ruta recién asignada ya tiene esta especie/estado
        // -- refleja eso en la tabla sin esperar al próximo poll.
        updateRowFromAssignment(
            location,
            await response.json()
        );

    } catch (error) {

        console.error(
            "Error asignando ruta:",
            error
        );
    }
}


function updateRowFromAssignment(
    location,
    responseData
) {

    const encounters =
        Array.isArray(responseData.encounters)
            ? responseData.encounters
            : [];

    const savedEntry =
        encounters.find(
            entry => entry.location === location
        );

    if (!savedEntry) {
        return;
    }

    const row =
        findRowByLocation(location);

    if (!row) {

        // La ruta no estaba en la lista por defecto ni ya
        // renderizada (caso raro: se asignó a una ubicación
        // completamente nueva). Se agrega como fila nueva.
        addRow(location, savedEntry);
        return;
    }

    const nicknameInput =
        row.querySelector(".nickname-input");

    const speciesInput =
        row.querySelector(".species-input");

    const statusSelect =
        row.querySelector(".status-select");

    let changed = false;

    if (
        nicknameInput &&
        document.activeElement !== nicknameInput
    ) {

        const newValue = savedEntry.nickname || "";

        if (nicknameInput.value !== newValue) {
            nicknameInput.value = newValue;
            changed = true;
        }
    }

    if (
        speciesInput &&
        document.activeElement !== speciesInput
    ) {

        const newValue = savedEntry.species || "";

        if (speciesInput.value !== newValue) {

            speciesInput.value = newValue;

            const spriteImg =
                row.querySelector(".species-sprite");

            if (spriteImg) {

                const speciesId =
                    speciesIdByLowerName.get(
                        newValue.trim().toLowerCase()
                    );

                if (speciesId) {

                    spriteImg.src =
                        `/overlay/team/sprites/${speciesId}.png`;

                    spriteImg.classList.add(
                        "visible"
                    );

                } else {

                    spriteImg.classList.remove(
                        "visible"
                    );

                    spriteImg.removeAttribute(
                        "src"
                    );
                }
            }

            changed = true;
        }
    }

    if (statusSelect) {

        const newValue =
            savedEntry.status || "sin_intentar";

        if (statusSelect.value !== newValue) {

            statusSelect.value = newValue;

            applyStatusClass(
                statusSelect,
                statusSelect.value
            );

            changed = true;
        }
    }

    // Solo se resalta la fila cuando algo cambió de verdad --
    // antes se disparaba en cada refresh automático (cada 3s)
    // aunque los datos fueran exactamente los mismos, lo que se
    // veía como un parpadeo azul constante en toda la tabla.
    if (changed) {
        flashSaved(row);
    }
}


/* =========================================
   AGREGAR UBICACIÓN NUEVA
========================================= */

addRowButton.addEventListener(
    "click",
    () => {

        const location =
            newLocationInput.value.trim();

        if (!location) {
            return;
        }

        const alreadyExists =
            Boolean(
                findRowByLocation(location)
            );

        if (alreadyExists) {
            newLocationInput.value = "";
            return;
        }

        addRow(location, null);

        newLocationInput.value = "";

        // Persistir la ubicación nueva de una vez, para
        // que sobreviva un refresh de la página aunque
        // todavía no se haya cargado nada ahí.
        const newRow =
            tableBody.lastElementChild;

        const nicknameInput =
            newRow.querySelector(
                ".nickname-input"
            );

        const speciesInput =
            newRow.querySelector(
                ".species-input"
            );

        const statusSelect =
            newRow.querySelector(
                ".status-select"
            );

        saveRow(
            newRow,
            location,
            nicknameInput,
            speciesInput,
            statusSelect
        );
    }
);

newLocationInput.addEventListener(
    "keydown",
    event => {

        if (event.key === "Enter") {
            addRowButton.click();
        }
    }
);


/* =========================================
   ESCAPAR HTML
========================================= */

function escapeHTML(value) {

    const div =
        document.createElement("div");

    div.textContent =
        value ?? "";

    return div.innerHTML;
}


init();
