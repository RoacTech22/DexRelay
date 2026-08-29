using System;
using System.Collections.Generic;
using System.Text.Json;
using PKHeX.Core;

// Sin esto, PKHeX resuelve nombres de especie/ubicación con su
// idioma por defecto (inglés), que no coincide con la lista de
// rutas en español precargada en panels/nuzlocke/app.js (ej.
// "Route 101" vs "Ruta 101") -- eso hacía que una captura nueva
// no encontrara su fila existente y creara una fila duplicada en
// vez de actualizar la que ya estaba. Fijar el idioma acá asegura
// que species/species_list/met_location devuelvan siempre nombres
// en español, consistentes entre sí.
GameInfo.CurrentLanguage = "es";

while (true)
{
    string? input = Console.ReadLine();

    if (string.IsNullOrWhiteSpace(input))
    {
        continue;
    }

    try
    {
        using JsonDocument document =
            JsonDocument.Parse(input);

        JsonElement root =
            document.RootElement;

        string action =
            root.GetProperty("action").GetString()
            ?? "";

        switch (action)
        {
            case "species":
                HandleSpecies(root);
                break;

            case "species_list":
                HandleSpeciesList();
                break;

            case "met_location":
                HandleMetLocation(root);
                break;

            case "location_list":
                HandleLocationList();
                break;

            default:
                WriteError(
                    $"Acción no soportada: {action}"
                );
                break;
        }
    }
    catch (Exception error)
    {
        WriteError(error.Message);
    }
}


static void HandleSpecies(JsonElement root)
{
    int speciesId =
        root.GetProperty("id").GetInt32();

    if (
        speciesId < 0 ||
        speciesId >= GameInfo.Strings.Species.Count
    )
    {
        WriteError(
            $"Species ID fuera de rango: {speciesId}"
        );

        return;
    }

    string species =
        GameInfo.Strings.Species[speciesId];

    var response = new
    {
        id = speciesId,
        name = species
    };

    Console.WriteLine(
        JsonSerializer.Serialize(response)
    );
}


static void HandleSpeciesList()
{
    var names = GameInfo.Strings.Species;

    var species = new List<object>();

    // id 0 es "vacío"/ninguna especie, se salta.
    for (int id = 1; id < names.Count; id++)
    {
        if (string.IsNullOrEmpty(names[id]))
        {
            continue;
        }

        species.Add(new { id, name = names[id] });
    }

    var response = new { species };

    Console.WriteLine(
        JsonSerializer.Serialize(response)
    );
}


static void HandleLocationList()
{
    // Misma fuente de verdad que HandleMetLocation() usa para
    // resolver el lugar de encuentro de una captura real -- así
    // la lista de rutas que se le muestra al usuario en el panel
    // SIEMPRE coincide textualmente con lo que la detección
    // automática va a reportar. Antes el panel tenía su propia
    // lista escrita a mano (con errores: nombres en inglés,
    // variantes regionales de traducción incorrectas), lo que
    // hacía que una captura nueva no encontrara su fila existente
    // y creara una duplicada.
    var locations =
        GameInfo.GetLocationList(
            GameVersion.AS,
            EntityContext.Gen6,
            egg: false
        );

    var result = new List<object>();

    foreach (var item in locations)
    {
        if (string.IsNullOrEmpty(item.Text))
        {
            continue;
        }

        result.Add(new { id = item.Value, name = item.Text });
    }

    var response = new { locations = result };

    Console.WriteLine(
        JsonSerializer.Serialize(response)
    );
}


