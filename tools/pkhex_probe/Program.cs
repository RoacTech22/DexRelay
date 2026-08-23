using PKHeX.Core;

Console.WriteLine("================================");
Console.WriteLine("       DEXRELAY PKHEX PROBE");
Console.WriteLine("================================");
Console.WriteLine();

Console.WriteLine("PKHeX.Core cargado correctamente.");
Console.WriteLine();

int[] speciesIds =
{
    269,
    659,
    258,
    15,
    661
};

foreach (int speciesId in speciesIds)
{
    string speciesName =
        GameInfo.Strings.Species[speciesId];

    Console.WriteLine(
        $"{speciesId} -> {speciesName}"
    );
}