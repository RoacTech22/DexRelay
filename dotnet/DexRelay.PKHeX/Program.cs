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

// Bug real (03/09/2026): con Types (ver TypeKey() más abajo) y
// ahora con los NOMBRES de movimiento, GameInfo.Strings seguía
// devolviendo texto en inglés aunque CurrentLanguage ya estuviera
// en "es" -- no está claro si el setter de CurrentLanguage no
// termina de refrescar GameInfo.Strings en esta versión de
// PKHeX.Core, o si directamente el diccionario "es" embebido
// tiene huecos para esas listas puntuales. Se fuerza
// explícitamente GameInfo.Strings a la versión en español vía
// GetStrings() -- si el problema era lo primero, esto lo
// resuelve solo; si es lo segundo (huecos reales en el
// diccionario), esto no alcanza y hay que armar una tabla propia
// como se hizo con hoenn_locations_es.py, pero recién ahí, no
// antes de confirmar que esto no lo resuelve.
GameInfo.Strings = GameInfo.GetStrings("es");

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

            case "pokemon_details":
                HandlePokemonDetails(root);
                break;

            case "save_info":
                HandleSaveInfo(root);
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
        // Bug real corregido (05/09/2026, reportado por el
        // usuario): una captura que va directo a la Caja PC no
        // trae nivel en los 232 bytes crudos que lee
        // read_box() -- ese formato no incluye el bloque extra de
        // stats que sí tiene una lectura de party
        // (app/readers/azahar_reader.py:build_pokemon_data()), así
        // que pokemon.level() del lado Python daba 0 para esos
        // casos. CurrentLevel es la misma propiedad que usa
        // pokemon_details (página Pokémon) -- PKHeX lo calcula
        // solo a partir de la experiencia y la curva de
        // crecimiento de la especie, ya presentes en estos mismos
        // 232 bytes, así que sirve como respaldo confiable sin
        // memoria nueva. build_pokemon_data() lo usa solo cuando
        // pokemon.level() da 0 (Caja PC) -- no reemplaza el nivel
        // ya correcto de una lectura de party.
        level = pk.CurrentLevel,
        // Ícono de género en la tabla de encuentros/pendientes/
        // cementerio del Nuzlocke Tracker (05/09/2026) -- misma
        // propiedad que ya usa pokemon_details (página Pokémon)
        // para esto, reutilizada acá sin golpear el bridge de
        // nuevo porque esta llamada ya tiene el PK6 completo en
        // memoria.
        genderId = pk.Gender,
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


