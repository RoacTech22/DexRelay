# DexRelay.PKHeX (bridge)

Código fuente del ejecutable `DexRelay.PKHeX.exe` que se incluye en cada
release de DexRelay. Usa [PKHeX.Core](https://github.com/kwsch/PKHeX)
(GPLv3), por lo que este código se publica bajo **GNU GPLv3** (ver `LICENSE`).

## Compilar

Requiere el SDK de .NET 10.

```
dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o out
```

DexRelay lo ejecuta como un proceso aparte y se comunica con él por la entrada
estándar (stdin) y la salida estándar (stdout).
