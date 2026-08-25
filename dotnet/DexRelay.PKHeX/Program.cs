using System;
using System.Collections.Generic;
using System.Text.Json;
using PKHeX.Core;

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

    var response = new
    {
        metLocationId,
        metLocationName,
        eggLocationId,
        version = pk.Version.ToString(),
        shiny = pk.IsShiny
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