# Gate P0 · Licencias del plugin editor de vídeo

**Autor:** Apollo (investigación técnica) · **Fecha:** 2026-11-08 (Caracas, UTC-4) · **Estado:** gate P0 cerrado con 3 verdes, 2 amarillos y 1 rojo condicionado.
**Alcance:** decidir con qué piezas se puede construir el plugin local del editor de vídeo (plan `PLAN-CONSOLIDADO.md` §«Licencias y costes» y §«Tres bases») sin riesgo legal evitable.
**Método:** texto de licencia leído en la fuente primaria (LICENSE/`Cargo.toml` del tag exacto, `ffmpeg -L` del binario instalado), no en resúmenes. Cada afirmación lleva URL y fecha de consulta. Esto **no es asesoría legal**: es evidencia documental para que Tormen decida dónde pagar abogado.
**Nivel de evidencia:** alto en FFmpeg, HyperFrames, FilmCraft (texto de licencia leído). Medio en Remotion (LICENSE.md + FAQ oficiales, sin carta de Remotion AG). Bajo en GSAP directo (gsap.com bloquea scraping → texto obtenido de espejo Wayback del 2026-10-29; ver «qué no se pudo verificar»).

---

## 1. Veredicto de un vistazo

| # | Componente | Veredicto | Condición que lo mantiene en verde/amarillo |
|---|---|---|---|
| 1 | **FFmpeg GPL (binario del sistema)** | 🟢 **VERDE** si se **invoca como proceso externo** y **no se empaqueta** | El plugin llama `ffmpeg.exe` por ruta/CLI; el binario lo aporta la máquina. Empaquetarlo pasa a 🟡/🔴 (§2.3) |
| 2 | **HyperFrames v0.9.23 (framework)** | 🟢 **VERDE** | Apache-2.0 sin campos de uso. Obligaciones: aviso de licencia + NOTICE si se redistribuye |
| 3 | **GSAP 3.15.0 (dependencia de `@hyperframes/studio`)** | 🟡 **AMARILLO** | No es open source; prohíbe «Competitive Products» (constructores visuales de animación tipo Webflow). No usar GSAP ni `@hyperframes/studio` en la UI del plugin |
| 4 | **Remotion v4.0.541** | 🟡 **AMARILLO** para uso propio de un individuo · 🔴 **ROJO** si el plugin se distribuye/vende a terceros | Licencia propietaria «source-available», no OSI. Embeber el Player o dejar que terceros rendericen su propio proyecto Remotion = plan Automators o prohibido |
| 5 | **FilmCraft v0.18.0** | 🟢 **VERDE** | MIT OR Apache-2.0, sin FFmpeg dentro (codecs propios en Rust). Marca «ArtCraft/FilmCraft» no licenciada: no usar su nombre/logo en material nuestro |
| 6 | **Nota «heat fix»** | ⚪ **SIN EVIDENCIA** | Ninguna fuente —oficial ni de terceros— asocia «heat fix» a HyperFrames (§6) |

**Regla de oro que sale de este gate:** el plugin puede ser **propietario y venderse** mientras (a) no redistribuya binarios GPL, (b) no embeber código de Remotion en un producto que terceros usen para renderizar, y (c) no construya un editor visual de animación sin código sobre GSAP.

---

## 2. FFmpeg — build GPL

### 2.1 Qué hay realmente instalado (medido, no asumido)

```
ffmpeg version n9.0.1-11-ge47273f4d9-20260831
configuration: ... --enable-gpl --enable-version3 ... --enable-libx264 --enable-libx265 --enable-libxvid
               --enable-libass --enable-libfreetype --enable-libmp3lame --enable-libopus --enable-libvpx ...
ruta: C:\Users\EgtYP\AppData\Local\hermes\tools\ffmpeg-9.0.1-win32-x64\bin\ffmpeg.exe (144.862.208 bytes, 2026-10-03)
```

`ffmpeg -L` (mismo binario, 2026-11-08) imprime:

> "ffmpeg is free software; you can redistribute it and/or modify it under the terms of the **GNU General Public License** as published by the Free Software Foundation; **either version 3 of the License, or (at your option) any later version**."

