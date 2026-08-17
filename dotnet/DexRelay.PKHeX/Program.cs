using System.Text.Json;
using PKHeX.Core;

Console.WriteLine("DEXRELAY PKHEX BRIDGE");

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