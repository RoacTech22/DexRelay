const ENCOUNTERS_API_URL = "/api/nuzlocke/encounters";
const PENDING_API_URL = "/api/nuzlocke/pending-encounters";
const ASSIGN_API_URL = "/api/nuzlocke/encounters/assign";

const VALID_RESULTS = [
    "sin_intentar",
    "atrapado",
    "perdido"
];

const RESULT_LABELS = {
    sin_intentar: "Sin intentar",
    atrapado: "Atrapado",
    perdido: "Perdido"
};

/* Orden principal de rutas/ciudades de ORAS (progresión de
   historia). No es 100% exhaustivo (no cubre cada cueva lateral) --
   lo que falte se agrega a mano con "Agregar" al final de la
   tabla. */
const DEFAULT_LOCATIONS = [
    "Ruta 101",
    "Ruta 102",
    "Ruta 103",
    "Petalburg City",
    "Ruta 104",
    "Petalburg Woods",
    "Rustboro City",
    "Ruta 105",
    "Ruta 116",
    "Rusturf Tunnel",
    "Dewford Town",
    "Ruta 106",
    "Ruta 107",
    "Ruta 108",
    "Ruta 109",
    "Slateport City",
    "Ruta 110",
    "Ruta 111",
    "Ruta 112",
    "Fallarbor Town",
    "Ruta 113",
    "Ruta 114",
    "Meteor Falls",
    "Ruta 115",
    "Mauville City",
    "Ruta 117",
    "Verdanturf Town",
    "Ruta 118",
    "Ruta 119",
    "Fortree City",
    "Ruta 120",
    "Ruta 121",
    "Ruta 122",
    "Ruta 123",
    "Lilycove City",
    "Ruta 124",
    "Ruta 125",
    "Ruta 126",
    "Ruta 127",
    "Ruta 128",
    "Mossdeep City",
    "Ruta 129",
    "Ruta 130",
    "Ruta 131",
    "Pacifidlog Town",
    "Ruta 132",
    "Ruta 133",
    "Ruta 134",
    "Sootopolis City",
    "Ever Grande City",
    "Victory Road"
];

const tableBody =
    document.getElementById("encounters-body");

const pendingList =
    document.getElementById("pending-list");

const newLocationInput =
    document.getElementById("new-location-input");

const addRowButton =
    document.getElementById("add-row-button");


/* =========================================
   INICIO
========================================= */

async function init() {

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

    // Las capturas nuevas se detectan solas mientras juegas --
    // el panel se refresca cada 3s para mostrarlas sin que haga
    // falta recargar la página a mano. No hace falta más
    // frecuencia que esa: es una lista que cambia cuando el
    // jugador atrapa algo, no algo animado en vivo.
    setInterval(refreshPending, 3000);
}


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

    info.innerHTML =
        `<strong>${
            escapeHTML(entry.species || "")
        }</strong> (${
            escapeHTML(entry.nickname || "")
        }) -- ¿en qué ruta lo atrapaste?`;

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

        // La ruta recién asignada ya tiene esta especie/resultado
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
        tableBody.querySelector(
            `tr[data-location="${
                CSS.escape(location)
            }"]`
        );

    if (!row) {

        // La ruta no estaba en la lista por defecto ni ya
        // renderizada (caso raro: se asignó a una ubicación
        // completamente nueva). Se agrega como fila nueva.
        addRow(location, savedEntry);
        return;
    }

    const speciesInput =
        row.querySelector(".species-input");

    const resultSelect =
        row.querySelector(".result-select");

    if (speciesInput) {
        speciesInput.value =
            savedEntry.species || "";
    }

    if (resultSelect) {
        resultSelect.value =
            savedEntry.result || "sin_intentar";

        applyResultClass(
            resultSelect,
            resultSelect.value
        );
    }

    flashSaved(row);
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


/* =========================================
   FILAS
========================================= */

function addRow(location, existingEntry) {

    const row =
        document.createElement("tr");

    row.dataset.location = location;

    const locationCell =
        document.createElement("td");

    const locationLabel =
        document.createElement("div");

    locationLabel.className =
        "location-label";

    locationLabel.textContent =
        location;

    locationCell.appendChild(locationLabel);


    const speciesCell =
        document.createElement("td");

    const speciesInput =
        document.createElement("input");

    speciesInput.type = "text";
    speciesInput.className = "species-input";
    speciesInput.placeholder = "Especie...";

    speciesInput.value =
        existingEntry?.species || "";

    speciesCell.appendChild(speciesInput);


    const resultCell =
        document.createElement("td");

    const resultSelect =
        document.createElement("select");

    resultSelect.className =
        "result-select";

    for (const value of VALID_RESULTS) {

        const option =
            document.createElement("option");

        option.value = value;
        option.textContent = RESULT_LABELS[value];

        resultSelect.appendChild(option);
    }

    resultSelect.value =
        existingEntry?.result || "sin_intentar";

    applyResultClass(
        resultSelect,
        resultSelect.value
    );

    resultCell.appendChild(resultSelect);


    row.appendChild(locationCell);
    row.appendChild(speciesCell);
    row.appendChild(resultCell);

    tableBody.appendChild(row);


    /* ================================
       AUTOGUARDADO
    ================================= */

    speciesInput.addEventListener(
        "blur",
        () => saveRow(
            row,
            location,
            speciesInput,
            resultSelect
        )
    );

    resultSelect.addEventListener(
        "change",
        () => {

            applyResultClass(
                resultSelect,
                resultSelect.value
            );

            saveRow(
                row,
                location,
                speciesInput,
                resultSelect
            );
        }
    );
}


function applyResultClass(
    selectElement,
    result
) {

    for (const value of VALID_RESULTS) {

        selectElement.classList.remove(
            `result-${value}`
        );
    }

    selectElement.classList.add(
        `result-${result}`
    );
}


async function saveRow(
    row,
    location,
    speciesInput,
    resultSelect
) {

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
                        species: speciesInput.value,
                        result: resultSelect.value
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
                tableBody.querySelector(
                    `tr[data-location="${
                        CSS.escape(location)
                    }"]`
                )
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

        const speciesInput =
            newRow.querySelector(
                ".species-input"
            );

        const resultSelect =
            newRow.querySelector(
                ".result-select"
            );

        saveRow(
            newRow,
            location,
            speciesInput,
            resultSelect
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