**Corrección al inventario de fase 0:** no es «GPL» a secas. El flag `--enable-version3` eleva el build a **GPLv3-or-later**, que añade obligaciones que GPLv2 no tenía (información de instalación para «User Products», §6 de GPLv3; y la prohibición de restricciones adicionales tipo DRM/anti-reverse-engineering). También es un build **estático** (`--pkg-config-flags=--static`), así que libx264/libx265 van dentro del ejecutable.

### 2.2 Invocar el binario ≠ empaquetar el binario

FFmpeg lo dice explícitamente en su página legal: la checklist que publica es «**for LGPL compliance when linking against the FFmpeg libraries**» — es decir, su propio marco de cumplimiento presupone **enlazado**, no ejecución. Y el paso 1 de esa checklist es «Compile FFmpeg **without** "--enable-gpl"», paso 18 «Make sure your program is not using any GPL libraries (notably **libx264**)». Con este build **ambos pasos son imposibles**, luego la vía LGPL está cerrada de origen.

El criterio para decidir si hay «obra combinada» o «programas separados» lo da la FSF (GNU GPL FAQ, `#MereAggregation`):

> "Where's the line between two separate programs, and one program with two parts? **This is a legal question, which ultimately judges will decide.** We believe that a proper criterion depends both on the mechanism of communication (exec, pipes, rpc, function calls within a shared address space, etc.) and the semantics of the communication…"
> "By contrast, **pipes, sockets and command-line arguments are communication mechanisms normally used between two separate programs.** So when they are used for communication, the modules normally are separate programs. **But if the semantics of the communication are intimate enough, exchanging complex internal data structures, that too could be a basis to consider the two parts as combined into a larger program.**"

Y sobre agregados:

> "An 'aggregate' consists of a number of separate programs, distributed together… The GPL permits you to create and distribute an aggregate, even when the licenses of the other software are nonfree or GPL-incompatible. **The only condition is that you cannot release the aggregate under a license that prohibits users from exercising rights that each program's individual license would grant them.**"

Aplicado a nuestro caso:

- **Plugin local que lanza `ffmpeg.exe` con argumentos y lee stdout/archivos** → comunicación por *command-line arguments* + ficheros: el patrón que la FSF describe como «separate programs». Nuestro código no es derivado de FFmpeg y **no se distribuye FFmpeg**, así que no hay obligación GPL que cumplir. 🟢
- **Límite a respetar:** no compartir estructuras internas complejas con FFmpeg (no enlazar `libav*`, no usar bindings nativos, no pasar buffers en memoria compartida), porque eso es justo lo que la FSF marca como posible «single work». Por CLI y archivos estamos en zona segura. Y no podemos impedir por EULA que el usuario use/redistribuya **su** FFmpeg (eso choca con «cannot release the aggregate under a license that prohibits…», aplicable si algún día lo empaquetamos).
- **Consulta legal recomendada** solo si el volumen de negocio lo justifica: la propia FSF avisa de que la línea la deciden jueces.

### 2.3 Qué cambia si el plugin se vende (y si algún día se empaqueta FFmpeg)

Vender el plugin **no** activa GPL: sólo la **distribución de copias del binario GPL** la activa. Si se empaqueta `ffmpeg.exe` dentro del instalador:

| Obligación GPLv3 | Texto / fuente |
|---|---|
| Entregar el código fuente completo correspondiente | "if you distribute binaries, you must distribute the complete corresponding source code too" — GPL FAQ `#UnchangedJustBinary` |
| Ofrecer acceso equivalente y sin coste extra al fuente (descarga) | "If the binaries being distributed are licensed under the GPLv3, then you must offer equivalent access to the source code in the same way through the same place at no further charge" — `#DoesTheGPLAllowDownloadFee` |
| Cobrar sí se puede (no es «gratis» obligatorio) | "Yes, the GPL allows everyone to do this… there is no limit on what price you can charge" — `#DoesTheGPLAllowMoney` |
| No se puede relicenciar FFmpeg en términos propietarios, **ni pagando** | "FFmpeg is **not available under any other licensing terms, especially not proprietary/commercial ones, not even in exchange for payment**" — ffmpeg.org/legal.html |
| Mantener avisos, no renombrar binarios con nombres ofuscados, no reclamar autoría | checklist ítems 9-16 de ffmpeg.org/legal.html |
| Si el paquete lleva `ffmpeg.exe` junto a nuestro `.exe` propietario: sólo es lícito como **agregado** y sin cláusulas que restrinjan los derechos GPL del usuario (p. ej. prohibir ingeniería inversa del conjunto) | GPL FAQ `#MereAggregation` + `#DoesTheGPLAllowNDA` ("You are not allowed to distribute the work on any more restrictive basis") |