// GUI v2, Bloque 3 (03/09/2026) -- página Pokémon: tipos,
// habilidad, naturaleza, stats de combate y movimientos. Reusa
// EXACTAMENTE el mismo pipeline que HandleMetLocation() (los 232
// bytes ya descifrados que ya manda azahar_reader.py) -- no hizo
// falta investigar memoria nueva para nada de esto, PKHeX calcula
// todo a partir de especie+nivel+IVs+EVs+naturaleza, igual que lo
// haría el propio juego.
static void HandlePokemonDetails(JsonElement root)
{
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

    // 232 = tamaño de la estructura PK6 "box format" descifrada
    // (SLOT_DATA_SIZE en pointers.py) -- mismo chequeo que ya usa
    // HandleMetLocation().
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

    // Stats de combate reales (Ataque/Defensa/Ataque Esp/Defensa
    // Esp/Velocidad). El formato "box" (232 bytes) que ya leemos
    // de memoria NO las trae calculadas -- viven en la sección de
    // datos de party que DexRelay lee aparte (STAT_DATA_OFFSET en
    // pointers.py), pero en vez de sumar offsets nuevos ahí (y
    // tener que investigarlos/validarlos con Cheat Engine), se le
    // pide a PKHeX que las calcule con la misma fórmula del juego
    // (especie + nivel + IVs + EVs + naturaleza) --
    // ResetPartyStats() es el mismo método que usa PKHeX
    // internamente al cargar un Pokémon a la party, así que el
    // resultado es idéntico al que muestra el juego.
    pk.ResetPartyStats();

    PersonalInfo personal = pk.PersonalInfo;

    string TypeName(int typeId) =>
        (typeId >= 0 && typeId < GameInfo.Strings.Types.Count)
            ? GameInfo.Strings.Types[typeId]
            : "";

    // Clave de tipo ESTABLE para que el frontend elija color/ícono
    // -- bug real (03/09/2026): primero se probó matchear por el
    // nombre localizado en español (GameInfo.Strings.Types), pero
    // esa localización no es confiable (solo "Normal" coincidía).
    // Después se probó una tabla de IDs numéricos armada a mano
    // (0=Normal, 1=Lucha, ...) -- pero varios tipos seguían
    // saliendo con el color/ícono de otro tipo, señal de que esa
    // tabla tampoco era 100% correcta. Solución definitiva: usar
    // el nombre del propio enum MoveType de PKHeX (ToString()) --
    // es SIEMPRE en inglés (Water, Fire, Electric...), fijo por
    // definición del enum, no depende de ningún idioma ni de
    // ninguna tabla escrita a mano acá. Se usa el mismo enum para
    // tipos de especie Y de movimiento -- es el mismo concepto de
    // "tipo" en todo PKHeX (así se comparan para calcular STAB).
    //
    // Bug real de compilación/runtime (03/09/2026): MoveType tiene
    // tipo base `sbyte`, no `int` -- Enum.IsDefined exige que el
    // valor que se le pasa sea EXACTAMENTE del tipo base del enum
    // (o un string), si no tira
    // "Enum underlying type and the object must be same type".
    // Por eso se castea explícitamente a sbyte antes de preguntar.
    string TypeKey(int typeId)
    {
        sbyte value = (sbyte)typeId;

        return Enum.IsDefined(typeof(MoveType), value)
            ? ((MoveType)value).ToString()
            : "";
    }

    int type1 = personal.Type1;
    int type2 = personal.Type2;

    string abilityName =
        (pk.Ability >= 0 && pk.Ability < GameInfo.Strings.Ability.Count)
            ? GameInfo.Strings.Ability[pk.Ability]
            : "";

    // Naturaleza -- qué stat sube y cuál baja. Fórmula clásica
    // (Gen 3 en adelante, sin cambios hasta hoy): con el índice
    // 0-24 de Nature, subida = índice/5, bajada = índice%5, en
    // el orden [Ataque, Defensa, Velocidad, Ataque Esp, Defensa
    // Esp]. Las 5 naturalezas "neutras" (Hardy/Docile/Serious/
    // Bashful/Quirky, índices múltiplos de 6: 0,6,12,18,24) no
    // suben ni bajan nada -- se detecta con subida==bajada, no
    // con una lista aparte de naturalezas neutras.
    //
    // A diferencia del resto del bridge (que son propiedades de
    // PKHeX leídas tal cual), esto es una fórmula escrita a mano
    // acá -- verificar la primera vez que se pruebe en vivo
    // contra la pantalla de resumen del juego (el stat que sube
    // sale en rojo, el que baja en azul).
    int natureId = (int)pk.Nature;

    string[] natureStatOrder =
    {
        "Ataque",
        "Defensa",
        "Velocidad",
        "AtaqueEsp",
        "DefensaEsp",
    };

    int increasedIndex = natureId / 5;
    int decreasedIndex = natureId % 5;
    bool neutralNature = increasedIndex == decreasedIndex;

    string natureName =
        (natureId >= 0 && natureId < GameInfo.Strings.Natures.Count)
            ? GameInfo.Strings.Natures[natureId]
            : "";

    var moves = new List<object>();
    ushort[] moveIds = { pk.Move1, pk.Move2, pk.Move3, pk.Move4 };

    foreach (ushort moveId in moveIds)
    {
        // Slot de movimiento vacío (Pokémon con menos de 4
        // movimientos aprendidos) -- se omite, no se manda un
        // movimiento "vacío" al frontend.
        if (moveId == 0)
        {
            continue;
        }

        string moveName =
            (moveId < GameInfo.Strings.Move.Count)
                ? GameInfo.Strings.Move[moveId]
                : "";

        byte moveTypeId = MoveInfo.GetType(moveId, pk.Context);

        moves.Add(new
        {
            id = moveId,
            name = moveName,
            typeKey = TypeKey(moveTypeId),
            type = TypeName(moveTypeId),
        });
    }

    var response = new
    {
        // 0=macho, 1=hembra, 2=sin sexo -- el frontend decide el
        // ícono, acá no se manda ningún ícono ni texto ya armado.
        genderId = pk.Gender,
        // Clave de tipo estable (nombre del enum en inglés, ver
        // TypeKey() arriba) -- el frontend colorea/elige el ícono
        // por acá, no por el nombre en español.
        type1Key = TypeKey(type1),
        type1 = TypeName(type1),
        // Muchas especies no tienen segundo tipo -- PKHeX repite
        // Type1 en Type2 para esos casos en vez de dejarlo en un
        // valor "ninguno", así que hay que compararlos para saber
        // si hay que mostrar la segunda insignia o no.
        type2Key = type1 != type2 ? TypeKey(type2) : "",
        type2 = type1 != type2 ? TypeName(type2) : "",
        // Se manda el ID además del nombre -- pensado para cuando
        // se conecte una fuente externa de descripciones de
        // habilidad (pendiente, a decidir más adelante), sin tener
        // que volver a tocar el bridge para agregar el ID en ese
        // momento.
        abilityId = pk.Ability,
        abilityName,
        natureId,
        natureName,
        natureIncreasedStat = neutralNature ? "" : natureStatOrder[increasedIndex],
        natureDecreasedStat = neutralNature ? "" : natureStatOrder[decreasedIndex],
        stats = new
        {
            attack = pk.Stat_ATK,
            defense = pk.Stat_DEF,
            spAttack = pk.Stat_SPA,
            spDefense = pk.Stat_SPD,
            speed = pk.Stat_SPE,
        },
        moves,
    };

    Console.WriteLine(
        JsonSerializer.Serialize(response)
    );
}


