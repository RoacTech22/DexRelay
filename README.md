# DexRelay

Aplicación de escritorio tipo companion para acompañar streams de Pokémon Alpha Sapphire / Omega Ruby ejecutados en el emulador Azahar — lectura realtime del juego, overlays para OBS, Nuzlocke Tracker.

## Requisitos

- Azahar (emulador 3DS) con la interfaz de depuración de memoria activa.
- **Pokémon Omega Ruby: actualización 1.4 instalada.** Confirmado — sin el parche (juego base), el mapa de memoria queda corrido y DexRelay no puede leer nada (equipo vacío, sin error visible).
- **Pokémon Alpha Sapphire: juego BASE, sin actualización.** Confirmado al revés que Omega Ruby — las direcciones actuales están validadas contra AS sin parchear. Con la actualización 1.4 puesta, no funciona (mismo síntoma).
- .NET 10 Runtime (para el bridge PKHeX).

## Pendiente

- Investigar las direcciones de memoria de Alpha Sapphire con la actualización 1.4 (mismo proceso que ya se hizo para Omega Ruby: Cheat Engine en vivo). No urgente — por ahora se sigue jugando AS en la versión base. Ver la nota completa en `app/memory/pointers.py`, junto a `PROCESS_NAME_ALPHA_SAPPHIRE`.