**Riesgo extra, independiente de GPL: patentes H.264/MPEG.** FFmpeg lo advierte en su mini-FAQ:

> "Are you using FFmpeg in a commercial software product? … **once you start trying to make money from patented technologies, the owners of the patents will come after their licensing fees. Notably, MPEG LA is vigilant and diligent about collecting for MPEG-related technologies.**"

Esto aplica **también** al escenario 🟢 (plugin de pago que produce MP4/H.264 con el FFmpeg del usuario): la GPL no es el problema, el pool de patentes AVC sí puede serlo según jurisdicción y volumen. Queda fuera de mi alcance resolverlo; se marca como decisión.

**Alternativa si algún día hay que empaquetar:** build **LGPL** (sin `--enable-gpl`) + `libopenh264` (BSD, con la licencia de patentes de Cisco) o encoder hardware; a cambio se pierde `libx264` y la calidad/velocidad del render por CPU en la GT 1030.

---

## 3. HyperFrames v0.9.23

- **Repo:** github.com/heygen-com/hyperframes · **Tag:** `v0.9.23`, publicado **2026-11-08T07:05:54Z** (GitHub Releases API).
- **Licencia del framework:** **Apache License 2.0**, texto íntegro en `LICENSE` del tag, cierre: «Copyright 2026 HeyGen, Inc.» — sin cláusulas adicionales ni campos de uso.
- **npm:** el paquete CLI `hyperframes@0.9.23` declara `"license": "Apache-2.0"`. Los paquetes con scope (`@hyperframes/core`, `/player`, `/producer`, `/studio`) **no declaran campo `license` en el registry** → el metadato npm es incompleto; lo que manda es el `LICENSE` del repo. Anotarlo para cualquier auditoría de SBOM.
- **README (mismo tag):** «**Open source:** Apache 2.0 license, with **no per-render fees or commercial-use thresholds**». Tabla comparativa del README: HyperFrames «License: Apache 2.0» vs Remotion «Source-available Remotion License».
- **Sin restricción para competidores:** Apache-2.0 no tiene campos de uso; lo único relevante es §6 (marcas: no usar «HyperFrames»/«HeyGen» para promocionar nuestro producto) y §4 (avisos y NOTICE al redistribuir).

### 3.1 GSAP: sí aparece, pero sólo en dos paquetes

Del `bun.lock` del tag (HyperFrames usa **bun**, no `package-lock.json`/`pnpm-lock.yaml`; ambos dan 404 en ese tag):

| Paquete del monorepo | Relación con GSAP |
|---|---|
| `packages/studio` (`@hyperframes/studio`) | **dependencia de runtime** `"gsap": "^3.13.0"` |
| `packages/sdk-playground` | dependencia de runtime `"gsap": "^3.15.0"` |
| `packages/player` | sólo **devDependency** `"gsap": "^3.12.5"` (no viaja en el paquete) |
| `packages/core`, `packages/engine`, `packages/producer` | **sin GSAP** |

Versión resuelta en el lockfile: **gsap@3.15.0** (`gsap: ["gsap@3.15.0", …]`).

⚠️ **Trampa grande encontrada:** `packages/aws-lambda` (`@hyperframes/aws-lambda`) depende de **`ffmpeg-static@^5.2.0`** y **`ffprobe-static@^3.1.0`**. `ffmpeg-static@5.3.0` se publica con `"license": "GPL-3.0-or-later"` y **contiene los binarios de FFmpeg**. Instalar el paquete de Lambda de HyperFrames = redistribuir un FFmpeg GPLv3. La ruta **local** (`core`/`producer`/`engine`) no arrastra FFmpeg: usa el del sistema. → Si adoptamos HyperFrames, **sólo** la ruta local; nunca `@hyperframes/aws-lambda` dentro de un entregable.

