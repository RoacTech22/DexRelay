/*
 * JS de la ventana standalone "Detalle de equipo de un líder"
 * (Fase B, 06/09/2026, a pedido del usuario: "que fuera una
 * ventana" en vez de un modal -- así se pueden abrir varias a la
 * vez, una por líder, y cada una se puede mover fuera de los
 * límites de la ventana principal, cosa que un modal HTML nunca
 * puede hacer).
 *
 * Esta página es standalone a propósito -- NO comparte el bundle
 * de app.js (esa clausura vive solo en index.html/la ventana
 * principal). Por eso duplica acá los pedazos mínimos que necesita
 * (TYPE_INFO para los colores/íconos de tipo, MOVE_NAME_ES para
 * traducir los movimientos) en vez de depender de un archivo
 * compartido -- mantiene cada ventana entendible por separado, al
 * costo de tener que actualizar las dos copias si algún tipo o
 * movimiento nuevo se agrega más adelante (documentado acá para no
 * olvidarlo).
 *
 * Flujo: se abre con `?order=N` en la URL (ver
 * Api.open_leader_team_window() en api.py). Apenas pywebview está
 * listo, pide el detalle completo de ESE líder puntual vía
 * `pywebview.api.get_leader_team_window_data(order)` -- una sola
 * vez, esta ventana no tiene poll propio (el equipo de un líder es
 * contenido fijo de la ROM, no cambia mientras la ventana está
 * abierta).
 */