static void HandleMetLocation(JsonElement root)
{
    // `data` son los 232 bytes de la estructura PK6 YA
    // DESCIFRADA por DexRelay (app/memory/structures.py:
    // decrypt_data), codificados en base64. PK6.Data espera
    // datos ya descifrados (accede a offsets fijos
    // directamente, ej. Data[0x1E] para EV_HP) -- no vuelve a
    // descifrar por su cuenta, así que hay que pasarle
    // exactamente lo mismo que ya usamos nosotros para leer
    // species/nickname/nivel/HP, no los bytes crudos de
    // memoria.
    string base64Data =
        root.GetProperty("data").GetString()
        ?? "";

    byte[] data;

    try
    {
        data = Convert.FromBase64String(base64Data);
    }
    catch (FormatException)
    {
        WriteError("El campo 'data' no es base64 válido.");
        return;
    }

    // 232 = tamaño de la estructura PK6 "box format"
    // descifrada (SLOT_DATA_SIZE en pointers.py). El campo
    // MetLocation vive ahí, no en los bytes de stats de
    // combate que DexRelay agrega aparte.
    if (data.Length != 232)
    {
        WriteError(
            $"Se esperaban 232 bytes descifrados, se "
            + $"recibieron {data.Length}."
        );

        return;
    }

    PK6 pk;

    try
    {
        pk = new PK6(data);
    }
    catch (Exception error)
    {
        WriteError(
            $"No se pudo interpretar como PK6: {error.Message}"
        );

        return;
    }

    ushort metLocationId = pk.MetLocation;
    ushort eggLocationId = pk.EggLocation;

    string metLocationName =
        GameInfo.GetLocationName(
            false,
            metLocationId,
            pk.Format,
            pk.Generation,
            pk.Version
        );

    // "Entregado por" (28/08/2026, a pedido del usuario): el
    // campo Egg_Location es DISTINTO de Met_Location -- guarda
    // quién/dónde se recibió el Pokémon (ej. "Anciana del
    // Balneario" para un huevo), no dónde se lo "encontró" en el
    // mundo. Antes ya se leía eggLocationId pero nunca se
    // resolvía a texto -- son las mismas tablas de PKHeX, solo
    // que con el flag `eggLocation: true` en vez de `false`.
    // Como GameInfo.CurrentLanguage ya está fijado en "es" arriba,
    // sale en español igual que metLocationName, sin traducción
    // aparte.
    //
    // BUG REAL corregido (28/08/2026, encontrado probando en el
    // juego): eggLocationId == 0 significa "este Pokémon NUNCA
    // fue huevo" (la inmensa mayoría de las capturas) -- pero a
    // diferencia de metLocationId, la tabla de ubicaciones de
    // huevo SÍ resuelve el ID 0 a un texto no vacío en vez de
    // vacío. Sin este chequeo, TODAS las capturas (no solo los
    // huevos reales) terminaban con un eggLocationName no vacío,
    // y el lado Python -- que le da prioridad a eggLocation
    // cuando no está vacío -- las registraba a todas como
    // "especial/huevo". Se corta acá explícitamente: solo se
    // resuelve el texto si el ID no es 0.
    string eggLocationName =
        eggLocationId == 0
            ? ""
            : GameInfo.GetLocationName(
                true,
                eggLocationId,
                pk.Format,
                pk.Generation,
                pk.Version
            );

    var response = new
    {
        metLocationId,
        metLocationName,
        eggLocationId,
        eggLocationName,
        version = pk.Version.ToString(),
        shiny = pk.IsShiny,
        // 29/08/2026, a pedido del usuario: el overlay del equipo
        // mostraba el sprite de la especie REAL de un huevo sin
        // nacer todavía (spoiler) -- species_id ya venía resuelto
        // desde antes (el dato está en el PK6 aunque el nickname
        // diga "Huevo"), pero no había forma de saber que HABÍA
        // que ocultarlo. pk.IsEgg es la misma propiedad de PKHeX
        // que ya usa el juego para decidir eso.
        isEgg = pk.IsEgg
    };

    Console.WriteLine(
        JsonSerializer.Serialize(response)
    );
}


static void WriteError(string message)
{
    var response = new
    {
        error = message
    };

    Console.WriteLine(
        JsonSerializer.Serialize(response)
    );
}