### 3.2 Licencia exacta de GSAP 3.15.0 (y por qué es amarillo)

El registry npm declara literalmente: `"license": "Standard 'no charge' license: https://gsap.com/standard-license."` — es decir, **no es OSI open source**; es gratis con condiciones de campo de uso. Texto (espejo Wayback del 2026-10-29 de gsap.com/community/standard-license):

> "**'Prohibited Uses'** means any implementation and/or use of GSAP Products **in tools that allow users to build visual animations without code** that encourages, induces, or materially assists in creating a solution that competes with **Webflow's visual animation building capabilities**."
> "**'Competitive Products'** means any software, tool, or service that **enables users to create, edit, or manage animations through a visual interface or builder similar to Webflow**."
> Restricciones: "1. Use any GSAP Products for any Prohibited Uses **without prior written consent**; 2. Reverse engineer…; 3. Remove or alter any proprietary notices".
> FAQ de la misma página: "**What if a WordPress plugin or theme or other niche tool allows users to create GSAP-driven effects through a visual interface? Is that prohibited?** … We want to encourage developers to build on top of GSAP, including visual tools that **don't directly compete** with Webflow's rich animation-building capabilities. If you are not sure… contact us."
> Y: "**Can I really use GSAP in commercial projects without paying anything?** Yes, really!"

Lectura para nuestro plugin: un editor de vídeo con timeline, títulos y captions **no** es por sí mismo un «animation builder» tipo Webflow; usar GSAP embebido para las animaciones de plantillas sería uso comercial permitido. Pero en cuanto la UI permita **construir animaciones sin código con un panel visual de keyframes/eases al estilo builder**, entramos de lleno en «Competitive Products» → ahí GSAP pasa a 🔴. Además HyperFrames documenta que «GSAP is the primary animation runtime for HyperFrames compositions», cargado por CDN en cada composición — es decisión de producto, no detalle técnico.

**Recomendación:** construir la UI del plugin **sin** `@hyperframes/studio` y **sin** GSAP en nuestro código (adapters CSS/WAAPI del propio HyperFrames bastan para el MVP); si una plantilla de usuario trae GSAP desde CDN, es contenido del usuario.

---

## 4. Remotion v4.0.541

- **Tag** `v4.0.541`, publicado **2026-11-05T08:22:08Z**. `LICENSE.md` en ese tag, primera línea relevante: «Remotion 5.0 license will slightly change — see PR #3750».
- npm `remotion@4.0.541` → `"license": "SEE LICENSE IN LICENSE.md"`.
- **No es open source.** La propia documentación de términos lo dice: «Remotion is **not open-source software according to the OSI definition**. Instead, it operates under a proprietary license called the Remotion License.»

### 4.1 ¿Un individuo es elegible para el tramo gratuito? **Sí**

LICENSE.md, «Eligibility»:

> "You are eligible to use Remotion for free if you are: **an individual**; a for-profit organization with up to 3 employees; a non-profit or not-for-profit organization; evaluating whether Remotion is a good fit…"

FAQ oficial: «Even if you are incorporated, you can operate under the Free License, as long as your total headcount is 3 or less.»

### 4.2 Qué permite

> "Permission is hereby granted… to use the software **non-commercially or commercially** for the purpose of creating videos and images and **to modify the software** to their own liking…"
> FAQ: "If you are [eligible for the Free License], **you don't need to buy a license — even if you set up an automation, launch a SaaS, or are using it commercially**."

→ Uso propio (Tormen, individuo): crear vídeos comerciales, automatizar renders, incluso montar un SaaS, **gratis**.

### 4.3 Qué prohíbe (aquí está el rojo para «vender el plugin»)

LICENSE.md, «Disallowed use cases»:

> "It is **not allowed to copy or modify Remotion code for the purpose of selling, renting, licensing, relicensing, or sublicensing your own derivate of Remotion**."

