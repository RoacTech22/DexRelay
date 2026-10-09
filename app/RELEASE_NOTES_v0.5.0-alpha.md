# DexRelay v0.5.0-alpha — primera versión multijuego

DexRelay ahora funciona con **Pokémon X e Y** (actualización 1.5) además de **Omega Ruby y Alpha Sapphire** (actualización 1.4), todo en Azahar.

## Novedades

### Pokémon X e Y
- Equipo en tiempo real, cajas, tarjeta de entrenador y medallas de Kalos con su arte.
- Nuzlocke completo: catálogo de 53 ubicaciones de Kalos en orden narrativo y en español, nombres de zona, detección automática de encuentros perdidos, fósiles (también en randomlocke) e intercambios.
- Líderes de gimnasio, Alto Mando y campeón de Kalos, con equipos, movimientos y habilidades.
- Tarjeta de "próximo líder" con el nivel máximo recomendado, que pasa al Alto Mando con las 8 medallas.
- Tiempo de juego leído del guardado.
- Herramientas: Caramelo Raro en la bolsa.
- Tarjetas de inicio, fondos, avatares y overlay de medallas propios de X e Y.

### Para ambos juegos
- Pestaña **Bosses** (antes Líderes) con las secciones Líderes y Alto Mando.
- Alto Mando y campeón de Hoenn (Sixto, Fátima, Nívea, Dracón y Máximo Peñas) con sus equipos.
- Sección "Alto Mando" en la página Medallas.
- "Intercambiado" vuelve a mostrarse en el Nuzlocke, y las etiquetas especiales (Fósil, Shiny, Huevo) se leen sin prefijo.
- Las filas especiales del Nuzlocke se ordenan bajo el lugar donde ocurrieron.

### Por dentro
- Arquitectura por perfiles de juego: cada juego declara su mapa de memoria, sus capacidades y su contenido.
- El bridge de PKHeX acepta el juego en las consultas de ubicaciones y especies.
- El módulo antiguo de direcciones fijas de ORAS se retiró de la aplicación.
