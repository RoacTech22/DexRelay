# Publicar la landing de DexRelay

Esta carpeta es un sitio estático: no necesita servidor ni instalación. Basta con subirla a un hosting estático.

## Opción recomendada: GitHub Pages (gratis)

1. En GitHub, abre el repositorio `RoacTech22/DexRelay` (o crea uno nuevo, por ejemplo `dexrelay-web`).
2. Sube el contenido de esta carpeta a una carpeta `docs/` en la rama `main`. El archivo `index.html` debe quedar en `docs/index.html`.
3. Ve a **Settings → Pages**. En *Build and deployment* elige **Deploy from a branch**, rama `main` y carpeta `/docs`, y guarda.
4. En uno o dos minutos la página estará en `https://roactech22.github.io/DexRelay/`.

Cada vez que subas cambios a `docs/`, la página se actualiza sola. HTTPS viene incluido.

## Si la URL final es distinta

Las rutas internas son relativas, así que la página funciona en cualquier carpeta. Pero estas URLs absolutas apuntan a `https://roactech22.github.io/DexRelay/` y hay que cambiarlas (buscar y reemplazar) por tu URL final:

- `index.html` y `en/index.html`: etiquetas `canonical`, `hreflang`, `og:url`, `og:image`, `twitter:image` y el JSON-LD (`url` e `image`).
- `robots.txt`: la línea `Sitemap:`.
- `sitemap.xml`: las etiquetas `<loc>` y los enlaces `hreflang`.

Si más adelante compras un dominio propio (por ejemplo `dexrelay.app`): en Settings → Pages escribe el dominio en *Custom domain*, crea el registro DNS que GitHub indica y vuelve a reemplazar la URL en esos tres archivos.

## Alternativas gratuitas

- **Cloudflare Pages**: conecta el repositorio, deja vacío el comando de build y pon como carpeta de salida `docs` (o la raíz). Da una URL `nombre.pages.dev` en la raíz del dominio.
- **Netlify**: arrastra la carpeta a netlify.com/drop y obtienes una URL al instante.

## Después de publicar

1. Entra a **Google Search Console** y agrega la URL de la página. Si usas GitHub Pages sin dominio propio, elige la verificación por etiqueta HTML o por archivo.
2. Envía el `sitemap.xml` en la sección *Sitemaps*.
3. Prueba cómo se ve al compartir el enlace en Discord o X para confirmar la imagen de vista previa.
4. Haz lo mismo en Bing Webmaster Tools (también sirve para DuckDuckGo).

## Contenido de la carpeta

- `index.html`, `styles.css`: la página en español. `en/index.html`: la versión en inglés (comparte estilos y assets).
- `assets/`: imágenes (WebP), fuentes de la app (Inter y Space Grotesk) e iconos.
- `404.html`: página de error, que GitHub Pages usa solo.
- `robots.txt`, `sitemap.xml`: para buscadores.
- `.nojekyll`: evita que GitHub Pages procese los archivos con Jekyll.

## Actualizar la versión de DexRelay

Cuando publiques una nueva versión de la app, cambia el texto `v0.4.0-alpha` en `index.html` y `en/index.html` (etiqueta del hero, preguntas frecuentes, nota bajo el botón final y JSON-LD `softwareVersion`). Los botones de descarga apuntan a la página de releases, así que no hay que tocar enlaces.

## Capturas de pantalla

Las capturas de la app están en `assets/screens/` (formato `.webp`). Para actualizarlas, reemplaza el archivo conservando el nombre; si cambia la proporción de la imagen, ajusta también los atributos `width` y `height` de su `<img>` en `index.html` y `en/index.html`.

## Idioma

El selector ES / EN del menú cambia entre `index.html` (español) y `en/index.html` (inglés) y recuerda la elección del visitante en su navegador. Los buscadores ven ambas versiones gracias a las etiquetas `hreflang` y al `sitemap.xml`.

## Logo

En `assets/brand/` están los SVG del logo (marca + wordmark) para fondo oscuro y claro, y la marca sola. El texto está convertido a trazados, así que no necesita la fuente instalada.