Términos (§ v5.0, mismo texto que rige la intención) y FAQ:

> "It is not allowed to **operate a rendering service that allows end-users to bring or upload their own Remotion code**… any such rendering service requires **prior explicit and written approval from Remotion**."
> FAQ: "Any commercial use case is allowed as long as you are **not selling Remotion as a product itself or allowing people to circumvent cases where they would have to buy a license themselves**."
> "Example of an **accepted** use case: Allowing users to create and render their own personalized video **based on your Remotion template**."
> "Example of an **unacceptable** use case: Allowing users to submit **any Remotion video, meaning a Remotion project, to your server for rendering**."

Y el encuadre que nos toca de lleno:

> "In practice, organizations building **video editors**, prompt-to-video tools, automated video pipelines **or using the Remotion Player** will fall under **Remotion for Automators**."

Traducción operativa:
- Plugin **para uso interno de Tormen** → tramo gratuito, permitido. 🟡 por ser licencia propietaria y por la telemetría (abajo), no por coste.
- Plugin **que se vende o se entrega a terceros** que renderizan con Remotion → **no** cabe en el tramo gratuito; o se paga Automators o se cae en la prohibición de «relicenciar tu derivado» / «servicio de render con código del usuario». 🔴
- **Telemetría:** «For client-side rendering, there is telemetry enabled by default **which cannot be disabled**»; en Remotion 5.0 será **obligatoria** para Automators. Relevante para un plugin «local y privado»: si algún día se usa Remotion Player en la UI, sale telemetría al exterior.

### 4.4 Precios publicados (si no fuera elegible)

| Opción | Precio | Fuente |
|---|---|---|
| Remotion for Creators | **$25 / asiento / mes**, sin mínimo | docs/license/faq líneas 54-61; remotion.pro/license |
| Remotion for Automators | **$0.01 por render**, mínimo **$100/mes** (facturado en bloques de 1.000 renders) | docs/license/faq líneas 63-64 |
| Enterprise | mínimo **$500/mes** | docs/license/faq línea 124; docs/terms (v5.0) |
| Free License | $0 | LICENSE.md / remotion.pro/license |

Coste realista de ejemplo para nosotros: automatizar 300 renders/mes → 300 × $0,01 = $3, pero el mínimo de $100/mes manda → **$1.200/año**. Un asiento Creators = **$300/año**.

⚠️ **Caveat de vigencia:** remotion.dev/docs/terms sirve hoy los términos **v5.0 «upcoming»** («will take effect upon the release of Remotion 5.0»), y los v4.0 están marcados como «Outdated document». El `LICENSE.md` de v4.0.541 es la referencia vinculante para la versión que usaríamos; precios y FAQ pueden cambiar con 5.0.

---

## 5. FilmCraft v0.18.0

- **Repo:** github.com/storytold/filmcraft · **Tag** `v0.18.0`, publicado **2026-11-06T20:21:40Z**.
- **Licencia confirmada en el tag:** `Cargo.toml` → `license = "MIT OR Apache-2.0"`, con `LICENSE-MIT` (1.101 B) y `LICENSE-APACHE` (10.174 B) presentes. README: «FilmCraft is dual-licensed under MIT or Apache-2.0, **at your option**. Copyright (c) 2026 ArtCraft Team and the FilmCraft contributors.»
- **Sin FFmpeg dentro** (esto es lo que la hace limpia): «**No FFmpeg inside.** The video codecs, AAC, Opus and the containers are **our own Rust code**, implemented from the public ITU-T, ISO and IETF specifications and tested frame by frame against ffmpeg **as an external oracle**.» y «contains no proprietary code… and **no GPL or LGPL code**; … ffmpeg is used only as an external test oracle.»
- **Binario oficial Windows sí existe** (assets del release v0.18.0): `filmcraft-0.18.0-windows-x64.msi` (90.464.256 B) y `-windows-x64-portable.zip` (109.616.261 B), además de arm64/x86 y `SHA256SUMS.txt` + firma `.asc`; el README dice «Installers and executables are **code-signed**». Hosting de descarga indicado: getartcraft.com/apps/filmcraft.
- **Uso como editor auxiliar de demos:** ✅ permitido sin condiciones (MIT o Apache-2.0, a elección). Si redistribuyéramos el `.msi`, obligaciones Apache-2.0 §4 (avisos + NOTICE) o MIT (aviso de copyright).
- **Única restricción real:** las marcas «ArtCraft»/«FilmCraft» y sus logos **no** están cubiertas por la licencia («are trademarks of the ArtCraft Team and are not covered by this license… Forks and modified versions must remove them»). No usar su marca para promocionar nuestro plugin, ni presentarlo como «FilmCraft-based».
- **Nota de hardware (no licencia):** el README indica que la app de escritorio inicia sólo Vulkan y DirectX 12, y que H.264/H.265 por hardware requieren NVIDIA (NVENC). La GT 1030 de esta máquina no tiene NVENC → decodificación por hardware vía Media Foundation, export por CPU. Verificar antes de usarlo como herramienta de demo; no afecta al gate legal.

