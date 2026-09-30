legacy/gui_tkinter -- GUI vieja (Tkinter/ttkbootstrap), archivada (Bloque 9.3, 30/09/2026)

Era la interfaz de escritorio original de DexRelay. Fue reemplazada por
completo por la GUI v2 (pywebview, app/gui_web/) y desde entonces no se
usa: nada en app/ la importa.

Se conserva como historial (mismo criterio que los probes), NO como
código ejecutable: sus imports siguen diciendo `app.gui.*` y necesita
`ttkbootstrap` y `Pillow`, que ya no están en requirements.txt ni se
empaquetan en el build (DexRelay.spec). Para volver a correrla
habría que moverla de nuevo a app/gui/ y reinstalar esas dos
dependencias.
