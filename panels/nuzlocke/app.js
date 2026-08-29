const ENCOUNTERS_API_URL = "/api/nuzlocke/encounters";
const PENDING_API_URL = "/api/nuzlocke/pending-encounters";
// Sigue existiendo en el backend (assign_encounter_location) pero
// el panel ya no la usa -- el flujo de "Capturas sin ruta
// asignada" pasó a ser "¿Pokémon Especial?" (27/08/2026), que usa
// PENDING_ASSIGN_SPECIAL_API_URL en su lugar. Se deja declarada
// por si hace falta reactivar un flujo de asignación de ruta
// libre a futuro.
const ASSIGN_API_URL = "/api/nuzlocke/encounters/assign";
const SPECIES_API_URL = "/api/species";
const LOCATIONS_API_URL = "/api/locations";

const PENDING_ASSIGN_SPECIAL_API_URL =
    "/api/nuzlocke/pending-encounters/assign-special";

const VALID_STATUSES = [
    "sin_intentar",
    "capturado",
    "perdido",
    "muerto",
    "especial"
];

const STATUS_LABELS = {
    sin_intentar: "Sin Capturar",
    capturado: "Capturado",
    perdido: "Perdido",
    muerto: "Muerto",
    especial: "Especial"
};

// Origenes posibles para una captura "Especial" (27/08/2026,
// reemplaza a los viejos estados sueltos intercambiado/regalo/
// shiny). El valor elegido acá se guarda aparte del status
// ("origin" en el encuentro) -- la etiqueta mostrada en la tabla
// combina los dos como "Especial/Shiny", "Especial/Huevo", etc.
// (ver updateSpecialOptionLabel()).
const VALID_ORIGINS = [
    "shiny",
    "huevo",
    "intercambio",
    "evento",
    "regalo",
    "fosil"
];

// Subconjunto seleccionable A MANO en la tarjeta "¿Pokémon
// Especial?" (29/08/2026, a pedido del usuario): huevo,
// intercambio y fósil ya se detectan solos (ver
// nuzlocke_service.py) -- dejarlos en este dropdown invita a
// elegir mal y pisar la detección automática por error. Quedan
// afuera de esta lista, pero siguen siendo VALID_ORIGINS válidos
// para el resto del panel (labels, colores, etc.) -- por eso es
// una lista aparte, no un recorte de VALID_ORIGINS.
//
// "captura_extra" (29/08/2026) es un caso aparte: NO es un
// origen real de VALID_ORIGINS (no usa status="especial", ver
// _assign_extra_capture() en el backend) -- se agrega acá nomás
// para que aparezca como opción en el mismo dropdown, aunque el
// backend lo maneje distinto.
const MANUAL_ORIGIN_OPTIONS = [
    "shiny",
    "evento",
    "regalo",
    "captura_extra"
];