---

## 6. Nota «heat fix»

**No hay ninguna fuente que asocie «heat fix» a HyperFrames.** Verificado el 2026-11-08:

- El cuerpo del release `v0.9.23` **no contiene la palabra «heat»** (0 coincidencias en el JSON de la API de Releases).
- Búsquedas web cruzadas (`hyperframes "heat fix"`, `"heat fix" HyperFrames`, `heygen hyperframes "heat" fix release notes`, `"heat fix" video editor plugin`): los resultados son térmica de portátiles, un addon de LAMMPS, un fix de rendimiento de DroidDeck/Steam Deck y productos «heat-fix» de bisutería. **Cero** relación con HyperFrames.

Conclusión: «heat fix» es una etiqueta sin respaldo documental en este contexto. Si venía de un chat o de una nota interna, **no se puede usar como hecho**; o se identifica la fuente original (¿qué release, qué issue, qué commit?) o se descarta.

---

## 7. Tabla maestra (para el registro de licencias del plugin)

| Componente | Versión | Licencia exacta | Uso permitido · plugin local | Obligaciones si se distribuye | Fuente (consultada 2026-11-08) |
|---|---|---|---|---|---|
| FFmpeg (build del sistema) | n9.0.1-11-ge47273f4d9-20260831 | **GPL-3.0-or-later** (por `--enable-gpl --enable-version3`) | Invocación por CLI/proceso externo, sin enlazar `libav*`: OK, sin obligaciones | Si se empaqueta el binario: fuente completa correspondiente, oferta de descarga equivalente, avisos, sin cláusulas más restrictivas; + riesgo patentes H.264 | `ffmpeg -L` (binario local, 2026-11-08); https://ffmpeg.org/legal.html ; https://www.gnu.org/licenses/gpl-faq.html#MereAggregation |
| FFmpeg vía `@hyperframes/aws-lambda` → `ffmpeg-static` | 5.3.0 | **GPL-3.0-or-later** (campo `license` del paquete npm) | **Prohibido** en nuestro stack: empaqueta binarios | Sería una redistribución de FFmpeg dentro de un paquete Node | https://registry.npmjs.org/ffmpeg-static/5.3.0 ; `bun.lock` del tag v0.9.23 |
| HyperFrames (framework) | v0.9.23 (2026-11-08) | **Apache-2.0** («Copyright 2026 HeyGen, Inc.») | Uso, modificación y uso comercial sin regalías | Aviso de licencia + NOTICE; §6 marcas (no usar «HyperFrames»/«HeyGen») | https://github.com/heygen-com/hyperframes/blob/v0.9.23/LICENSE ; README del tag |
| GSAP (dep. de `@hyperframes/studio`) | 3.15.0 (rango `^3.13.0`) | **Standard "no charge" GSAP License** (propietaria, gratis, con campos de uso) | Uso comercial de animaciones: OK | Prohibido en «herramientas que permiten construir animaciones visuales sin código» competidoras de Webflow; sin consentimiento escrito no hay excepción | https://registry.npmjs.org/gsap/3.15.0 ; espejo Wayback 2026-10-29 de https://gsap.com/community/standard-license/ |
| Remotion | v4.0.541 (2026-11-05) | **Remotion License** (propietaria, source-available; no OSI) | Individuo: vídeos comerciales + automatización + SaaS propios, gratis | Prohibido vender/relicenciar/sublicenciar el derivado o dejar que terceros suban su proyecto Remotion; Player en producto de terceros = Automators ($0,01/render, mín. $100/mes) | https://github.com/remotion-dev/remotion/blob/v4.0.541/LICENSE.md ; https://www.remotion.dev/docs/license/faq ; https://www.remotion.pro/license |
| FilmCraft | v0.18.0 (2026-11-06) | **MIT OR Apache-2.0** (a elección) | Uso libre como editor auxiliar de demos | Aviso de copyright (MIT) o avisos+NOTICE (Apache-2.0) si se redistribuye el binario; marcas excluidas | https://github.com/storytold/filmcraft/blob/v0.18.0/Cargo.toml ; LICENSE-MIT / LICENSE-APACHE ; GitHub Releases v0.18.0 |