// GUI v2, página Nuzlocke (04/09/2026) -- tiempo de juego real
// para la tarjeta de estadísticas. A diferencia de todas las
// demás acciones de este bridge, acá NO se manda ningún byte por
// stdin -- se manda la RUTA del archivo de guardado
// (app/services/save_file_locator.py ya la resolvió del lado de
// Python) y el bridge lo lee directo del disco. Motivo: el
// archivo de guardado real de Gen 6 pesa varios cientos de KB,
// mandarlo como base64 por una sola línea de stdin (como sí se
// hace con los 232 bytes de un Pokémon) infla el payload ~33% y
// no aporta nada -- el bridge corre en la misma máquina y ya
// tiene acceso directo al archivo.
static void HandleSaveInfo(JsonElement root)
{
    string path =
        root.GetProperty("path").GetString()
        ?? "";

    // BUG REAL corregido (04/09/2026, reportado por el usuario
    // con el error de compilación exacto): esta versión de
    // PKHeX.Core (26.7.7) ya NO tiene
    // SaveUtil.GetVariantSAV(byte[]) -- esa era la API vieja
    // (todavía aparece en varios ejemplos/documentación externa
    // desactualizada). La API actual carga directo desde una
    // ruta con SaveUtil.GetSaveFile(path), que además evita tener
    // que leer los bytes a mano acá.
    SaveFile? sav;

    try
    {
        sav = SaveUtil.GetSaveFile(path);
    }
    catch (Exception error)
    {
        WriteError(
            $"No se pudo leer el archivo de guardado: "
            + $"{error.Message}"
        );

        return;
    }

    if (sav is null)
    {
        WriteError(
            "El archivo no fue reconocido como un "
            + "guardado válido de PKHeX."
        );

        return;
    }

    // PlayedHours/Minutes/Seconds son las mismas propiedades que
    // PKHeX muestra en su pestaña "Trainer Info" -- exactamente
    // el contador que el juego lleva en pantalla de inicio. Si
    // esta versión de PKHeX.Core usa otro nombre de propiedad acá,
    // esto no compila -- avisar el error de compilación exacto
    // para ajustarlo, no adivinar un nombre alternativo.
    var response = new
    {
        ok = true,
        playedHours = sav.PlayedHours,
        playedMinutes = sav.PlayedMinutes,
        playedSeconds = sav.PlayedSeconds,
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