const ORIGIN_LABELS = {
    shiny: "Shiny",
    huevo: "Huevo",
    intercambio: "Intercambio",
    evento: "Evento",
    regalo: "Regalo",
    fosil: "Fósil",
    captura_extra: "Captura Extra"
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
   UBICACIÓN DE FILAS "ESPECIAL" EN LA TABLA
   (27/08/2026, a pedido explícito)

   Por defecto toda fila nueva se agrega al final
   (comportamiento de siempre, sin tocar). Las filas
   "especial" son la única excepción: se reubican
   justo debajo de su ruta real (`anchorLocation`,
   ver backend) o, si no tienen ninguna ruta real
   conocida (huevo/regalo/intercambio/evento), debajo
   de la ÚLTIMA ruta real que ya tenga algo capturado
   -- nunca se tocan otras filas para hacerles lugar,
   solo se reposiciona la fila nueva.

   Se llama DESPUÉS de que addRow() ya agregó la fila
   al final (comportamiento normal) -- esta función
   solo la mueve si corresponde.
========================================= */

function repositionSpecialRow(row, entry) {

    if (!row || entry?.status !== "especial") {
        return;
    }

    // Agrupa esta fila con otras "especial" ancladas al mismo
    // lugar (misma ruta real, o mismo "sin ruta real") -- así
    // varias capturas especiales apiladas quedan en el orden en
    // que se fueron asignando, no se pisan entre sí.
    const anchorGroup =
        entry.anchorLocation || "__sin_ruta__";

    row.dataset.anchorGroup = anchorGroup;

    const referenceRow =
        entry.anchorLocation
            ? findRowByLocation(entry.anchorLocation)
            : findLastCapturedRouteRow();

    if (!referenceRow || referenceRow === row) {
        // Sin ancla real todavía (ruta no encontrada en la tabla,
        // o directamente nada capturado aún) -- se queda al
        // final, que es donde addRow() ya la puso.
        return;
    }

    let insertAfter = referenceRow;

    while (
        insertAfter.nextElementSibling &&
        insertAfter.nextElementSibling.dataset.anchorGroup ===
            anchorGroup
    ) {
        insertAfter = insertAfter.nextElementSibling;
    }

    if (insertAfter === row) {
        return;
    }

    tableBody.insertBefore(
        row,
        insertAfter.nextSibling
    );
}


function findLastCapturedRouteRow() {

    let last = null;

    for (const row of tableBody.children) {

        // Otra fila "especial" (anclada o no) no cuenta como
        // ruta real -- solo interesan las rutas de verdad.
        if (row.dataset.anchorGroup) {
            continue;
        }

        const statusSelect =
            row.querySelector(".status-select");

        if (
            statusSelect &&
            statusSelect.value !== "sin_intentar"
        ) {
            last = row;
        }
    }

    return last;
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

        // En modo lectura (readOnly) el campo puede recibir foco
        // por clic, pero no se puede escribir -- no tiene sentido
        // mostrar sugerencias que no se pueden seleccionar sin
        // antes habilitar la edición con el ícono de lápiz.
        if (input.readOnly) {
            return;
        }

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
    // defecto: rutas agregadas a mano en una sesión anterior, y
    // las pseudo-rutas de "¿Pokémon Especial?" (Inicial también
    // cae acá si por algún motivo no viniera en DEFAULT_LOCATIONS,
    // aunque siempre debería). Se ordenan por updatedAt para que,
    // si hay varias especiales sin ruta real apiladas en el mismo
    // lugar (ver repositionSpecialRow), queden en el orden en que
    // se fueron asignando -- no en el orden en que llegaron del
    // servidor, que no está garantizado.
    const extras = existing
        .filter(entry => !renderedLocations.has(entry.location))
        .sort(
            (a, b) =>
                (a.updatedAt || "").localeCompare(
                    b.updatedAt || ""
                )
        );

    for (const entry of extras) {

        addRow(entry.location, entry);

        renderedLocations.add(entry.location);

        repositionSpecialRow(
            tableBody.lastElementChild,
            entry
        );
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

function syncNicknameSize(nicknameInput) {

    // El atributo `size` (no CSS width) es lo que realmente hace
    // que un <input> mida según su contenido en vez de quedarse
    // con el ancho por defecto del navegador (~20 caracteres) --
    // sin esto, el ícono de shiny quedaba pegado al borde derecho
    // de la celda en vez de al texto del nickname, aunque el
    // input ya no se estirara con flex (28/08/2026, a pedido del
    // usuario). Mínimo 4 para que no quede una cajita minúscula
    // con el placeholder o un nickname muy corto.
    nicknameInput.size = Math.max(
        nicknameInput.value.length,
        4
    );
}


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

    // Ícono de edición: por defecto la tabla es de SOLO
    // INFORMACIÓN (27/08/2026, a pedido explícito) -- los campos
    // se ven pero no se pueden tocar hasta hacer clic acá. Existe
    // para TODAS las filas, incluida "Inicial" (a diferencia del
    // botón de reseteo, que sigue excluido para esa fila).
    const editButton =
        document.createElement("button");

    editButton.type = "button";
    editButton.className = "edit-button";
    editButton.title = "Editar esta fila";
    editButton.textContent = "✎";

    editButton.addEventListener(
        "click",
        () => {

            const isEditable =
                !row.classList.contains(
                    "row-readonly"
                );

            toggleRowEditing(row, !isEditable);
        }
    );

    const actionsWrapper =
        document.createElement("div");

    actionsWrapper.className =
        "location-actions";

    actionsWrapper.appendChild(editButton);

    // "Inicial" es permanente por definición -- ni siquiera se
    // muestra el botón de reseteo (el backend también lo rechaza,
    // esto es solo para no invitar al click en primer lugar).
    if (location !== "Inicial") {

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

        actionsWrapper.appendChild(resetButton);
    }

    locationCell.appendChild(actionsWrapper);


    const nicknameCell =
        document.createElement("td");

    const nicknameWrapper =
        document.createElement("div");

    nicknameWrapper.className = "nickname-wrapper";

    const nicknameInput =
        document.createElement("input");

    nicknameInput.type = "text";
    nicknameInput.className = "nickname-input";
    nicknameInput.placeholder = "Nickname...";
    nicknameInput.readOnly = true;

    nicknameInput.value =
        existingEntry?.nickname || "";

    syncNicknameSize(nicknameInput);

    nicknameInput.addEventListener(
        "input",
        () => syncNicknameSize(nicknameInput)
    );

    nicknameWrapper.appendChild(nicknameInput);

    // Ícono de shiny (28/08/2026, a pedido del usuario) --
    // mismo criterio que los íconos de editar/resetear (✎/✕):
    // un carácter, no una imagen, para no depender de ningún
    // sprite nuevo. Va DESPUÉS del nickname, pegado (mismo
    // estilo " ✨" que ya usan las tarjetas de "¿Pokémon
    // Especial?"). Se muestra cuando `entry.shiny` es true --
    // YA NO depende de origin === "shiny" (29/08/2026): desde
    // que se invirtió la prioridad de origen (huevo/fósil/
    // intercambio le ganan a shiny), un Pokémon shiny puede
    // tener cualquier otro origen y el ícono tiene que seguir
    // mostrándose igual.
    const shinyIcon =
        document.createElement("span");

    shinyIcon.className = "shiny-icon";
    shinyIcon.textContent = "✨";
    shinyIcon.title = "Shiny";

    shinyIcon.classList.toggle(
        "visible",
        existingEntry?.shiny === true
    );

    nicknameWrapper.appendChild(shinyIcon);

    nicknameCell.appendChild(nicknameWrapper);


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

    speciesInput.readOnly = true;


    const statusCell =
        document.createElement("td");

    const statusSelect =
        document.createElement("select");

    statusSelect.className =
        "status-select";

    statusSelect.disabled = true;

    for (const value of VALID_STATUSES) {

        const option =
            document.createElement("option");

        option.value = value;
        option.textContent = STATUS_LABELS[value];

        // "Especial" ya no se puede elegir a mano desde acá
        // (29/08/2026, a pedido del usuario) -- huevo/intercambio/
        // fósil/shiny se detectan solos, y el resto de los casos
        // "especial" (evento/regalo/captura extra) se asignan
        // desde la tarjeta "¿Pokémon Especial?", que sí sabe pedir
        // el origen. Elegir "Especial" directo acá no tenía forma
        // de pedir el origen y rompía con ValueError. La opción
        // sigue en el DOM (deshabilitada) para que una fila YA
        // marcada como especial se pueda seguir mostrando/
        // seleccionar programáticamente.
        if (value === "especial") {
            option.disabled = true;
        }

        statusSelect.appendChild(option);
    }

    statusSelect.value =
        existingEntry?.status || "sin_intentar";

    updateSpecialOptionLabel(
        statusSelect,
        existingEntry
    );

    applyStatusClass(
        statusSelect,
        statusSelect.value,
        row,
        existingEntry?.tradedAway === true,
        existingEntry?.extraCapture === true
    );

    statusCell.appendChild(statusSelect);


    row.classList.add("row-readonly");

    row.appendChild(locationCell);
    row.appendChild(nicknameCell);
    row.appendChild(speciesCell);
    row.appendChild(statusCell);

    tableBody.appendChild(row);


    /* ================================
       AUTOGUARDADO -- y vuelta automática a
       modo lectura cuando el foco sale de la
       fila (ver toggleRowEditing/lockRowIfFocusLeft).
    ================================= */

    nicknameInput.addEventListener(
        "blur",
        () => {

            saveRow(
                row,
                location,
                nicknameInput,
                speciesInput,
                statusSelect
            );

            lockRowIfFocusLeft(row);
        }
    );

    speciesInput.addEventListener(
        "blur",
        () => {

            saveRow(
                row,
                location,
                nicknameInput,
                speciesInput,
                statusSelect
            );

            lockRowIfFocusLeft(row);
        }
    );

    statusSelect.addEventListener(
        "change",
        () => {

            applyStatusClass(
                statusSelect,
                statusSelect.value,
                row
            );

            saveRow(
                row,
                location,
                nicknameInput,
                speciesInput,
                statusSelect
            );

            lockRowIfFocusLeft(row);
        }
    );
}


/* =========================================
   MODO SOLO LECTURA / EDICIÓN POR FILA

   Por defecto la tabla es de solo información
   (27/08/2026, a pedido explícito) -- cada fila
   arranca bloqueada (row-readonly) y el ícono de
   lápiz la desbloquea puntualmente. Se vuelve a
   bloquear sola cuando el foco sale de la fila
   (blur de nickname/especie, change de estado),
   sin necesidad de un botón de "guardar" aparte --
   reutiliza el autoguardado que ya existía.
========================================= */

function toggleRowEditing(row, editable) {

    const nicknameInput =
        row.querySelector(".nickname-input");

    const speciesInput =
        row.querySelector(".species-input");

    const statusSelect =
        row.querySelector(".status-select");

    const editButton =
        row.querySelector(".edit-button");

    if (nicknameInput) {
        nicknameInput.readOnly = !editable;
    }

    if (speciesInput) {
        speciesInput.readOnly = !editable;
    }

    if (statusSelect) {
        statusSelect.disabled = !editable;
    }

    row.classList.toggle(
        "row-readonly",
        !editable
    );

    if (editButton) {

        editButton.classList.toggle(
            "active",
            editable
        );

        editButton.title = editable
            ? "Terminar de editar"
            : "Editar esta fila";
    }

    if (editable && nicknameInput) {
        nicknameInput.focus();
    }
}


function lockRowIfFocusLeft(row) {

    // Mismo margen que ya se usaba para las sugerencias del
    // buscador de especie (100ms) -- un poco más generoso acá
    // porque a veces el blur de un campo y el focus del
    // siguiente (nickname -> especie) no son perfectamente
    // atómicos.
    setTimeout(
        () => {

            if (!row.contains(document.activeElement)) {
                toggleRowEditing(row, false);
            }
        },
        150
    );
}


// La opción "especial" de un <select> de estado es la MISMA para
// todas las filas (viene del loop de VALID_STATUSES en addRow()),
// pero el origen (shiny/huevo/intercambio/evento/regalo/fosil) es
// un dato POR FILA -- así que la etiqueta visible de esa opción
// puntual se ajusta acá, por instancia de <select>. A pedido del
// usuario (29/08/2026) ya no se antepone "Especial/" -- se muestra
// directo el origen ("Fósil", "Huevo", "Shiny", etc.), el status
// interno sigue siendo "especial" igual (value del <option> no
// cambia). Sin origen conocido (fila nueva, o estado puesto a
// mano sin pasar por la tarjeta de "¿Pokémon Especial?"), se deja
// el texto genérico "Especial".
function updateSpecialOptionLabel(
    statusSelect,
    entry
) {

    const option =
        statusSelect.querySelector(
            'option[value="especial"]'
        );

    if (!option) {
        return;
    }

    const origin =
        entry?.status === "especial"
            ? entry.origin
            : null;

    option.textContent =
        origin && ORIGIN_LABELS[origin]
            ? ORIGIN_LABELS[origin]
            : STATUS_LABELS.especial;
}


function applyStatusClass(
    selectElement,
    status,
    row,
    tradedAway,
    extraCapture
) {

    for (const value of VALID_STATUSES) {

        selectElement.classList.remove(
            `status-${value}`
        );
    }

    selectElement.classList.add(
        `status-${status}`
    );

    // Filas "perdido"/"muerto" quedan apagadas (grises,
    // atenuadas) -- mismo lenguaje visual que ya usa el Team
    // Overlay para un Pokémon debilitado (.nuzlocke-dead),
    // aplicado acá a la fila entera de la tabla del panel.
    if (row) {

        const isDimmed =
            status === "perdido" ||
            status === "muerto";

        row.classList.toggle(
            "row-dimmed",
            isDimmed
        );

        // Pokémon intercambiado, se fue (28/08/2026, a pedido del
        // usuario): nickname y especie quedan tachados y el
        // color del estado pasa a gris, sin perder el registro de
        // dónde se lo había atrapado (status/ubicación no
        // cambian). Si no se pasa `tradedAway` explícitamente
        // (ej. el listener de "cambiar estado a mano"), se
        // preserva lo que la fila ya tenía en vez de borrarlo.
        const resolvedTradedAway =
            tradedAway !== undefined
                ? tradedAway
                : row.classList.contains("row-traded-away");

        row.classList.toggle(
            "row-traded-away",
            resolvedTradedAway
        );

        // "Captura Extra" (29/08/2026, a pedido del usuario):
        // mismo patrón que tradedAway -- el status en sí sigue
        // siendo "capturado" (dato histórico real), solo cambia
        // el TEXTO que se muestra para esta fila puntual. Mismo
        // criterio de "preservar si no se pasa explícito".
        const resolvedExtraCapture =
            extraCapture !== undefined
                ? extraCapture
                : row.classList.contains("row-extra-capture");

        row.classList.toggle(
            "row-extra-capture",
            resolvedExtraCapture
        );

        // El status en sí sigue siendo "capturado" (es un dato
        // histórico real -- ahí se lo atrapó), pero el texto que
        // se muestra en el <select> pasa a "Intercambiado" o
        // "Captura Extra" para esta fila puntual -- mismo patrón
        // que updateSpecialOptionLabel() usa para "Especial/
        // Huevo". Intercambiado tiene prioridad si por algún
        // motivo coincidieran los dos (el Pokémon literalmente
        // ya no está en el juego, es el dato más "final").
        const capturadoOption =
            selectElement.querySelector(
                'option[value="capturado"]'
            );

        if (capturadoOption) {

            capturadoOption.textContent =
                resolvedTradedAway
                    ? "Intercambiado"
                    : resolvedExtraCapture
                        ? "Captura Extra"
                        : STATUS_LABELS.capturado;
        }
    }
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
            syncNicknameSize(nicknameInput);
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
                "sin_intentar",
                row
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

    const speciesLine =
        document.createElement("div");

    speciesLine.className = "pending-species";

    speciesLine.innerHTML =
        `<strong>${
            escapeHTML(entry.species || "")
        }</strong>${shinyTag}`;

    const questionLine =
        document.createElement("div");

    questionLine.className = "pending-question";

    questionLine.textContent =
        `No te quedan capturas en esta ruta. ` +
        `¿Es ${entry.nickname || ""} un Pokémon especial?`;

    info.appendChild(speciesLine);
    info.appendChild(questionLine);

    // La ruta real solo se conoce cuando PKHeX SÍ pudo resolver
    // un lugar de encuentro, pero esa ruta ya tenía otro
    // encuentro registrado (colisión) -- ver
    // NuzlockeService._register_new_capture(), caso 2. Para
    // huevo/regalo/intercambio no hay ruta real que mostrar,
    // directamente no existió un encuentro salvaje.
    if (entry.metLocation) {

        const realLocationLine =
            document.createElement("div");

        realLocationLine.className =
            "pending-real-location";

        realLocationLine.textContent =
            `Ruta real detectada: ${entry.metLocation}`;

        info.appendChild(realLocationLine);
    }

    const controls =
        document.createElement("div");

    controls.className = "pending-controls";

    const originLabel =
        document.createElement("label");

    originLabel.className = "pending-origin-label";
    originLabel.textContent = "Origen";

    const select =
        document.createElement("select");

    select.className = "pending-select";

    const blankOption =
        document.createElement("option");

    blankOption.value = "";
    blankOption.textContent = "Elegir origen...";

    select.appendChild(blankOption);

    for (const origin of MANUAL_ORIGIN_OPTIONS) {

        const option =
            document.createElement("option");

        option.value = origin;
        option.textContent = ORIGIN_LABELS[origin];

        select.appendChild(option);
    }

    // Ya sabemos por PKHeX si es shiny -- preseleccionarlo de
    // una, el jugador lo puede cambiar igual si no corresponde.
    if (entry.shiny) {
        select.value = "shiny";
    }

    originLabel.appendChild(select);

    const button =
        document.createElement("button");

    button.type = "button";
    button.className = "pending-assign-button";
    button.textContent = "Asignar";
    button.disabled = !select.value;

    select.addEventListener(
        "change",
        () => {
            button.disabled =
                !select.value;
        }
    );

    button.addEventListener(
        "click",
        () => assignSpecialOrigin(
            entry.nickname,
            select.value,
            card
        )
    );

    const discardButton =
        document.createElement("button");

    discardButton.type = "button";
    discardButton.className =
        "pending-discard-button";
    discardButton.textContent = "Descartar";
    discardButton.title =
        "No contar esta captura para el tracker " +
        "de rutas (sigue en tu equipo real)";

    discardButton.addEventListener(
        "click",
        () => discardPending(
            entry.nickname,
            card
        )
    );

    controls.appendChild(originLabel);
    controls.appendChild(button);
    controls.appendChild(discardButton);

    card.appendChild(info);
    card.appendChild(controls);

    return card;
}



async function discardPending(nickname, card) {

    try {

        const response =
            await fetch(
                "/api/nuzlocke/pending-encounters/discard",
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    body: JSON.stringify({ nickname })
                }
            );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        card.remove();

    } catch (error) {

        console.error(
            "Error descartando captura:",
            error
        );
    }
}


async function assignSpecialOrigin(
    nickname,
    origin,
    card
) {

    if (!origin) {
        return;
    }

    try {

        const response =
            await fetch(
                PENDING_ASSIGN_SPECIAL_API_URL,
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    body: JSON.stringify({
                        nickname,
                        origin
                    })
                }
            );

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        card.remove();

        const data =
            await response.json();

        // A diferencia del viejo flujo (el usuario elegía la
        // ruta, así que ya la sabíamos), acá la pseudo-ubicación
        // "Especial (Nickname)" la genera el backend -- hay que
        // buscarla en la respuesta por nickname en vez de
        // asumirla de antemano.
        const savedEntry =
            (data.encounters || []).find(
                entry => entry.nickname === nickname
            );

        if (savedEntry) {

            updateRowFromAssignment(
                savedEntry.location,
                data
            );
        }

    } catch (error) {

        console.error(
            "Error asignando origen especial:",
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

        repositionSpecialRow(
            tableBody.lastElementChild,
            savedEntry
        );

        return;
    }

    const nicknameInput =
        row.querySelector(".nickname-input");

    const speciesInput =
        row.querySelector(".species-input");

    const statusSelect =
        row.querySelector(".status-select");

    const shinyIcon =
        row.querySelector(".shiny-icon");

    let changed = false;

    if (shinyIcon) {

        // Ver comentario en addRow() (29/08/2026): ya no depende
        // de origin === "shiny".
        const isShiny = savedEntry.shiny === true;

        if (
            shinyIcon.classList.contains("visible")
            !== isShiny
        ) {
            shinyIcon.classList.toggle("visible", isShiny);
            changed = true;
        }
    }

    if (
        nicknameInput &&
        document.activeElement !== nicknameInput
    ) {

        const newValue = savedEntry.nickname || "";

        if (nicknameInput.value !== newValue) {
            nicknameInput.value = newValue;
            syncNicknameSize(nicknameInput);
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

        const newTradedAway =
            savedEntry.tradedAway === true;

        const newExtraCapture =
            savedEntry.extraCapture === true;

        const previousOptionLabel =
            statusSelect
                .querySelector(
                    'option[value="especial"]'
                )
                ?.textContent;

        updateSpecialOptionLabel(
            statusSelect,
            savedEntry
        );

        const newOptionLabel =
            statusSelect
                .querySelector(
                    'option[value="especial"]'
                )
                ?.textContent;

        // tradedAway/extraCapture pueden cambiar SIN que cambie
        // el status (el Pokémon sigue "capturado", solo cambia
        // el texto mostrado) -- por eso se comparan aparte, no
        // alcanza con mirar statusSelect.value/newOptionLabel.
        const tradedAwayChanged =
            row.classList.contains("row-traded-away")
            !== newTradedAway;

        const extraCaptureChanged =
            row.classList.contains("row-extra-capture")
            !== newExtraCapture;

        if (
            statusSelect.value !== newValue ||
            previousOptionLabel !== newOptionLabel ||
            tradedAwayChanged ||
            extraCaptureChanged
        ) {

            statusSelect.value = newValue;

            applyStatusClass(
                statusSelect,
                statusSelect.value,
                row,
                newTradedAway,
                newExtraCapture
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

        const newRow =
            tableBody.lastElementChild;

        // Recién agregada -- se abre directo en modo edición, no
        // tiene sentido pedirle al usuario un clic más para poder
        // cargar los datos de algo que acaba de crear a mano.
        toggleRowEditing(newRow, true);

        // Persistir la ubicación nueva de una vez, para
        // que sobreviva un refresh de la página aunque
        // todavía no se haya cargado nada ahí.
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


/* =========================================
   REINICIAR TODO EL NUZLOCKE TRACKER
   (provisional)

   Borra roster, cementerio, encounters y pending_encounters --
   arranca la partida en DexRelay como si fuera nueva. Doble
   confirmación porque es mucho más destructivo que resetear una
   sola ruta (ver resetLocation): no hay forma de deshacerlo.
========================================= */

const resetAllButton =
    document.getElementById("reset-all-button");

resetAllButton.addEventListener(
    "click",
    async () => {

        const firstConfirm = window.confirm(
            "Esto borra TODO el Nuzlocke Tracker: " +
            "capturados, cementerio y todos los " +
            "encuentros registrados. No se puede " +
            "deshacer.\n\n¿Seguro que querés continuar?"
        );

        if (!firstConfirm) {
            return;
        }

        const secondConfirm = window.confirm(
            "Confirmá una vez más: se va a borrar TODO " +
            "de verdad. ¿Continuar?"
        );

        if (!secondConfirm) {
            return;
        }

        try {

            const response =
                await fetch(
                    "/api/nuzlocke/reset",
                    { method: "POST" }
                );

            if (!response.ok) {
                throw new Error(
                    `HTTP ${response.status}`
                );
            }

            // Recargar la página es lo más simple y
            // confiable para reflejar el estado vacío en
            // toda la tabla, las tarjetas pendientes, etc.
            window.location.reload();

        } catch (error) {

            console.error(
                "Error reiniciando el Nuzlocke Tracker:",
                error
            );
        }
    }
);


init();