---

## 8. Qué no se pudo verificar (declarado, no escondido)

1. **gsap.com no se pudo leer en directo** — la web sirve un challenge anti-bot («One moment, please…»). El texto de la licencia se obtuvo del **espejo Wayback del 2026-10-29** (`web.archive.org/…/gsap.com/community/standard-license/`). Es texto de GSAP/Webflow, pero no confirmé que la versión vigente hoy en `gsap.com/standard-license` sea idéntica. **Acción barata:** abrir esa URL en navegador real una vez y comparar.
2. **Procedencia del `ffmpeg.exe` instalado:** el build es mingw64 estático con `--extra-version=20260831` y gcc 15.2.0 (patrón de builds tipo BtbN/gyan.dev), pero el binario **no declara su autor**. Si algún día se redistribuye *este* binario, además de nuestras obligaciones habría que reproducir **su** configuración exacta de build y su fuente. Para un plugin que no lo empaqueta, irrelevante.
3. **API de GitHub limitó el rate** al final de la sesión (403); los datos de repos/tags se obtuvieron antes y los archivos, por `raw.githubusercontent.com`, que no está limitado.
4. **Remotion:** no hay carta ni confirmación escrita de Remotion AG sobre nuestro caso concreto (plugin local que genera MP4 vía Remotion). La lectura se apoya en LICENSE.md + FAQ + precios publicados. La elegibilidad «individuo» es clara; la frontera «producto para terceros» la define su FAQ, no un contrato firmado.
5. **Remotion 5.0** cambia licencia y hace obligatoria la telemetría para Automators; lo citado es válido para v4.0.541, no para 5.x.
6. **Patentes H.264/AVC:** nadie en este proyecto ha evaluado el pool (Via LA/MPEG LA y otros) para venta comercial de un encoder. FFmpeg avisa explícitamente; **no** hay conclusión aquí.
7. **Ninguna conclusión de este documento es asesoría legal.** Los puntos que un abogado debería revisar antes de vender: (a) empaquetar FFmpeg GPLv3, (b) patentes H.264, (c) frontera «producto para terceros» de Remotion.

---

## 9. Decisiones necesarias (para Tormen / Padre)

1. **¿Se vende el plugin o es herramienta interna?** Es la decisión que más cambia el mapa: interna → Remotion 🟡 y FFmpeg 🟢 sin más; **se vende** → Remotion 🔴 (no usar en el producto vendido) y FFmpeg 🟢 sólo si el usuario aporta su binario.
2. **Confirmar la arquitectura «FFmpeg del sistema, invocado por CLI»** como invariante del plugin (y escribirla en el plan): prohíbe enlazar `libav*`, prohíbe empaquetar `ffmpeg.exe`, prohíbe `ffmpeg-static`/`@hyperframes/aws-lambda`. Es lo que sostiene el 🟢.
3. **Autorizar o descartar HyperFrames** como base del render HTML→vídeo. Si se autoriza: sólo la ruta local (`core` + `producer`), sin `@hyperframes/studio` ni GSAP en nuestra UI.
4. **Política GSAP:** ¿aceptamos GSAP como runtime de las plantillas del usuario (permitido, con el límite de «no builder visual»), o lo excluimos del MVP? Recomiendo excluirlo hasta que exista UI de animación.
5. **FilmCraft:** ¿se adopta como editor auxiliar para grabar demos? Legalmente 🟢; hay que resolver antes el tema GPU/Vulkan en la GT 1030 con una prueba de 10 minutos.
6. **Presupuesto de patentes H.264:** decidir si se consulta a un abogado cuando exista precio de venta (no bloquea el MVP).