(function () {
  "use strict";

  var TYPE_ICON_VIEWBOX = "0 0 76.71 76.71";

  // Base URL del HTTPServer, resuelta una vez en init() (08/09/2026,
  // agregado junto con el modal Pokédex de especie -- antes el
  // baseUrl solo se pasaba como parámetro a render()/
  // buildMonCardHtml(), pero openSpeciesModal() necesita poder
  // armar URLs de sprite en cualquier momento, no solo durante el
  // render inicial).
  var spriteBaseUrl = "";

  // Mismo TYPE_INFO que app.js, con los glifos incluidos (06/09/2026
  // -- antes esta copia no los tenía porque el modal viejo no
  // reusaba .pokemon-type-badge/.pokemon-move-type; ahora que la
  // tarjeta de detalle reutiliza esos mismos componentes de la
  // página Pokémon, hacen falta acá también). Ver ese archivo para
  // el comentario completo sobre la paleta oficial "EP" de 3 tonos
  // por tipo.
  var TYPE_INFO = {
    "Normal": { label: "Normal", color: "#9fa19f", colorDark: "#4f504f", colorLight: "#cfd0cf", glyph: "<path d=\"M63.81 26.43c3.12-4.29 2.43-10.33-1.69-13.79-4-3.36-9.82-3.11-13.54.39-3.18-1.21-6.63-1.88-10.23-1.88s-7.05.67-10.23 1.88c-3.71-3.5-9.53-3.74-13.54-.39-4.13 3.46-4.81 9.49-1.69 13.79-2.17 4.05-3.4 8.67-3.4 13.58 0 15.91 12.95 28.86 28.86 28.86s28.86-12.95 28.86-28.86c0-4.91-1.23-9.53-3.4-13.58zM38.35 60.87c-11.5 0-20.86-9.36-20.86-20.86s9.36-20.86 20.86-20.86 20.86 9.36 20.86 20.86-9.36 20.86-20.86 20.86z\" fill=\"#fff\"/>" },
    "Fire": { label: "Fuego", color: "#e62829", colorDark: "#731414", colorLight: "#f29394", glyph: "<path d=\"M55.78 38.1c-5.32-5.15-3.66-9.14-1.21-11.26 0 0-6.53-.79-8.85 4.53-2.33 5.32 2.16 8.06 2.16 8.06s-6.48-2.58-4.66-8.9c1.61-5.56 4.57-8.48 3.24-14.38-1.5-6.67-10.97-9.49-15.55-7.74 3.2 1.08 5.51 4.09 5.51 7.66 0 4.16-3.29 6.92-7.71 11.39-5.11 5.15-10.32 10.97-10.32 20.31 0 10.78 6.65 17.45 14.62 19.87-4.04-1.93-12.45-7.99-11.4-19.65 1.1-12.3 12.89-20.7 12.89-20.7s-2.54 4.26-1.43 11.16c.62 3.88 3.4 8.65 6.05 10.72 3.72 2.91 8.64 5.93 7.93 11.45-.67 5.18-7.55 7.5-11.02 7.71 1.58.26 3.19.37 4.78.32 11.81 0 20.58-8.78 20.58-18.12 0-7.39-3.54-10.43-5.62-12.43z\" fill=\"#fff\"/>" },
    "Water": { label: "Agua", color: "#2980ef", colorDark: "#144077", colorLight: "#94bff7", glyph: "<path d=\"M54 41.57s-3.96-6.86-5.85-9.78c-1.97-3.07-3.82-6.73-5.26-12.61-1.44-5.87-2.22-11.53-4.54-11.53s-3.1 5.65-4.54 11.53c-1.44 5.87-3.29 9.53-5.26 12.61-1.88 2.93-5.85 9.78-5.85 9.78a18.018 18.018 0 00-2.58 9.32c0 10.03 8.2 18.17 18.23 18.17s18.23-8.13 18.23-18.17c0-3.41-.95-6.59-2.58-9.32zM38.35 64.96c-8.18 0-14.61-6.1-14.61-10.5 0-2.91 6.43 2.52 14.61 2.52s14.61-5.43 14.61-2.52c0 4.41-6.43 10.5-14.61 10.5z\" fill=\"#fff\"/>" },
    "Electric": { label: "Eléctrico", color: "#fac000", colorDark: "#7d6000", colorLight: "#fcdf7f", glyph: "<path d=\"M37.97 6.94c2.5 1.14 12.84 6.04 19.84 12.22.31.27.34.75.07 1.06-1.55 1.8-6.66 7.75-12.82 14.99-.27.32-.24.8.07 1.08 1.8 1.59 7.48 6.69 10.91 10.43.28.3.26.77-.04 1.06-2.98 2.87-17.73 17.06-23.45 21.97-.3.26-.76-.02-.67-.41.74-3.02 2.8-11.05 4.99-16.89.12-.31.02-.66-.25-.86-2.15-1.64-11.56-8.86-17.74-14.4a.746.746 0 01-.16-.91c1.36-2.62 7.8-14.72 18.32-29.07.21-.29.6-.4.92-.25z\" fill=\"#fff\"/>" },
    "Grass": { label: "Planta", color: "#3fa129", colorDark: "#1f5014", colorLight: "#9fd094", glyph: "<path d=\"M11.47 66.62H29.1s4.82-44.39 2.33-44.39-19.96 44.39-19.96 44.39zm29.6 0h17.62S67 22.23 64.51 22.23 41.07 66.62 41.07 66.62zm-5.99 0l12.8-25.44s4.66-30.26 2.49-30.26-13.14 26.94-13.14 26.94l-2.16 28.76z\" fill=\"#fff\"/>" },
    "Ice": { label: "Hielo", color: "#3fd8ff", colorDark: "#1f6c7f", colorLight: "#9febff", glyph: "<path fill=\"#fff\" transform=\"rotate(-45 38.354 11.743)\" d=\"M33.44 6.82h9.83v9.83h-9.83z\"/><path fill=\"#fff\" d=\"M11.49 48.24h9.83v9.83h-9.83z\"/><path fill=\"#fff\" transform=\"rotate(-45 38.353 64.974)\" d=\"M33.44 60.05h9.83v9.83h-9.83z\"/><path fill=\"#fff\" d=\"M55.38 18.75v9.77l-17.03-9.83-17.03 9.83v-9.77h-9.83v9.83h9.83v19.6l17.03 9.83 17.03-9.83v-19.6h9.83v-9.83h-9.83zM31.14 34.32v9.62h-5.11v-12.6h.05l10.86-6.27 2.55 4.42-8.36 4.83zm24.24 13.92h9.83v9.83h-9.83z\"/>" },
    "Fighting": { label: "Lucha", color: "#ff8000", colorDark: "#7f4000", colorLight: "#ffbf7f", glyph: "<path d=\"M40.72 34.03h21.8v9.88h-21.8v-9.88zm13.33-22v17.66h8.47V12.03h-8.47zm-4.86 0h-8.47v17.66h8.47V12.03zm-13.2 0h-8.47v23.22h8.47V12.03zm-13.33 0h-8.47v23.22h8.47V12.03zm14.03 31.43h-22.5v12.97l14.41 9.42 33.92-10.46v-7.38H36.69v-4.54z\" fill=\"#fff\"/>" },
    "Poison": { label: "Veneno", color: "#9141cb", colorDark: "#482065", colorLight: "#c8a0e5", glyph: "<path fill=\"#fff\" d=\"M47.7 56.75c-.55-4.68-4.52-8.31-9.35-8.31s-8.8 3.63-9.35 8.31c-11.51.84-19.8 3.18-19.8 5.93 0 3.46 13.05 6.26 29.15 6.26s29.15-2.8 29.15-6.26c0-2.76-8.29-5.09-19.8-5.93z\"/><circle fill=\"#fff\" cx=\"28.31\" cy=\"23.22\" r=\"11.2\"/><circle fill=\"#fff\" cx=\"51.28\" cy=\"37.57\" r=\"6.64\"/>" },
    "Ground": { label: "Tierra", color: "#915121", colorDark: "#482810", colorLight: "#c8a890", glyph: "<path fill=\"#fff\" d=\"M52.29 16.07h8.31v8.31h-8.31zm-24.44 6.49h6.48v6.48h-6.48zM13.55 8.92h10.81v10.81H13.55zm53.89 39.29V46.1L38.35 34.49 9.26 46.1v2.11l29.09 11.6 29.09-11.6z\"/><path fill=\"#fff\" d=\"M67.52 53.52L38.35 65.3 9.19 53.52l-1.47 3.64 30.63 12.38 30.64-12.38-1.47-3.64z\"/>" },
    "Flying": { label: "Volador", color: "#81b9ef", colorDark: "#405c77", colorLight: "#c0dcf7", glyph: "<path d=\"M23.78 27.7c-1.94 4.43-7.5 23.12-8.81 33.15-.67 5.09-1.31 6.86 0 7.25 1.66.5 8.65-10.31 11.14-14.47 0 0 15.92 2.39 24.09-7.79.19-.24-.02-.59-.32-.53-3.22.55-14.81 2.34-19.94.35 0 0 20.89.81 30.38-14.67.13-.2-.08-.46-.3-.38-3.29 1.19-17.5 5.86-26.01 3.66 0 0 13.83-.81 24.28-10.31S69.6 9.66 68.85 8.91c-1.42-1.42-8.65 2.16-14.47 3.99s-13.14 3.99-17.96 4.99-8.81 1.08-12.64 9.81z\" fill=\"#fff\"/>" },
    "Psychic": { label: "Psíquico", color: "#ef4179", colorDark: "#77203c", colorLight: "#f7a0bc", glyph: "<path d=\"M38.35 16.28c.29 0 .59.16.72.48 2.62 6.29 8.79 10.32 15.47 10.32.71 0 1.43-.05 2.15-.14h.11c.63 0 1.01.73.61 1.26-4.58 5.98-4.58 14.34-.02 20.33.4.52.01 1.25-.61 1.25h-.11c-.72-.09-1.43-.14-2.14-.14-6.68 0-12.85 4.02-15.47 10.32-.13.32-.43.48-.72.48s-.59-.16-.72-.48C35 53.67 28.83 49.64 22.15 49.64c-.71 0-1.43.05-2.15.14h-.11c-.63 0-1.01-.73-.61-1.26 4.58-5.98 4.58-14.34.02-20.33-.4-.52-.01-1.25.61-1.25h.11c.72.09 1.43.14 2.14.14 6.68 0 12.85-4.02 15.47-10.32.13-.32.43-.48.72-.48m0-8.7c-3.84 0-7.28 2.29-8.75 5.84-1.23 2.96-4.22 4.96-7.44 4.96-.34 0-.68-.02-1.02-.07-.4-.05-.81-.08-1.22-.08-3.62 0-6.88 2.02-8.49 5.27a9.42 9.42 0 00.95 9.95c2.19 2.88 2.19 6.9 0 9.77a9.417 9.417 0 00-.97 9.96 9.407 9.407 0 008.49 5.28c.41 0 .82-.03 1.23-.08.34-.04.69-.07 1.03-.07 3.22 0 6.21 1.99 7.44 4.96 1.48 3.55 4.91 5.84 8.75 5.84s7.28-2.29 8.75-5.84c1.23-2.96 4.22-4.96 7.44-4.96.34 0 .68.02 1.02.07.4.05.81.08 1.22.08 3.62 0 6.88-2.02 8.49-5.27a9.42 9.42 0 00-.95-9.95c-2.19-2.88-2.19-6.9 0-9.77 2.21-2.89 2.58-6.7.97-9.96a9.407 9.407 0 00-8.49-5.28c-.41 0-.82.03-1.23.08-.34.04-.69.07-1.03.07-3.22 0-6.21-1.99-7.44-4.96a9.443 9.443 0 00-8.75-5.84z\" fill=\"#fff\"/>" },
    "Bug": { label: "Bicho", color: "#91a119", colorDark: "#48500c", colorLight: "#c8d08c", glyph: "<path d=\"M38.35 28.23c8.1 0 15.19-3.44 19.07-8.57-3.88-6.28-10.97-10.49-19.07-10.49s-15.19 4.21-19.07 10.49c3.88 5.13 10.97 8.57 19.07 8.57zm22.84-4.26c-4.56 5.02-11.7 8.47-19.88 9.14l10.93 34.42c8.67-5.52 14.42-15.13 14.42-26.08 0-6.49-2.02-12.5-5.47-17.48zm-45.67 0c4.56 5.02 11.7 8.47 19.88 9.14L24.47 67.53C15.8 62.01 10.05 52.4 10.05 41.45c0-6.49 2.02-12.5 5.47-17.48zm22.83 30.75c1.66 0 3.31-.37 4.83-1.09l-1.3-4.74a6.554 6.554 0 01-7.07 0l-1.3 4.74c1.53.72 3.18 1.09 4.83 1.09zm0 9.14c2.53 0 4.98-.48 7.27-1.36l-1.33-4.85c-1.85.79-3.86 1.21-5.94 1.21s-4.08-.42-5.94-1.21l-1.33 4.85c2.29.88 4.74 1.36 7.27 1.36z\" fill=\"#fff\"/>" },
    "Rock": { label: "Roca", color: "#afa981", colorDark: "#575440", colorLight: "#d7d4c0", glyph: "<path fill=\"#fff\" d=\"M58.71 18l2.67 11.72-14.39-14.39L58.71 18l-8.43-8.43H26.43L9.57 26.43v23.85l8.23 8.23-4.49-19.72L37.52 63 17.8 58.51l8.63 8.63h23.85l8.43-8.43-19.72 4.49L63.2 38.99l-4.49 19.72 8.43-8.43V26.43L58.71 18z\"/>" },
    "Ghost": { label: "Fantasma", color: "#704170", colorDark: "#382038", colorLight: "#b7a0b7", glyph: "<path d=\"M64.73 37.52c-2.45-.58-4.47.48-5.75 1.48.49-2.06.77-4.09.77-6.02 0-11.82-9.58-21.4-21.4-21.4s-21.4 9.58-21.4 21.4c0 1.93.28 3.96.77 6.02-1.28-.99-3.31-2.06-5.75-1.48-3.51.83-6.4 5.88-6.57 10.24-.03.9 1.07 1.36 1.67.69.97-1.09 2.24-2.21 3.12-1.84 2.88 1.22 3.1 6.32 5.87 6.32 2.43 0 4.52-2.43 5.54-3.86 4.66 8.79 11.84 16.06 16.74 16.06s12.07-7.26 16.74-16.06c1.02 1.43 3.11 3.86 5.54 3.86 2.77 0 2.99-5.1 5.87-6.32.88-.37 2.15.74 3.12 1.84.6.67 1.71.21 1.67-.69-.17-4.36-3.06-9.41-6.57-10.24zm-31.59-2.74c-1.78.83-4.48-1.18-6.03-4.5-1.55-3.32-1.35-6.68.43-7.51 1.78-.83 4.48 1.18 6.03 4.5 1.55 3.32 1.36 6.68-.43 7.51zm16.45-4.5c-1.55 3.32-4.25 5.33-6.03 4.5-1.78-.83-1.98-4.2-.43-7.51 1.55-3.32 4.25-5.33 6.03-4.5 1.78.83 1.98 4.2.43 7.51z\" fill=\"#fff\"/>" },
    "Dragon": { label: "Dragón", color: "#5060e1", colorDark: "#283070", colorLight: "#a7aff0", glyph: "<path d=\"M12.39 23.98c-8.41 11.05-7.23 26.81 3.02 36.47 1.09-3.6 3.14-6.95 6.1-9.6a20.91 20.91 0 01-4.04-10.48c-5.13-3.92-7-10.56-5.08-16.4zm51.92 0c1.92 5.84.05 12.48-5.08 16.4-.38 3.88-1.82 7.47-4.04 10.48 2.96 2.65 5.01 5.99 6.1 9.6 10.25-9.65 11.43-25.42 3.02-36.47zm-12.95 1.33c-1.12-7.41-3.63-15.73-4.89-19.64-.22-.68-1.26-.66-1.44.03-1.17 4.28-2.6 11.09-3.24 14.2-1.07-.2-2.29-.32-3.42-.32s-2.35.11-3.42.32c-.64-3.11-2.07-9.91-3.24-14.2-.19-.69-1.22-.72-1.44-.03-1.26 3.91-3.78 12.22-4.89 19.64-2.67 2.99-4.3 6.93-4.3 11.33 0 6.35 3.37 13.85 8.39 18.21l1.38 12.27c0 1.8 3.37 4.41 7.53 4.41s7.53-2.62 7.53-4.41l1.38-12.27c5.02-4.36 8.39-11.86 8.39-18.21 0-4.4-1.63-8.34-4.3-11.33zM29.81 48.82c-2.98-.92-5.06-3.61-5.15-6.73-.12-3.67.07-7.59.07-7.59l9.2 15.41c-1.61-.37-2.97-.74-4.12-1.09zm17.1 0c-1.14.35-2.51.73-4.12 1.09l9.2-15.41s.19 3.92.07 7.59a7.285 7.285 0 01-5.15 6.73z\" fill=\"#fff\"/>" },
    "Dark": { label: "Siniestro", color: "#50413f", colorDark: "#28201f", colorLight: "#a7a09f", glyph: "<path fill=\"#fff\" d=\"M60.1 20.73s-3.25 4.41-10.78 6.74c.84 2.28 1.32 4.93 1.32 7.9 0 10.15-5.5 18.39-12.28 18.39s-12.28-7.27-12.28-18.39c0-2.95.58-5.58 1.52-7.84-7.67-2.32-10.98-6.8-10.98-6.8s-7.54 8.04-6.83 17.19c.42 5.33 3.3 11.6 10.35 17.38 0 0 7.54 6.66 18.22 6.66s18.22-6.66 18.22-6.66c7.05-5.78 9.93-12.04 10.35-17.38.72-9.15-6.83-17.19-6.83-17.19z\"/><path fill=\"#fff\" d=\"M35.54 28.85c-.96 2-1.58 4.89-1.58 7.72 0 5.08 1.97 9.19 4.39 9.19s4.39-4.12 4.39-9.19c0-2.84-.61-5.73-1.58-7.72-.9.04-1.84.05-2.81.02-.97.03-1.91.02-2.81-.02z\"/>" },
    "Steel": { label: "Acero", color: "#60a1b8", colorDark: "#30505c", colorLight: "#afd0db", glyph: "<path fill=\"#fff\" d=\"M41 27.35l9.18 32.02 17.37-12.62-8.03-24.71L41 27.35zM52.3 37.6c-2.52 0-4.56-2.04-4.56-4.56s2.04-4.56 4.56-4.56 4.56 2.04 4.56 4.56-2.04 4.56-4.56 4.56z\"/><path fill=\"#fff\" d=\"M37.9 38.21l-4.29-14.95 24.07-6.9-1.28-3.93H20.3L9.15 46.75l28.75-8.54zM26.03 15.23c1.87 0 3.38 1.51 3.38 3.38s-1.51 3.38-3.38 3.38-3.38-1.51-3.38-3.38 1.51-3.38 3.38-3.38zm13.01 26.95l-25.69 7.63 25 18.17 6.69-4.87-6-20.93z\"/>" },
    "Fairy": { label: "Hada", color: "#ef70ef", colorDark: "#773877", colorLight: "#f7b7f7", glyph: "<path d=\"M66.36 12.08c-2.18-2.18-15.61-3.16-24.65 5.88-1.55 1.55-2.63 3.4-3.25 5.35-.62-1.96-1.7-3.8-3.25-5.35-9.04-9.04-22.47-8.06-24.65-5.88S7.4 27.69 16.44 36.73c1.91 1.91 4.26 3.11 6.73 3.61-5 4.33-5.57 11.18-4.61 12.52 1.02 1.42 8.4 3.21 14.31-.94-.27.79-.53 1.6-.79 2.44-2.47 8.08-3.39 14.96-2.07 15.36 1.33.41 4.41-5.81 6.88-13.89.62-2.03 1.15-3.99 1.56-5.79.41 1.8.94 3.76 1.56 5.79 2.47 8.08 5.55 14.3 6.88 13.89 1.33-.41.4-7.29-2.07-15.36-.26-.84-.52-1.65-.79-2.44 5.91 4.15 13.3 2.36 14.31.94.96-1.34.39-8.18-4.61-12.52 2.47-.5 4.82-1.7 6.73-3.61 9.04-9.04 8.06-22.47 5.88-24.65zm-27.9 28.05c-4.31 0-8.04-2.45-9.9-6.03 5.01-.02 9.15-3.74 9.81-8.57.02-.12.17-.12.18 0 .66 4.83 4.8 8.56 9.81 8.57-1.86 3.58-5.59 6.03-9.9 6.03Z\" fill=\"#fff\"/>" },
  };

  function typeInfo(typeKey) {
    return TYPE_INFO[typeKey] || null;
  }

  function typeStyleVars(typeKey) {
    var info = typeInfo(typeKey);
    if (!info) {
      return "";
    }
    return "--type-color:" + info.color + ";--type-dark:" + info.colorDark + ";--type-light:" + info.colorLight + ";";
  }

  // Ícono de tipo inline (mismo que app.js) -- necesario acá porque
  // ahora la tarjeta reusa .pokemon-type-badge/.pokemon-move-type
  // tal cual, que esperan este ícono adentro.
  function typeIconSvg(typeKey, size) {
    var info = typeInfo(typeKey);
    if (!info) {
      return "";
    }
    return '<svg class="type-icon" viewBox="' + TYPE_ICON_VIEWBOX + '" width="' + size + '" height="' + size + '" xmlns="http://www.w3.org/2000/svg">' + info.glyph + '</svg>';
  }

  // Traducción de movimientos (09/09/2026, Fase E): MOVE_NAME_ES/
  // translateMoveName() (tabla duplicada de app.js, mismo límite de
  // 64 movimientos) se eliminó -- causaba el bug reportado jugando
  // el hackroom ("el idioma de los movimientos y habilidades se han
  // mezclado"). Ahora usa mon.movesEs, ya resuelto en el backend
  // contra el bridge PKHeX (ver _resolve_move_es() en
  // gym_leaders.py) -- cubre cualquier movimiento real de Gen 6.

  function escapeHtml(value) {
    var div = document.createElement("div");
    div.textContent = value == null ? "" : String(value);
    return div.innerHTML;
  }

  function getOrderFromUrl() {
    var params = new URLSearchParams(window.location.search);
    return Number(params.get("order"));
  }

  // Mismos STAT_ROWS/STATS_TITLE_ICON que app.js (06/09/2026, a
  // pedido del usuario: reusar los mismos íconos de stats que ya
  // existen en la página Pokémon en vez de un set propio). El
  // valor de cada fila siempre es "—" acá (ver buildMonCardHtml) --
  // Total/IV/EV de un Pokémon de un entrenador rival no se pueden
  // saber sin su save real.
  var STATS_TITLE_ICON =
    '<svg viewBox="0 0 1280 685" xmlns="http://www.w3.org/2000/svg">' +
    '<g transform="translate(0,685) scale(0.1,-0.1)" fill="currentColor" stroke="none">' +
    '<path d="M2730 3445 l0 -3405 1000 0 1000 0 0 3405 0 3405 -1000 0 -1000 0 0-3405z"/>' +
    '<path d="M10790 3330 l0 -3290 1005 0 1005 0 0 3290 0 3290 -1005 0 -1005 0 0-3290z"/>' +
    '<path d="M5418 2535 l2 -2535 1000 0 1000 0 0 2535 0 2535 -1002 0 -1003 0 3-2535z"/>' +
    '<path d="M0 1590 l0 -1550 1005 0 1005 0 0 1550 0 1550 -1005 0 -1005 0 0-1550z"/>' +
    '<path d="M8100 1495 l0 -1495 1005 0 1005 0 0 1495 0 1495 -1005 0 -1005 0 0-1495z"/>' +
    "</g></svg>";

  var STAT_ROWS = [
    { label: "HP", color: "#ff5c7a", iconViewBox: "0 0 255.84 224.93", icon: "<path fill=\"currentColor\" d=\"M235.18,20.88C221.78,7.48,204.05.16,185.12.16s-36.72,7.38-50.12,20.77l-7,7-7.11-7.11C107.5,7.43,89.66,0,70.73,0S34.06,7.38,20.72,20.72C7.32,34.12-.05,51.91,0,70.84,0,89.76,7.43,107.5,20.83,120.9l101.86,101.86c1.41,1.41,3.31,2.17,5.15,2.17s3.74-.71,5.15-2.12l102.08-101.7c13.4-13.4,20.77-31.19,20.77-50.12.05-18.93-7.27-36.72-20.66-50.12Z\"/>" },
    { label: "ATK", color: "#ff5252", iconViewBox: "0 0 207.12 207.12", icon: "<path fill=\"currentColor\" d=\"M198.2.56l-43.64,5.42c-2.67.33-4.95.44-7.02,2.41l-72.44,99.59,8.27,8.18,77.02-77.02c2.45-2.46,5.97-2.09,7.97.31,1.97,2.36,1.77,5.54-.99,7.88l-76.41,76.41,8.18,8.27,99.59-72.44c1.97-2.07,2.08-4.35,2.41-7.02l5.42-43.64c.6-4.84-3.51-8.96-8.35-8.35Z\"/><path fill=\"currentColor\" d=\"M25.31,159.53c11.25,2.72,19.51,11.06,22.29,22.24l15.53-15.47-22.31-22.31-15.51,15.54Z\"/><path fill=\"currentColor\" d=\"M23.83,170.28c-6.38-1.73-13.2.08-17.89,4.75-7.23,7.2-7.26,18.9-.06,26.14,7.19,7.24,18.89,7.28,26.14.09,4.69-4.66,6.55-11.46,4.86-17.86-1.69-6.39-6.66-11.4-13.05-13.12Z\"/><path fill=\"currentColor\" d=\"M120.08,149.96c-1.5,1.43-3.43,2.59-5.32,3.17-4.89,1.5-9.61-.06-13.27-3.33-.97-.87-1.58-1.72-2.5-2.64l-24.06-24.15-16.87-16.71c-3.83-3.79-5.71-8.6-4.04-14.09.53-1.76,1.78-3.73,3.13-5.16,3.23-3.41,3.16-8.12-.2-11.11-3.38-3.01-8.07-2.31-11.01,1.26-1.09,1.32-2.05,2.24-3.01,3.79-6.07,9.84-6.03,22.84,1.39,32.24l12.21,12.52,1.16,1.6-9.3,9.07,22.31,22.31,8.63-8.99c.69-.24,1.1-.06,1.79.62l13.01,12.63c9.02,6.96,21.35,7.24,30.88,1.86,1.99-1.13,3.28-2.24,4.93-3.66,3.5-3,4.28-7.61,1.24-11.03-2.97-3.34-7.7-3.43-11.1-.19Z\"/>" },
    { label: "SPA", color: "#ab47bc", iconViewBox: "0 0 195.83 195.38", icon: "<path fill=\"currentColor\" d=\"M34.73,175.67c-14.35,13.63-24.59,23.49-31.65,18.31-3.41-2.5-4.52-9.6-.56-13.69,9.48-9.78,18.15-19.23,27.57-29.15l35.64-37.54,26.2-42.15,30.52-22.73c8.49-6.32,3.72-20.71,6.96-29.71L147.66,0l47,.91,1.17,47.97c-17.03,10.66-35.46,17.55-54.81,23.69-23.51,7.46-33.82,41.16-68.7,67.4l-37.58,35.69ZM178.75,36.15l-.35-18.92c-7.06-.56-12.31-.64-19.29.03-.19,8.46-2.08,13.87-3.64,22.59l23.27-3.7Z\"/>" },
    { label: "DEF", color: "#42a5f5", iconViewBox: "0 0 192.93 225.8", icon: "<path fill=\"currentColor\" d=\"M99.1,225.3h-6.14c-7.06-.87-13.72-3.27-19.98-7.22C33.09,194.8,3.41,152.88.5,105.33l.02-69.88c.64-3.21,2.39-4.56,5.2-5.88L91.02,1.13c3.34-.87,7.72-.83,11.05.04l85.15,28.41c2.9,1.33,4.56,2.7,5.21,5.98l-.02,69.85c-2.33,42.62-26.13,80.27-59.94,104.19-9.81,6.94-21.36,14.1-33.37,15.7ZM162.17,57.28c0-2.35-2.17-4.65-3.79-5.2l-19.36-6.59-12.23-4.07-30.33-9.64.02,162.12c5.89-1.02,10.13-3.7,14.86-6.42,18.01-11.84,32.66-28.4,41.6-48.17,5.39-11.93,9.03-24.29,9.07-37.39l.15-44.63Z\"/>" },
    { label: "SPD", color: "#26c6da", iconViewBox: "0 0 199.94 236.21", icon: "<path fill=\"currentColor\" d=\"M102.28,236.21h-4.61c-17.8-6.1-34.17-15.54-48.66-27.83l-5-4.69c-1.87-1.76-3.31-3.25-5.09-5.12C16.02,174.51,2.48,143.41.01,110.14V36.66c-.01-2.27,2.9-4.7,4.86-5.36L97.75.32c1.85-.62,3.66-.27,5.46.33l91.85,30.65c1.97.66,4.88,3.09,4.88,5.36v73.48c-4.45,58.62-42.56,107.36-97.67,126.08ZM151.1,186.32c19.4-21.06,30.84-47.93,33.14-76.63l.14-65.56-84.41-28.12L15.56,44.13l.14,65.56c2.25,28.69,13.78,55.55,33.12,76.63,2.53,2.98,4.87,5.39,7.91,7.87,12.45,11.55,27.1,20.22,43.28,26.04,19.44-7.03,37.27-18.62,51.08-33.92Z\"/><path fill=\"currentColor\" d=\"M103.76,202.41c-2.9,1.33-4.74,1.28-7.33.1-37.81-17.21-63.55-53.84-65.65-95.45l-.32-6.42v-39.49c0-3.58,2.33-6.72,5.65-7.82l61.48-20.5c1.71-.57,3.09-.56,4.8,0l61.14,20.36c3.46,1.15,5.98,4.15,5.98,7.97v39.88s-.31,5.56-.31,5.56c-2.28,41.64-27.51,78.39-65.42,95.81ZM153.55,106.08c-.56-2.14.33-3.42.33-5.03v-34.65s-46.03-15.31-46.03-15.31l-.23,40.25c-.02,4.2-5.17,6.83-8.76,6.46-3.1-1-6.56-3.04-6.57-6.48l-.2-40.12c-2.69,1.07-5.32,1.72-8.09,2.64l-37.98,12.7v34.97c.53,1.77.59,3.27.4,5.17,2.13,31.2,19.03,59.38,45.68,75.85l.17-32.06c.02-3.99,4.31-6.89,7.88-6.79s7.51,2.92,7.53,6.79l.17,32.06c26.77-16.56,43.75-44.89,45.71-76.45Z\"/>" },
    { label: "SPE", color: "#ffca28", iconViewBox: "0 0 204.4 176.93", icon: "<path fill=\"currentColor\" d=\"M194.5.04L188.89,0c-.66,0-1.12.29-1.18.77-.35-.41-.71-.74-1.06-.74-32.9-.02-69.74,3.25-102.52,13.16-16.69,5.05-33.45,13.24-48.95,22.39-9.95,5.87-22.54,13.33-31.25,21.26-3.78,3.44-4.75,4.37-3.22,10.43,5.49,21.01,9.67,42.4,12.82,64.04.39,2.71.55,5.46.5,8.21l-.23,11.13c-.47,8.4-3.01,16.35-6.31,23.7l.23,2.58h.62c4.93-6,13.77-22.09,15.77-29.43l3.37-12.35c.41-1.51.84-3.11.95-4.62l.9-12.55c.16-1.73.02-12.89.05-16.89l-.04-.21c0-7.86-1.09-12.16-2.53-20.54l14.88-11.75c11.15-8.8,22.83-15.53,35.53-20.46l13.64-5.3c25.28-9.03,50.65-15.87,76.45-22.58,11.65-3.03,21.82-3.78,31.85-12.49,1.93-1.68,3.21-4.35,5.26-5.48V.04h-9.9Z\"/><path fill=\"currentColor\" d=\"M173.61,27.72c-1.78-1.24-5.85-1.25-7.33-.04l-11.45,1.54c-33.23,6.51-79.82,22.8-108.41,43.65-5.24,3.82-10.36,7.68-14.33,13.27-.99,2.15-.07,5.32-.04,8.07l.5,6.4c.04,3.03.08,5.23.36,8.98l26.04-19.29c4.65-3.45,9.07-5.43,14.6-10.03,2.77-2.3,6.92-3,9.41-5.74,2.13-2.34,4.36-2.56,6.76-3.99,11.54-6.84,23.09-12.74,35.27-17.76l15.25-6.29,21.91-10.08c4.5-2.07,12.11-6.05,12.48-7.62.08-.34-.7-1.06-1.02-1.06Z\"/><path fill=\"currentColor\" d=\"M120.45,62.96c-9.37,4.01-18.03,8.33-27.01,13.76-20.37,12.3-39.76,25.87-59,40.52-.37,7.82-1.38,14.84-2.67,22.54l72.44-54.74,3.76-2.86,17.68-12.99c3.2-2.35,6.44-4.18,9.36-7.66-1.9-3.62-9.02-.93-14.55,1.44Z\"/><path fill=\"currentColor\" d=\"M88.71,104.52c-9.15,5.81-17.25,12.65-25.98,19.4l-32.35,25c-1.75,8.14-4.42,15.26-8.71,22.39,2.11.34,3.32-1.65,4.86-3l21.45-18.92,23.31-19.98,16.16-12.89c2.95-2.36,5.67-4.48,8.52-6.98l4.28-3.77c2.68-2.36,6.43-6.29,6.14-8.11-6.7.57-12.17,3.37-17.68,6.86Z\"/>" },
  ];

  function buildMonCardHtml(mon, baseUrl) {
    var spriteUrl = baseUrl + "/sprites/pokemon/" + mon.speciesId + ".png";
    var primaryType = (mon.typeKeys || [])[0];

    // Insignia de tipo -- solo ícono (06/09/2026, a pedido del
    // usuario: "quitemosle el texto... dejemosle solo el ícono con
    // su color respectivo para que entren dos en una fila"). Sigue
    // siendo el mismo círculo de color de .pokemon-type-badge, sin
    // la etiqueta de texto al lado.
    var typesHtml = (mon.typeKeys || []).map(function (typeKey) {
      var info = typeInfo(typeKey);
      return (
        '<span class="pokemon-type-badge mondetail-type-icon-only" style="' + typeStyleVars(typeKey) + '" title="' + (info ? escapeHtml(info.label) : "") + '">' +
          typeIconSvg(typeKey, 12) +
        "</span>"
      );
    }).join("");

    // Stats: mismos íconos que la página Pokémon (color + glifo),
    // pero sin el valor -- Total/IV/EV de un Pokémon de un
    // entrenador rival no se pueden saber sin su save real, por eso
    // un único aviso "No Disponible" para todo el bloque en vez de
    // "—" fila por fila (estructura original, con el encabezado
    // Total/IV/EV).
    var statsRowsHtml = STAT_ROWS.map(function (stat) {
      return (
        '<div class="mondetail-stat-row">' +
          '<svg class="pokemon-stat-icon" style="color:' + stat.color + '" viewBox="' + stat.iconViewBox + '">' + stat.icon + "</svg>" +
          "<span>" + stat.label + "</span>" +
        "</div>"
      );
    }).join("");

    // Movimientos: 2 columnas x 2 filas (06/09/2026, a pedido del
    // usuario), con el mismo estilo que .pokemon-move-row/
    // .pokemon-move-type de la página Pokémon -- ahora con el TIPO
    // REAL de cada movimiento (moveTypeKeys, curado en
    // data/gym_leaders.json vía MOVE_TYPE_KEYS en gym_leaders.py:
    // es un dato único y bien documentado en toda fuente Pokémon,
    // no como los nombres de líderes/ciudades, así que no hacía
    // falta dejarlo "No disponible" -- solo faltaba curarlo).
    //
    // Clickeable (07/09/2026, a pedido del usuario: "en donde haya
    // una habilidad o movimiento se debería poder acceder a su
    // información") -- data-move-name lleva el nombre en INGLÉS
    // (mon.moves[index], sin traducir) porque
    // get_move_modal_data_by_name() normaliza contra el identifier
    // real de PokéAPI, que está en inglés -- ver
    // MoveDescriptionCatalog.get_id_by_name().
    var moveTypeKeys = mon.moveTypeKeys || [];
    var movesEs = mon.movesEs || [];
    var movesHtml = (mon.moves || []).length
      ? mon.moves.map(function (name, index) {
          var moveType = moveTypeKeys[index];
          var nameEs = movesEs[index] || name;
          return (
            '<div class="pokemon-move-row" data-move-name="' + escapeHtml(name) + '">' +
              '<span class="pokemon-move-name">' + escapeHtml(nameEs) + "</span>" +
              '<span class="pokemon-move-type" style="' + typeStyleVars(moveType) + '">' + typeIconSvg(moveType, 16) + "</span>" +
            "</div>"
          );
        }).join("")
      : '<div class="pokemon-move-row empty"><span class="pokemon-move-name">No disponible</span></div>';

    var itemText = mon.item ? escapeHtml(mon.item) : "Ninguno";

    // Naturaleza: "NN" (06/09/2026) -- no hay forma de saberla sin
    // el save real del entrenador rival, a diferencia de la
    // habilidad (ver abajo). Filas de texto simples, SIN el borde
    // de .pokemon-card-ability -- a pedido del usuario, "dejalos
    // como estaba antes".
    //
    // Habilidad: curada en data/gym_leaders.json/
    // gym_leaders_rrss.json (investigada contra Bulbapedia + un
    // playthrough completo de ORAS) -- a diferencia de
    // Naturaleza/IVs/EVs (que NUNCA se pueden saber sin el save
    // real del entrenador rival), la habilidad de un Pokémon de un
    // líder de gimnasio SÍ está fija en los datos del juego.
    // abilityEs se resuelve en el backend vía el bridge PKHeX
    // (09/09/2026, Fase E -- ver _resolve_ability_es() en
    // gym_leaders.py), no con un diccionario local.
    return (
      '<div class="mondetail-card">' +
        '<div class="mondetail-left">' +
          '<div class="mondetail-sprite-box" style="' + typeStyleVars(primaryType) + '">' +
            '<img class="mondetail-sprite" src="' + spriteUrl + '" alt="' + escapeHtml(mon.species || "") + '" />' +
            (mon.isAce ? '<span class="nz-leader-ace-tag mondetail-ace-badge">Ace</span>' : "") +
          "</div>" +
          '<div class="mondetail-name" data-species-id="' + mon.speciesId + '" title="Ver Pokédex de la especie">' +
            escapeHtml(mon.species || "") + " - Nv." + mon.level +
          "</div>" +
          '<div class="mondetail-types">' + typesHtml + "</div>" +
          '<div class="mondetail-info-rows">' +
            '<div class="mondetail-info-row"><strong>Naturaleza:</strong> <em>NN</em></div>' +
            '<div class="mondetail-info-row"><strong>Habilidad:</strong> ' +
              (mon.ability
                ? '<span class="ability-name" data-ability-name="' + escapeHtml(mon.ability) + '">' +
                  escapeHtml(mon.abilityEs || mon.ability) + "</span>"
                : "—") +
            "</div>" +
            '<div class="mondetail-info-row"><strong>Objeto:</strong> ' + itemText + "</div>" +
          "</div>" +
        "</div>" +
        '<div class="mondetail-right">' +
          '<div class="mondetail-stats">' +
            '<div class="mondetail-stats-header"><span></span><span>Total</span><span>IV</span><span>EV</span></div>' +
            '<div class="mondetail-stats-body">' +
              '<div class="mondetail-stats-labels">' + statsRowsHtml + "</div>" +
              '<div class="mondetail-na-overlay"><em>No Disponible</em></div>' +
            "</div>" +
          "</div>" +
          '<div class="mondetail-divider"></div>' +
          '<div class="mondetail-moves-grid">' + movesHtml + "</div>" +
        "</div>" +
      "</div>"
    );
  }

  function render(leader, baseUrl) {
    var titleEl = document.getElementById("leader-window-title");
    var subtitleEl = document.getElementById("leader-window-subtitle");
    var cardsEl = document.getElementById("leader-window-cards");

    if (!leader) {
      titleEl.textContent = "No se encontró el líder";
      subtitleEl.textContent = "";
      return;
    }

    document.title = "Equipo de " + (leader.nameEs || leader.name || "líder");
    titleEl.textContent = "Equipo de " + (leader.nameEs || leader.name || "—");
    subtitleEl.textContent =
      (leader.badgeNameEs || leader.badgeName || "") + " · " + (leader.gymLocationEs || leader.gymLocation || "") +
      " · Nivel máximo permitido: Nv. " + leader.levelCap +
      " · " + (leader.earned ? "Medalla obtenida" : "Medalla pendiente");

    cardsEl.innerHTML = (leader.team || [])
      .map(function (mon) {
        return buildMonCardHtml(mon, baseUrl);
      })
      .join("");
  }

  // ===================== MODALES DE MOVIMIENTO / HABILIDAD (07/09/2026) =====================
  // Mismo mecanismo que app.js (página Pokémon), extendido acá a
  // pedido del usuario ("en donde haya una habilidad o movimiento
  // se debería poder acceder a su información") -- esta ventana es
  // standalone (no comparte JS con app.js), así que necesita su
  // propia copia chica de openModal/closeModal y del wiring de
  // cierre, mismo criterio ya usado para
  // typeInfo/typeStyleVars/typeIconSvg/escapeHtml más arriba.

  var MOVE_CATEGORY_LABELS = {
    Physical: "Físico",
    Special: "Especial",
    Status: "Estado",
  };

  function openModal(id) {
    document.getElementById(id).hidden = false;
  }

  function closeModal(id) {
    document.getElementById(id).hidden = true;
  }

  function initModalActions() {
    document.querySelectorAll("[data-close-modal]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        closeModal(btn.dataset.closeModal);
      });
    });

    document.querySelectorAll(".nz-modal-overlay").forEach(function (overlay) {
      overlay.addEventListener("click", function (event) {
        if (event.target === overlay) {
          overlay.hidden = true;
        }
      });
    });

    // Delegación sobre el contenedor de tarjetas -- se reconstruye
    // entero cada vez que llega un dato nuevo (render(), una sola
    // vez al abrir esta ventana), mismo criterio que
    // initPokemonPageActions() en app.js.
    var cardsEl = document.getElementById("leader-window-cards");
    cardsEl.addEventListener("click", function (event) {
      // Pokédex de especie (08/09/2026, a pedido del usuario:
      // "extiende el modal de pokedex a los pokes de los lideres
      // de gimnasio").
      var speciesEl = event.target.closest(".mondetail-name[data-species-id]");
      if (speciesEl) {
        openSpeciesModal(Number(speciesEl.dataset.speciesId));
        return;
      }

      var moveRow = event.target.closest(".pokemon-move-row[data-move-name]");
      if (moveRow) {
        openMoveModal(moveRow.dataset.moveName);
        return;
      }

      var abilityEl = event.target.closest(".ability-name[data-ability-name]");
      if (abilityEl) {
        openAbilityModal(abilityEl.dataset.abilityName, abilityEl.textContent);
      }
    });
  }

  function openMoveModal(moveName) {
    document.getElementById("pkm-move-modal-title").textContent = "Cargando...";
    document.getElementById("pkm-move-modal-type").textContent = "";
    document.getElementById("pkm-move-modal-type").style.cssText = "";
    document.getElementById("pkm-move-modal-category").textContent = "";
    document.getElementById("pkm-move-modal-power").textContent = "—";
    document.getElementById("pkm-move-modal-accuracy").textContent = "—";
    document.getElementById("pkm-move-modal-pp").textContent = "—";
    document.getElementById("pkm-move-modal-description").textContent = "";

    openModal("pkm-modal-move");

    window.pywebview.api.get_move_modal_data_by_name(moveName).then(function (data) {
      if (!data || data.error) {
        document.getElementById("pkm-move-modal-title").textContent = "No se pudo cargar";
        document.getElementById("pkm-move-modal-description").textContent =
          "No se pudo obtener el detalle de este movimiento.";
        return;
      }

      document.getElementById("pkm-move-modal-title").textContent = data.name || "—";

      var typeEl = document.getElementById("pkm-move-modal-type");
      var ti = typeInfo(data.typeKey);
      typeEl.style.cssText = typeStyleVars(data.typeKey);
      typeEl.innerHTML = typeIconSvg(data.typeKey, 14) + "<span>" + (ti ? ti.label : data.type || "") + "</span>";

      document.getElementById("pkm-move-modal-category").textContent =
        MOVE_CATEGORY_LABELS[data.categoryKey] || data.categoryKey || "—";

      document.getElementById("pkm-move-modal-power").textContent =
        data.power != null ? data.power : "—";
      document.getElementById("pkm-move-modal-accuracy").textContent =
        data.accuracy != null ? data.accuracy + "%" : "—";
      document.getElementById("pkm-move-modal-pp").textContent =
        data.basePP != null ? data.basePP : "—";

      document.getElementById("pkm-move-modal-description").textContent =
        data.descriptionEs || "Descripción no disponible.";
    });
  }

  function openAbilityModal(abilityName, displayedText) {
    document.getElementById("pkm-ability-modal-title").textContent = displayedText || "Cargando...";
    document.getElementById("pkm-ability-modal-description").textContent = "";

    openModal("pkm-modal-ability");

    window.pywebview.api.get_ability_modal_data_by_name(abilityName).then(function (data) {
      document.getElementById("pkm-ability-modal-description").textContent =
        (data && data.descriptionEs) || "Descripción no disponible.";
    });
  }

  // ===================== MODAL POKÉDEX DE ESPECIE (08/09/2026) =====================
  // Extendido acá a pedido del usuario ("extiende el modal de
  // pokedex a los pokes de los lideres de gimnasio") -- copiado de
  // openSpeciesModal()/initSpeciesModalActions() en app.js (página
  // Pokémon), adaptado al criterio de este archivo standalone: usa
  // window.pywebview.api.* directo (sin el wrapper api() de
  // app.js) y spriteBaseUrl en vez de la variable homónima que
  // vive en la clausura de app.js. Las habilidades del panel
  // izquierdo del modal de especie tienen ID numérico real (vienen
  // del bridge PKHeX, no del dataset curado de gym_leaders.json),
  // así que usan get_ability_modal_data(id) -- openAbilityModalById()
  // más abajo, DISTINTA de openAbilityModal(name, texto) de arriba
  // (esa es para la habilidad de la propia tarjeta del líder, que
  // sí viene por nombre).

  var BASE_STAT_BAR_COLORS = {
    hp: "#22c55e",
    attack: "#ef4444",
    defense: "#f59e0b",
    spAttack: "#3b82f6",
    spDefense: "#a855f7",
    speed: "#22d3ee",
  };

  var BASE_STAT_BAR_MAX = 255;

  function formatMultiplier(multiplier) {
    if (multiplier === 0) { return "0×"; }
    if (multiplier === 0.25) { return "¼×"; }
    if (multiplier === 0.5) { return "½×"; }
    return multiplier + "×";
  }

  function renderTypeEffectGrid(containerId, entries) {
    var container = document.getElementById(containerId);

    if (!entries || !entries.length) {
      container.innerHTML = '<span class="pkm-modal-stat-label">Ninguna</span>';
      return;
    }

    container.innerHTML = entries.map(function (entry) {
      var info = typeInfo(entry.typeKey);
      return (
        '<span class="pokemon-type-badge" style="' + typeStyleVars(entry.typeKey) + '">' +
        typeIconSvg(entry.typeKey, 14) +
        "<span>" + (info ? info.label : entry.typeKey) + " " + formatMultiplier(entry.multiplier) + "</span>" +
        "</span>"
      );
    }).join("");
  }

  function openAbilityModalById(abilityId, abilityName) {
    document.getElementById("pkm-ability-modal-title").textContent = abilityName || "Cargando...";
    document.getElementById("pkm-ability-modal-description").textContent = "";

    openModal("pkm-modal-ability");

    window.pywebview.api.get_ability_modal_data(abilityId).then(function (data) {
      document.getElementById("pkm-ability-modal-description").textContent =
        (data && data.descriptionEs) || "Descripción no disponible.";
    });
  }

  function openSpeciesModal(speciesId) {
    document.getElementById("pkm-species-modal-name").textContent = "Cargando...";
    document.getElementById("pkm-species-modal-dexnum").textContent = "";
    document.getElementById("pkm-species-modal-artwork").src = "";
    document.getElementById("pkm-species-modal-gender").innerHTML = "";
    document.getElementById("pkm-species-modal-types").innerHTML = "";
    document.getElementById("pkm-species-modal-description").textContent = "";
    document.getElementById("pkm-species-modal-height").textContent = "—";
    document.getElementById("pkm-species-modal-weight").textContent = "—";
    document.getElementById("pkm-species-modal-genus").textContent = "—";
    document.getElementById("pkm-species-modal-ability1").textContent = "—";
    document.getElementById("pkm-species-modal-ability1").removeAttribute("data-ability-id");
    var ability2ResetEl = document.getElementById("pkm-species-modal-ability2");
    ability2ResetEl.textContent = "";
    ability2ResetEl.hidden = true;
    ability2ResetEl.removeAttribute("data-ability-id");
    document.getElementById("pkm-species-modal-abilityhidden").textContent = "—";
    document.getElementById("pkm-species-modal-abilityhidden").removeAttribute("data-ability-id");
    document.getElementById("pkm-species-modal-stats").innerHTML = "";
    document.getElementById("pkm-species-modal-evolutions").innerHTML = "";
    document.getElementById("pkm-species-modal-weaknesses").innerHTML = "";
    document.getElementById("pkm-species-modal-resistances").innerHTML = "";
    document.getElementById("pkm-species-modal-immunities").innerHTML = "";

    openModal("pkm-modal-species");

    window.pywebview.api.get_species_modal_data(speciesId).then(function (data) {
      if (!data || data.error) {
        document.getElementById("pkm-species-modal-name").textContent = "No se pudo cargar";
        return;
      }

      document.getElementById("pkm-species-modal-name").textContent = data.name || "—";
      document.getElementById("pkm-species-modal-dexnum").textContent = "#" + String(speciesId).padStart(3, "0");
      document.getElementById("pkm-species-modal-artwork").src =
        spriteBaseUrl + "/sprites/species_artwork/" + speciesId + ".png";

      var typesHtml = "";
      if (data.type1Key) {
        var t1 = typeInfo(data.type1Key);
        typesHtml += '<span class="pokemon-type-badge" style="' + typeStyleVars(data.type1Key) + '">' +
          typeIconSvg(data.type1Key, 14) + "<span>" + (t1 ? t1.label : "") + "</span></span>";
      }
      if (data.type2Key) {
        var t2 = typeInfo(data.type2Key);
        typesHtml += '<span class="pokemon-type-badge" style="' + typeStyleVars(data.type2Key) + '">' +
          typeIconSvg(data.type2Key, 14) + "<span>" + (t2 ? t2.label : "") + "</span></span>";
      }
      document.getElementById("pkm-species-modal-types").innerHTML = typesHtml;

      document.getElementById("pkm-species-modal-description").textContent =
        data.description || "Descripción no disponible.";

      document.getElementById("pkm-species-modal-height").textContent =
        data.heightM != null ? data.heightM + " m" : "—";
      document.getElementById("pkm-species-modal-weight").textContent =
        data.weightKg != null ? data.weightKg + " kg" : "—";
      document.getElementById("pkm-species-modal-genus").textContent = data.genus || "—";

      var ability1El = document.getElementById("pkm-species-modal-ability1");
      ability1El.textContent = data.ability1Name || "—";
      if (data.ability1Id != null) {
        ability1El.dataset.abilityId = data.ability1Id;
        ability1El.dataset.abilityName = data.ability1Name || "";
      } else {
        delete ability1El.dataset.abilityId;
        delete ability1El.dataset.abilityName;
      }

      var ability2El = document.getElementById("pkm-species-modal-ability2");
      var hasAbility2 = data.ability2Id != null && data.ability2Id !== data.ability1Id;
      ability2El.hidden = !hasAbility2;
      if (hasAbility2) {
        ability2El.textContent = data.ability2Name || "—";
        ability2El.dataset.abilityId = data.ability2Id;
        ability2El.dataset.abilityName = data.ability2Name || "";
      } else {
        ability2El.textContent = "";
        delete ability2El.dataset.abilityId;
        delete ability2El.dataset.abilityName;
      }

      var abilityHiddenEl = document.getElementById("pkm-species-modal-abilityhidden");
      abilityHiddenEl.textContent = data.abilityHiddenName || "—";
      if (data.abilityHiddenId != null) {
        abilityHiddenEl.dataset.abilityId = data.abilityHiddenId;
        abilityHiddenEl.dataset.abilityName = data.abilityHiddenName || "";
      } else {
        delete abilityHiddenEl.dataset.abilityId;
        delete abilityHiddenEl.dataset.abilityName;
      }

      var stats = data.baseStats || {};
      var statsOrder = [
        { key: "hp", label: "HP" }, { key: "attack", label: "ATK" }, { key: "spAttack", label: "SPA" }, { key: "defense", label: "DEF" }, { key: "spDefense", label: "SPD" }, { key: "speed", label: "SPE" },
      ];
      document.getElementById("pkm-species-modal-stats").innerHTML = statsOrder.map(function (s) {
        var value = stats[s.key] != null ? stats[s.key] : 0;
        var barPercent = Math.min(100, (value / BASE_STAT_BAR_MAX) * 100);
        var barColor = BASE_STAT_BAR_COLORS[s.key];
        return (
          '<div class="pkm-species-stat-card">' +
          '<span class="pkm-species-stat-card-value">' + (stats[s.key] != null ? stats[s.key] : "—") + "</span>" +
          '<span class="pkm-species-stat-card-label">' + s.label + "</span>" +
          '<div class="pkm-species-stat-bar-track"><div class="pkm-species-stat-bar-fill" style="width:' + barPercent + "%;background:" + barColor + ';"></div></div>' +
          "</div>"
        );
      }).join("");

      var evolutionData = data.evolutionChain || null;
      var ancestors = (evolutionData && evolutionData.ancestors) || [];
      var currentNode = evolutionData && evolutionData.current;

      function stageHtml(stage) {
        var stageSpriteUrl = spriteBaseUrl + "/sprites/pokemon/" + stage.speciesId + ".png";
        return (
          '<div class="pkm-species-evolution-stage' + (stage.isCurrent ? " current" : "") + '" data-species-id="' + stage.speciesId + '">' +
          '<img src="' + stageSpriteUrl + '" alt="" />' +
          '<span class="pkm-species-evolution-stage-name">' + escapeHtml(stage.name || "—") + "</span>" +
          "</div>"
        );
      }

      function connectorHtml(transition) {
        if (!transition) {
          return (
            '<span class="pkm-species-evolution-connector">' +
            '<svg class="pkm-species-evolution-arrow" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">' +
            '<line x1="4" y1="12" x2="18" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>' +
            '<polyline points="13,7 18,12 13,17" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
            "</span>"
          );
        }

        var innerHtml;

        if (transition.level != null && transition.level > 0) {
          innerHtml = '<span class="pkm-species-evolution-connector-label">Nv. ' + transition.level + "</span>";
        } else if (transition.itemId != null) {
          innerHtml = '<img class="pkm-species-evolution-item-sprite" src="' + spriteBaseUrl + "/sprites/items/" + transition.itemId + '.png" alt="" onerror="this.style.display=\'none\'" />';
        } else if (transition.moveName) {
          innerHtml = '<span class="pkm-species-evolution-connector-label">' + escapeHtml(transition.moveName) + "</span>";
        } else if (transition.teammateName) {
          innerHtml = '<span class="pkm-species-evolution-connector-label">' + escapeHtml(transition.teammateName) + "</span>";
        } else if (transition.conditionLabel) {
          innerHtml = '<span class="pkm-species-evolution-connector-label">' + escapeHtml(transition.conditionLabel) + "</span>";
        } else {
          innerHtml =
            '<svg class="pkm-species-evolution-arrow" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">' +
            '<line x1="4" y1="12" x2="18" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>' +
            '<polyline points="13,7 18,12 13,17" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        }

        return (
          '<span class="pkm-species-evolution-connector" title="' + escapeHtml(transition.description || "") + '">' +
          innerHtml +
          "</span>"
        );
      }

      function renderForwardNode(node) {
        var html = stageHtml(node);
        var children = node.children || [];

        if (children.length === 0) {
          return html;
        }

        if (children.length === 1) {
          html += connectorHtml(children[0].transition) + renderForwardNode(children[0].node);
          return html;
        }

        var branchesHtml = children.map(function (child) {
          return (
            '<div class="pkm-species-evolution-branch-row">' +
            connectorHtml(child.transition) + renderForwardNode(child.node) +
            "</div>"
          );
        }).join("");

        html += '<div class="pkm-species-evolution-branches">' + branchesHtml + "</div>";
        return html;
      }

      var stagesHtml = "";

      ancestors.forEach(function (ancestor) {
        stagesHtml += stageHtml(ancestor) + connectorHtml(ancestor.transitionToNext);
      });

      if (currentNode) {
        stagesHtml += renderForwardNode(currentNode);
      }

      var hasChain = ancestors.length > 0 || (currentNode && currentNode.children && currentNode.children.length > 0);

      document.getElementById("pkm-species-modal-evolutions").innerHTML =
        hasChain ? stagesHtml : '<span class="pkm-modal-stat-label">No evoluciona</span>';

      renderTypeEffectGrid("pkm-species-modal-weaknesses", data.weaknesses);
      renderTypeEffectGrid("pkm-species-modal-resistances", data.resistances);
      renderTypeEffectGrid("pkm-species-modal-immunities", data.immunities);
    });
  }

  function initSpeciesModalActions() {
    var modalBody = document.getElementById("pkm-modal-species");
    if (!modalBody) {
      return;
    }

    modalBody.addEventListener("click", function (event) {
      var abilityRow = event.target.closest(
        ".pkm-species-ability-row[data-ability-id], .pkm-species-info-value[data-ability-id]"
      );
      if (abilityRow) {
        openAbilityModalById(
          Number(abilityRow.dataset.abilityId),
          abilityRow.dataset.abilityName || ""
        );
        return;
      }

      var stage = event.target.closest(".pkm-species-evolution-stage[data-species-id]");
      if (stage) {
        openSpeciesModal(Number(stage.dataset.speciesId));
      }
    });
  }

  function init() {
    var order = getOrderFromUrl();

    initModalActions();
    initSpeciesModalActions();

    window.pywebview.api.get_server_base_url().then(function (baseUrl) {
      spriteBaseUrl = baseUrl || "";
      window.pywebview.api.get_leader_team_window_data(order).then(function (leader) {
        render(leader, baseUrl || "");
      });
    });
  }

  if (window.pywebview) {
    init();
  } else {
    window.addEventListener("pywebviewready", init);
  }
})();