---

## 10. Fuentes (todas consultadas 2026-11-08)

| Fuente | Qué se citó |
|---|---|
| `ffmpeg -version` / `ffmpeg -L` (binario local, 2026-11-08) | versión n9.0.1, flags `--enable-gpl --enable-version3`, texto «GNU General Public License… version 3… or any later version» |
| https://ffmpeg.org/legal.html | licencia FFmpeg = LGPL2.1+ salvo partes GPL; checklist «when linking against the FFmpeg libraries»; «not available under any other licensing terms… not even in exchange for payment»; mini-FAQ de patentes |
| https://www.gnu.org/licenses/gpl-faq.html#MereAggregation | «aggregate» vs «modified version»; pipes/sockets/command-line = separate programs; caveat de comunicación íntima |
| https://www.gnu.org/licenses/gpl-faq.html#DoesTheGPLAllowMoney | se permite vender copias |
| https://www.gnu.org/licenses/gpl-faq.html#DoesTheGPLAllowDownloadFee | GPLv3: acceso equivalente al fuente sin coste extra |
| https://www.gnu.org/licenses/gpl-faq.html#UnchangedJustBinary | binario ⇒ fuente completa correspondiente |
| https://github.com/heygen-com/hyperframes/releases/tag/v0.9.23 (+ API Releases) | tag publicado 2026-11-08T07:05:54Z; assets |
| https://github.com/heygen-com/hyperframes/blob/v0.9.23/LICENSE | Apache-2.0, «Copyright 2026 HeyGen, Inc.» |
| https://raw.githubusercontent.com/heygen-com/hyperframes/v0.9.23/bun.lock | gsap@3.15.0; `packages/studio` dep `^3.13.0`; `packages/aws-lambda` → `ffmpeg-static ^5.2.0` |
| https://registry.npmjs.org/gsap/3.15.0 | campo `license`: «Standard 'no charge' license» |
| Wayback 2026-10-29: https://gsap.com/community/standard-license/ | «Prohibited Uses», «Competitive Products», FAQ de plugins visuales (gsap.com directo bloqueado) |
| https://registry.npmjs.org/ffmpeg-static/5.3.0 | `"license": "GPL-3.0-or-later"` |
| https://github.com/remotion-dev/remotion/blob/v4.0.541/LICENSE.md | elegibilidad Free License; «Disallowed use cases»; cambio en 5.0 |
| https://www.remotion.dev/docs/license/faq | individuo/≤3 empleados; «video editors… fall under Remotion for Automators»; «not selling Remotion as a product itself»; casos aceptado/no aceptable; precios |
| https://www.remotion.pro/license | Free vs Company License, requisito de licencia para 4+ personas |
| https://www.remotion.dev/docs/terms (v5.0, «upcoming») y https://www.remotion.pro/terms-4-0 («Outdated») | Automators $0,01/render, mín. $100; Enterprise $500; «Remotion is not open-source software according to the OSI definition»; restricción de rendering service |
| https://registry.npmjs.org/remotion/4.0.541 | «SEE LICENSE IN LICENSE.md» |
| https://github.com/storytold/filmcraft/blob/v0.18.0/Cargo.toml + LICENSE-MIT + LICENSE-APACHE | `MIT OR Apache-2.0` |
| https://github.com/storytold/filmcraft/releases/tag/v0.18.0 | publicado 2026-11-06T20:21:40Z; `windows-x64.msi`, `windows-x64-portable.zip`, SHA256SUMS + `.asc` |
| README de FilmCraft v0.18.0 | «No FFmpeg inside»; codecs propios; marcas ArtCraft; requisitos Vulkan/DX12 |
