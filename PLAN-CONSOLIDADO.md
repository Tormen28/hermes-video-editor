# Plugin editor dentro de Hermes Web — plan por fases

Page: https://cursor.com/canvas/store-4e145a23-5a08-40c7-9d67-0ce34d8599f6/85c24690-4fa9-487e-8beb-aac70f1ed91e

Revisión de diseño: 8 nov 2026, America/Caracas (UTC-4). Corrección de Gustavo incorporada: una sola experiencia dentro de Hermes Web con contexto de proyecto seleccionado. El resto del diseño está aprobado; no es orden de construir/desplegar.

## Decisión y estado

Entregar un plugin editor básico dentro de la propia superficie de Hermes Web, no una app que Hermes sólo abre. Comparte contexto de proyecto seleccionado explícitamente y devuelve el resultado al chat/proyecto. Reutilizar componentes verificados o construir controles mínimos; un único motor y worker backend aislado para cuidar recursos. Demos como apoyo, nunca sustituto del plugin.

Versión del 8 de noviembre de 2026, America/Caracas (UTC-4). Se completaron investigación y revisión de factibilidad; no se inició implementación, instalación, render, captura ni publicación. Éste es el plan base completo de ejecución por etapas, adaptado al requisito definitivo de plugin editor dentro de Hermes Web. Gustavo aprobó el resto del diseño; esta aprobación de diseño no ordena construir, instalar ni desplegar.

- [x] Investigación de fuentes oficiales y propuesta preliminar completadas
- [x] Revisión de Antigravity completada con Opus 5.5 — El coordinador confirmó claude-opus-5-5-medium; finalizó 8 nov, 12:54:44 Caracas.
- [x] Plan consolidado con las objeciones de viabilidad incorporadas
- [ ] Hardware, rendimiento y formatos reales de la PC medidos para vídeo
- [ ] Hermes integrado y lifecycle Panteón verificados de extremo a extremo
- [ ] API/extensión UI de Hermes verificada y componentes/motor elegidos; ejecución de etapa autorizada
- [ ] Vídeos capturados/renderizados o aplicación implementada

La revisión de Antigravity fue documental, sin webs ni tests independientes. Recomendaba aplazar producto mientras el objetivo era ambiguo. Gustavo confirmó después que el editor esencial debe estar dentro de Hermes Web, junto a su experiencia de navegador y con contexto compartido: esa instrucción prevalece sobre aplazar producto o abrir una app aparte. Conservamos riesgos y pruebas de la revisión, no su aplazamiento como decisión del usuario. Para ahorrar uso, Grok Bot queda en planificación/revisión y Antigravity en ejecución y tests futuros, únicamente con autorización para la etapa y acceso correspondiente.

**Hermes: estado reportado por Gustavo:** Tormen desplegado: 178 skills registradas, 174 available y 4 unsupported. No hubo recarga runtime. BSK y JEV: suites aisladas aprobadas, integración pendiente. Panteón: ficha registrada, lifecycle completo no probado.

**Lo que este plan no vuelve a diagnosticar:** No se inspeccionó otra vez la instalación. Los números anteriores son del informe aportado, no certificación actual del proceso activo.

**Supuesto abierto:** «Heat fix» podría ser HyperFrames; la equivalencia no está confirmada. Si era otra herramienta, ampliar la comparación antes de elegir.

## Visión y alcance

Un futuro plugin editor integrado en Hermes Web: entrar desde la propia interfaz, continuar en el proyecto activo, seleccionar assets y guion autorizados, editar visualmente, previsualizar, exportar y devolver el artefacto al chat/proyecto. Hermes y editor son una sola experiencia de usuario, no un enlace a otra aplicación. El render puede ejecutarse en backend separado. No se afirma que hoy existan hooks, paneles o APIs upstream que permitan hacerlo.

1. Entrega principal: plugin editor básico dentro de Hermes Web, usable sin programar, con contexto compartido explícito, controles visibles y un único motor.
2. Reutilizar antes de construir: comprobar componentes/UI de HyperFrames Studio integrables legal y técnicamente en Hermes Web; si no, controles mínimos dentro de Hermes con Player/renderer adecuados. FilmCraft sólo como base si su superficie web realmente puede integrarse con el contrato de proyecto; desktop, WASM anunciado o abrir otra app no bastan.
3. Demo paralela: validar guion y resultado con herramientas existentes; no satisface por sí sola el editor.
4. Integración visual desde el MVP dentro de Hermes Web; después endurecer la orquestación JEV/Panteón tras gate R. La propuesta de valor es Hermes Web con navegador y editor en el mismo proyecto; no afirmar que ese plugin ya existe ni añadir SaaS o publicación automática.

## Plugin editor básico dentro de Hermes Web · MVP

### Proyecto e importación
Entrar al editor desde Hermes Web y mantener el proyecto seleccionado. Elegir explícitamente assets/guion autorizados, objetivo, formato e idioma; importar PNG/JPEG, vídeo y audio compatibles. Originales protegidos, VFR/CFR cuando haga falta. No pasar secretos ni el proyecto entero indiscriminadamente.

### Edición guiada
Lista/timeline visual, reordenar por arrastre y botones, trim inicio/fin y split básico si el ensayo lo fija como esencial; editar texto/subtítulos, volumen y horizontal/vertical con crop/fit. Transiciones limitadas. No exigir HTML, React, JSON o comandos al usuario.

### Preview y persistencia
Play/pause y scrub en baja resolución, undo básico, autosave y guardar/reabrir conservando edición. Relink explícito de medios faltantes.

### Exportación y operación
Un job local, progreso real, cancelación, pausa en punto seguro y recuperación. MP4 720p/30 inicial sujeto a medición; 1080p no garantizado.

Fuera del MVP: streaming, publicación/cron automáticos, actuación en cuentas reales, clonación de voz, colaboración multiusuario, nube/billing, 4K/60, editor tipo Premiere completo y modelo editable universal entre tres motores. Intercambiar un MP4 no conserva toda la edición de escenas, efectos o captions.

## Tres bases y alternativa rápida

| Base | Aporte real | Condición decisiva |
| --- | --- | --- |
| HyperFrames | HTML/CSS y animación seekable → vídeo; CLI, preview, Studio y skills. | Primer candidato: componentes/UI realmente reutilizables e integrables dentro de Hermes Web, con proyecto compartido; trim/texto/save/export, local/hosted/Pro y licencia. Abrir Studio externo o instalar skill no cumple. |
| Remotion | React/TypeScript, Studio, Player embebible y renderer; no NLE terminado por sí solo. | Alternativa: controles mínimos como plugin UI dentro de Hermes Web, Player para preview y renderer backend para export. Timeline/trim/undo/proyecto se construyen aparte; licencia, RAM y API Hermes por verificar. |
| FilmCraft | NLE visual Rust, timeline, recortes, títulos/audio, CLI y MCP documentados. | GUI nativa/MCP no cumplen UI dentro de Hermes. WASM no demuestra integración web: exigir componentes/superficie y licencia verificadas. Puede apoyar demos, no sustituir plugin. |
| Editor existente · ruta D | Montaje auxiliar de demos mientras se prepara el editor web. | Usar lo instalado y apto con permiso. No sustituye la entrega del MVP web. |

## Dependencias, mantenimiento y límites

**HyperFrames:** Node >=22, FFmpeg y Chrome headless/Puppeteer. Framework Apache-2.0; Studio Pro/modelos/servicios tienen condiciones aparte. Release observada: v0.9.23, 8 nov, 03:05 Caracas.

**Remotion:** Node/Bun compatible, React y Chrome Headless Shell; desde 4 incluye FFmpeg para su pipeline. Paquetes y browser deben fijarse por versión. Release observada: v4.0.541, 5 nov, 04:22 Caracas.

**FilmCraft:** Motor/GUI nativo Rust/egui/wgpu y codecs propios según upstream; no requiere Node/Chrome ni FFmpeg dentro del motor según README. Compilar main declara Rust 1.95/edition 2024; verificar tag/binarios. Release observada: v0.18.0, 6 nov, 16:21 Caracas.

Los repositorios tenían actividad reciente y no estaban archivados al consultarlos. FilmCraft se declara joven; codecs propios, benchmarks y amplitud funcional son claims del autor, no pruebas nuestras. Las releases/documentación favorecen la evaluación, pero no certifican estabilidad. No se usan estrellas ni contadores resumidos inconsistentes como criterio.

HyperFrames y Remotion se solapan como composición/render web. FilmCraft puede servir de editor externo para acabado de un MP4 generado, sin promesa de round-trip editable. La skill de migración Remotion→HyperFrames no garantiza equivalencia universal. No se incorporan dos motores salvo nuevo ADR con necesidad y coste demostrados. Ningún editor externo de apoyo satisface por sí solo la entrega del plugin dentro de Hermes Web.

## Licencias y costes

**HyperFrames · código:** Apache License 2.0: uso comercial/redistribución sujetos a licencias, avisos y cambios; no concede marcas. No hay tarifa por render del framework según README; eso no cubre servicios hosted, Pro, modelos, medios o dependencias.

**GSAP · gate pendiente:** La revisión alertó de posibles restricciones para herramientas visuales competidoras. No se verificó aquí ese supuesto legal en la versión exacta utilizada: revisar lockfile, licencia y uso pretendido. No afirmar prohibición ni autorización por extensión de Apache del repo.

**FilmCraft · código y activos:** MIT OR Apache-2.0 a elección según README/Cargo y archivos de licencia. Fuentes/activos tienen términos propios, incluida OFL-1.1; ArtCraft y logos conservan condiciones de marca. Claims de ausencia GPL/LGPL y codecs propios requieren auditoría; no eliminan patentes.

**Remotion · uso personal:** Source-available bajo Remotion License, no MIT/Apache. LICENSE consultado permite vídeos comerciales a individuos y entidades elegibles pequeñas; FAQ y términos actuales deben cotejarse con versión, entidad y número de personas. No atribuir coste obligatorio a Gustavo sin comprobar elegibilidad.

**Remotion · automatización comercial:** Quienes no son elegibles al tramo gratuito pueden necesitar Company License. Precios publicados consultados: Creators USD 25/mes por seat; Automators USD 0,01 por render exitoso, mínimo USD 100/mes. No incluye infraestructura; no es presupuesto aprobado para Gustavo.

**Remotion · distribuir el editor:** Distinguir SaaS permitido en ciertos términos de vender/relicenciar un derivado de Remotion, restringido en LICENSE. Antes de distribuir app/fork/editor embebido: aclaración escrita y licencia aplicable; no presumir que permiso para hacer MP4 cubre redistribuir software.

**Starter y telemetría:** Editor Starter es producto/licencia separados, no gratis por defecto. main anuncia cambios de Remotion 5; docs de licensing distinguen reporting/telemetría según versión y modalidad, con excepción indicada de web-renderer. Validar paquete fijado y compatibilidad offline; no evadir reporting requerido.

Crear un vídeo, ofrecer automatización y distribuir una aplicación son tres operaciones distintas. Además se revisan build de FFmpeg y sus obligaciones según configuración, fuentes, música, imágenes, voces, plantillas, iconos y codecs. No es asesoría legal ni auditoría completa. Presupuesto externo inicial propuesto: cero; permanecen tiempo, disco y energía. Cloud, modelos pagados, suscripciones o Starter necesitan aprobación e importe específicos.

## Arquitectura y contexto compartido

1. Ingesta: sondear fps/timebase/codecs y audio; VFR puede afectar seek/sincronía. Crear CFR cuando pruebas lo requieran; preservar original, offset y mapeo para captions. Proxy no es garantía automática de sincronización.
2. Cola backend fuera del proceso gateway, no otra app UI: draft → validated → queued → running → completed/failed/cancelled; paused sólo en límites seguros. Snapshot inmutable, idempotencia, journal/DB propio y progreso por trabajo. Caer el gateway no debe borrar el estado.
3. Worker: carpeta por job, allowlist de argumentos, entorno sin secretos y mínimos privilegios. Job Objects permiten límites/kill-tree, no aislamiento de seguridad. Identidad restringida/ACL y sandbox compatible deben probarse; Chrome flags no son una barrera de red ni filesystem.
4. Preview y recuperación: límite de recursos, cerrar workers propios al terminar, checkpoints sólo de chunks completos. Pausa puede ser diferida o no soportada; no prometer suspender encoder instantáneamente. Staging y validación antes de salida atómica; MP4 parcial nunca es éxito.
5. Integración UI dentro de Hermes Web obligatoria: comprobar extensión real en fase 0, permisos, contexto y retorno. Si falta, documentar bloqueo y proponer extensión compatible/versionada para aprobación. Un backend local aislado puede proteger recursos; no implica abrir otra app UI. Usar APIs soportadas, sesión/origen/CSRF y skill sin duplicación. MCP opcional no sustituye la interfaz.
6. Local-first: assets/fuentes cacheados, egress bloqueado por mecanismo validado y telemetría/licencias compatibles. Si no se prueba aislamiento, sólo plantillas confiables o función detenida. Red, TTS/transcripción y almacenamiento externo requieren consentimiento y coste declarado.

Contrato de contexto compartido: selección explícita por el usuario de assets, guion y referencias permitidas dentro del proyecto; identificador/revisión y permisos acompañan cada operación. Ediciones deterministas versionadas con historial, detección de conflictos y snapshot autorizado al render; preview y export parten del mismo documento. No copiar todo el proyecto, chats, credenciales o secretos al worker. El resultado vuelve al chat/proyecto correcto con su revisión y sin envío externo.

Si realmente hay 8 GB: comenzar con concurrencia 1, preview 360p–540p y proxies; fijar límites sólo tras medir margen del SO y Hermes. Evitar sumar Whisper/TTS local durante render sin presupuesto. No asumir que WSL2/Windows Sandbox caben ni que una GPU vuelve gratis el render. ETA estimada y métricas del árbol completo, no porcentaje inventado.

## Fases y dependencias

| Pista | Depende de | Decisión |
| --- | --- | --- |
| 0R · Reparación | Permiso y diagnóstico real | Separada; bloquea integración, no todas las demos. |
| 0 · Requisitos | Lectura y decisiones de alcance | Comprueba API/extensión Hermes Web, contexto autorizado y editor esencial. |
| D · Demo | Función verificada + medios consentidos | Paralela a reparación; no exige editor propio. |
| 1 · Spike | Gate 0 + permiso de experimento | Elegir UI web/motor; si falla, bloqueo y alternativa, no eliminar editor. |
| 2 · Editor web MVP | Gate 1 + autorización de ejecución | UI integrada Hermes Web; reutilizar o controles mínimos, no otra app. |
| 3 · Integración | Gate R + MVP estable | Misma UI/contexto; Hermes orquesta y worker backend aislado. |
| 4 · Calidad | Plugin integrado y orquestación probados | Tests, recursos y licencias demostrados. |
| 5 · Entrega | Gate D o Gate 4 según artefacto | Distribución/publicación con permiso aparte. |

El editor web se mantiene obligatorio; un motor fallido obliga a evaluar alternativa o reportar bloqueo, no reducir la entrega a vídeos. Las bandas siguientes son esfuerzo orientativo de una persona técnica, no fechas ni trabajos iniciados. No sumarlas como contrato: hay ramas alternativas y esperas. La reparación de Hermes es la incertidumbre principal del calendario de integración. No se verificó aquí ningún deadline de concurso Nous y no se promete terminar producto para él.

### 0R · Cerrar la reparación de Hermes

**Responsables:** Antigravity: diagnóstico, implementación y pruebas en PC sólo cuando Gustavo lo autorice. Grok Bot: revisión del informe; Gustavo: coordinación del reinicio y permisos.

**Entrada:** Informe anterior, respaldos y autorización específica para inspeccionar o cambiar la instalación. Esta fase es una pista separada, no una instalación del editor.

#### 0R.1 · Reconciliar disco y runtime
Leer RESULTADO-ANTIGRAVITY.md, manifiestos, hashes y versiones reales. Distinguir lo probado en canary de lo cargado en el gateway activo. No volver a aplicar las 131 correcciones de metadatos ni sobrescribir plugin.yaml.

#### 0R.2 · Resolver el seam BSK/JEV
Comprobar inventario PluginManager, nombres canónicos, propietario y ruta hasta la lectura final; colisión local/plugin, plataformas, skills deshabilitadas y exclusiones por perfil/canal. Verificar el interruptor efectivo y sus overrides por una interfaz soportada, no sólo jev.skills: true.

#### 0R.3 · Preparar cambios mínimos recuperables
Sólo ante defecto demostrado: plan de archivos, copia selectiva, manifiesto before/after y rollback por hash; preservar CRLF y cambios locales. Detenerse ante diferencias concurrentes. No tocar perfiles, modelos, claves, routing, cron o bases de datos a ciegas.

#### 0R.4 · Cargar mediante mecanismo soportado
Inventariar tareas activas y coordinar recarga/reinicio mínimo sin matar trabajos. Demostrar que el proceso real carga el cambio; una importación en host simulado no basta.

#### 0R.5 · Probar el ciclo completo
En tablero y sesiones temporales: skill namespaced → selección JEV → apertura de esa identidad → despacho al perfil correcto → kanban → espera/gates → finalización → retorno al Padre. Sin notificaciones externas ni tareas reales.

#### 0R.6 · Cerrar el informe de reparación
Separar suites aisladas, instalación, carga runtime y extremo a extremo; adjuntar comandos, salidas, omisiones y hashes. Reestimar reparación sólo después de diagnosticar; no convertir el estado anterior en un nuevo diagnóstico.

**Salida / gate:** Gate R: ciclo real reproducible, identidad preservada, exclusiones respetadas y rollback ensayado en copia. Si falla, la integración de vídeo permanece detenida; una demo de otra función verificada puede continuar.

**Evidencia:** Matriz de capacidades, logs redactados del proceso real, pruebas de colisión y lifecycle, manifiestos y tareas/servicios afectados.

**Rollback:** Restaurar únicamente archivos cuyos hashes coincidan con lo desplegado y usar recarga soportada; conservar datos y trabajo concurrente. Si no hay permiso de reinicio, documentar pendiente, no forzarlo.

**Esfuerzo orientativo:** Diagnóstico orientativo: 0,5–1 día técnico. Reparación: sin cota fiable hasta diagnóstico. Confianza baja en calendario total.

### 0 · Aterrizar objetivo, entorno y derechos

**Responsables:** Grok Bot consolida requisitos y decisiones; Antigravity hace inventario read-only de PC cuando esté autorizado; Gustavo define objetivo y medios consentidos.

**Entrada:** Este plan y la revisión de viabilidad terminada. No necesita reparación completa para revisar requisitos.

#### 0.1 · Registrar editor obligatorio y supuestos
Registrar lo aprobado: editor esencial dentro de Hermes Web como plugin, en continuidad con navegador y contexto de proyecto, no profesional. Mantener HyperFrames como interpretación condicional de «heat fix». Describir la propuesta futura de producto sin afirmar que ya existe ni asumir permiso para distribuir/vender o desplegar.

#### 0.2 · Inventariar sin instalar
Registrar SO/build, CPU/arquitectura, RAM libre/instalada, GPU/driver, disco y versiones de Hermes, Node, FFmpeg y browsers; 8 GB no está confirmado. Comprobación obligatoria read-only de API/extensiones reales de Hermes Web: UI integrada, navegación, identidad/contexto de proyecto, permisos y retorno de resultados. No inventar hooks/paneles. Si no existe extensión suficiente, documentar bloqueo y propuesta UI compatible/versionada para aprobación, sin ofrecer app separada como solución.

#### 0.3 · Definir material y privacidad
Identificar plugins que funcionan en runtime y archivos autorizados. Para grabaciones nuevas, concretar ventana, perfil de prueba, duración y datos sintéticos. Excluir chats, secretos, notificaciones y datos de terceros; ninguna captura se inicia con este plan.

#### 0.4 · Inspeccionar formatos
Sondear códecs, audio, duración, timebase y fps de muestras autorizadas; detectar VFR. Definir cuándo crear proxy CFR y cómo conservar originales, offsets y mapeo temporal. No transcodificar todo indiscriminadamente.

#### 0.5 · Fijar presupuesto y baseline
Proponer un job concurrente, coste externo cero y hasta 10 GB temporales sólo si hay espacio y aprobación. Diseñar medición comparable del gateway antes/durante/después, con misma carga y muestras suficientes para p95.

#### 0.6 · Cerrar contrato del MVP
Fijar escenarios dentro de Hermes Web sin programación: entrada y continuidad de proyecto, selección explícita de assets/guion, importar captura/clip/audio, play/pause/scrub, arrastrar/reordenar, trim inicio/fin, texto/captions, volumen, horizontal/vertical, undo/autosave, guardar/reabrir, export y retorno al chat/proyecto. Probar si split básico es esencial y fijarlo antes de implementar. Definir derechos de activos y requisitos offline. Validar licencias del tag elegido antes de implementación de producto.

**Salida / gate:** Gate 0: contrato de plugin Hermes Web, entorno, medios, contexto autorizado y permisos definidos; extensión UI real verificada. Si falta soporte, bloqueo explícito y propuesta compatible/versionada pendiente de aprobación antes de implementar UI. No reemplazar el requisito por app aparte.

**Evidencia:** Ficha de entorno, lista de medios/códecs, consentimiento de captura si corresponde, checklist ponderada y baseline diseñado/medido según acceso.

**Rollback:** Sólo lectura y documentación; no requiere revertir configuración. Mantener archivos privados fuera de documentos compartibles.

**Esfuerzo orientativo:** 0,5–1 día técnico orientativo; esperas por decisiones y accesos no incluidas. Confianza media.

### D · Preparar demos sin esperar un editor propio

**Responsables:** Grok Bot: guion y revisión de honestidad. Antigravity: edición/pruebas locales cuando esté autorizado. Gustavo: consentimiento de captura y aprobación de preview/publicación.

**Entrada:** Una capacidad ya comprobada y medios autorizados. No depende de 0R si no muestra la cadena pendiente; sí depende de verificar la función concreta que aparecerá.

#### D.1 · Elegir una evidencia concreta
Una demo de ARGOS, BotChat o skills existentes sólo si esa acción funciona de verdad. Tormen puede ser candidato, pero el informe de 178 registros no sustituye comprobar el proceso real. No presentar JEV/Panteón como terminados antes del gate R.

#### D.2 · Escribir guion y storyboard
45–90 segundos: problema → acción real → resultado → límites. Para cada escena: mensaje, captura fuente, duración, título y evidencia. Opcional versión de 20–30 segundos, no requisito inicial.

#### D.3 · Reutilizar herramientas disponibles
Preferir grabador/editor ya instalado y apto; o HyperFrames si ya está operativo y compatible. OBS/Shotcut/Kdenlive/Resolve son ejemplos de alternativas, no un inventario de la PC ni una recomendación de instalar todas. Evaluar permisos, licencia y recursos si hiciera falta otra.

#### D.4 · Importar o capturar con consentimiento
Usar perfil temporal y datos sintéticos claramente rotulados. Recortar o redactar en origen. No fabricar una interfaz para simular una función. Si hay ilustración conceptual, etiquetarla como concepto.

#### D.5 · Editar y revisar
Zooms legibles, títulos, transiciones discretas y subtítulos españoles revisados por humano. Comprobar acentos y fuentes locales. Voz, música y transcripción sólo con derechos y consentimiento; manual por defecto si IA local excede recursos.

#### D.6 · Entregar preview y archivo
Mostrar preview para aprobación; exportar el MP4 sólo cuando se autorice. Validar audio, sincronía, duración y lectura. Conservar proyecto y fuentes autorizadas. Publicar o enviar fuera requiere autorización separada con destino concreto.

**Salida / gate:** Gate D: demo honesta y legible, preview aprobado, medios con derechos, sin secretos. No implica que el editor propio exista ni que Hermes esté íntegramente reparado.

**Evidencia:** Guion con fuentes por escena, comprobación runtime de la función mostrada, checklist de privacidad, reporte de vídeo y aprobación del preview.

**Rollback:** Volver a la versión del proyecto anterior; no sobrescribir originales ni publicar un borrador. Limpiar sólo derivados propios tras revisar qué se conserva.

**Esfuerzo orientativo:** 0,5–1,5 días técnicos si ya existe función y herramienta operativa; no fecha prometida ni compromiso de concurso.

### 1 · Spike: elegir una base con datos

**Responsables:** Antigravity realiza el experimento en entorno aislado cuando se autorice; Grok Bot revisa la decisión; Gustavo aprueba la elección y siguiente fase.

**Entrada:** Gate 0 y permiso de instalaciones/pruebas acotadas. El editor web ya está confirmado: esta fase decide cómo cumplirlo, no si se elimina.

#### 1.1 · Seleccionar candidato principal
Primero verificar componentes/UI de HyperFrames Studio integrables en Hermes Web y sus controles/proyecto. Si no encajan, evaluar controles mínimos dentro de Hermes + Remotion Player/renderer con licencia/RAM aptas. FilmCraft sólo con integración web real demostrada; desktop/MCP/WASM no bastan. Segundo candidato por carencia concreta, nunca tres integraciones.

#### 1.2 · Fijar release y revisar licencias
Revisar tag, lockfile, binarios Windows, compatibilidad de skill y dependencias. Auditar GSAP/bloques/activos si aplica; para distribución Remotion aclarar términos por escrito antes de código de producto. Preferir binario oficial FilmCraft verificado frente a compilar si cubre el caso.

#### 1.3 · Ejecutar fixture de 10–15 segundos
Tres escenas con PNG, clip VFR autorizado, audio, título con acentos y caption. Probar original y proxy CFR cuando lo requiera. Verificar seek, frames en cortes, offsets, audio y export en dos reproductores. La composición y preview deben concordar.

#### 1.4 · Medir recursos y control
Con Hermes activo y carga comparable: RSS de todo el árbol, CPU, disco, paginación, tiempo de export, p50/p95 del gateway. Cancelar y relanzar; reiniciar supervisor de prueba; confirmar que no quedan huérfanos ni dobles outputs.

#### 1.5 · Medir UX y offline
Probar tareas esenciales y encaje en la superficie de Hermes Web con UI/componentes verificables: contexto seleccionado, contrato de proyecto, edición versionada y retorno. Separar motor/CLI de UI; revisar local/hosted y reutilización. Una app externa o FilmCraft desktop no aprueban integración. Render de prueba con egress realmente bloqueado y activos cacheados; documentar telemetría y descargas. No evadir obligaciones de licencia.

#### 1.6 · Emitir ADR-002 y decidir
Tabla de resultados, vídeos/frames de evidencia, costes, licencias y bloqueos. Si componentes/UI integrables en Hermes cubren tareas críticas y cerca del 80% ponderado, reutilizar; 80% es heurística, no resultado. Si no, controles propios mínimos dentro de Hermes, un motor y mismo documento versionado para preview/export. Sin API UI viable: bloqueo y propuesta de extensión para aprobar; no app separada ni demos como sustituto.

**Salida / gate:** Gate 1: solución plugin UI dentro de Hermes Web + motor supera sincronía, recursos, licencia y contrato de contexto/proyecto; ADR aceptado. Falta de soporte UI es bloqueo técnico y propuesta de extensión aprobable, no permiso para standalone.

**Evidencia:** Versiones/hash, fixture y proxy reproducibles, métricas antes/durante/después, resultados de cancel/recovery/offline y ADR con alternativa rechazada.

**Rollback:** Retirar sólo entorno de prueba y restaurar configuración que se hubiera cambiado con permiso; no dejar instalaciones globales ni previews residentes.

**Esfuerzo orientativo:** 1–3 días técnicos como timebox inicial. Si a mitad ningún candidato pasa sincronía/memoria, repriorizar alternativa/proxies; al agotar presupuesto reportar bloqueo o pedir ajuste, no ampliar silenciosamente ni dar demos como cumplimiento.

### 2 · MVP del plugin editor dentro de Hermes Web

**Responsables:** Antigravity implementa y prueba después de autorización y diseño aprobado; Grok Bot revisa alcance/aceptación; Gustavo valida flujo y preview.

**Entrada:** Gate 1, extensión UI real verificada o propuesta compatible/versionada aprobada, y autorización de implementación. UI obligatoria dentro de Hermes Web desde el MVP; reusable o mínima propia. No otra app, GUI desktop o comandos de escenas.

#### 2.1 · Diseñar proyecto e ingesta
Contrato versionado de proyecto compartido con Hermes: projectId/revisión y selección explícita de assets/guion autorizados; motor/tag, fps racional, dimensiones, escenas, hashes/derechos/offsets. Ediciones deterministas y revisión base para detectar conflicto, no sobrescribir cambios concurrentes. Originales read-only, rutas autorizadas y relink; sin copiar secretos o contexto completo indiscriminadamente.

#### 2.2 · Construir sólo controles faltantes
Editor visual en la superficie de Hermes Web, junto a su experiencia de navegador y proyecto activo: importar captura/clip/audio; play/pause/scrub; arrastre/botones, trim y split según alcance; texto/captions, volumen y horizontal/vertical. UI reutilizada o controles mínimos, no salto a app aparte. No NLE profesional.

#### 2.3 · Preview, guardado y undo
Preview bajo consumo usando el mismo timing que export. Autosave e historial recuperable, validación al abrir, undo básico y migraciones no destructivas. Ningún MP4 sustituye el proyecto editable.

#### 2.4 · Servicio de jobs separado
Cola persistente fuera del gateway con snapshot inmutable, idempotency key y un job concurrente. Estados explícitos y progreso por etapa/frames. JSON atómico o SQLite propios del servicio backend del plugin; no consultar/editar DB interna de Hermes por fuera de APIs soportadas.

#### 2.5 · Worker y export seguro
Worker con permisos mínimos, carpeta por job, allowlist de ejecutables/argumentos y sin secretos heredados. MP4 H.264/AAC 720p/30 inicial si cabe en recursos; staging, validación y promoción atómica. Pausa en límite de chunk/escena si el motor lo soporta.

#### 2.6 · Probar recuperación autónoma
Cancelar libera el árbol propio; reanudar sólo desde checkpoint completo y relanzar sin duplicados. Caída o reconexión de Hermes no pierde la cola backend del plugin. Medio inválido, disco lleno o fallo de encoder no corrompen el proyecto ni producen éxito falso.

**Salida / gate:** Gate 2: usuario no programador entra desde Hermes Web y completa dentro de esa superficie seleccionar contexto → importar → editar → guardar → reabrir → preview → export → resultado en chat/proyecto. Un motor y mismo documento versionado; backend de jobs desacoplado, no UI independiente. Demo, link externo o GUI nativa no aprueban.

**Evidencia:** Proyecto fixture, pruebas de persistencia/recovery, matriz del MVP, muestras de export y guía local; ningún dato privado en artefactos de revisión.

**Rollback:** Revertir versión del plugin UI/servicio backend y abrir copia previa del proyecto por interfaz soportada; migraciones reversibles o copias antes de migrar. Conservar originales y backups.

**Esfuerzo orientativo:** Reutilización: 2–5 días técnicos; shell nueva acotada: 6–12 días, confianza baja. Un editor general requeriría una estimación aparte.

### 3 · Completar contexto y orquestación Hermes

**Responsables:** Antigravity integra y verifica con permiso; Grok Bot revisa identidad, scope y evidencia; Gustavo coordina acceso y recargas si hicieran falta.

**Entrada:** Gate R y Gate 2 completos. Licencias, extensión y controles mínimos de aislamiento resueltos antes de incorporar el worker.

#### 3.1 · Elegir interfaz soportada
Revalidar la API UI identificada en fase 0 y su compatibilidad/versiones. Mantener el editor dentro de Hermes Web, con continuidad de proyecto y permisos. Si el soporte no existe o cambió, detener y presentar extensión UI compatible/versionada para aprobar; no enlazar otra app como reemplazo. Ningún cambio core sin necesidad demostrada y autorización.

#### 3.2 · Reutilizar skill y exponer lo mínimo
Si se elige HyperFrames, usar su skill oficial compatible, sin duplicarla ni colisionar. Plugin UI y tools estrechos: selección de contexto, validar, preview, encolar, estado, pausar/cancelar y devolver resultado al mismo chat/proyecto. Una skill no ejecuta ni aísla por sí sola.

#### 3.3 · Mantener identidad y permisos
La selección de JEV conserva namespace, propietario y ruta hasta la apertura. Respetar plataforma, perfil, canal y desactivaciones. No fallback por nombre pelado. Roots explícitas del proyecto, no todo el usuario o disco.

#### 3.4 · Usar MCP sólo si hace falta
FilmCraft dispone de MCP stdio y puente desktop documentados. Allowlist de comandos y token de sesión según protocolo; no exponer TCP a LAN ni todos los comandos a la IA. No introducir MCP si basta CLI/API local soportada.

#### 3.5 · Ensayar lifecycle temporal
Petición → proyecto/preview → aprobación necesaria → job asíncrono → progreso → cancelación o finalización → retorno al Padre por mecanismo interno soportado. Tablero y sesiones de prueba sin cron ni mensajes externos.

#### 3.6 · Probar independencia y degradación
Desconectar/reconectar Hermes de prueba manteniendo cola y estado coherentes; comprobar que preview/render no bloquea el gateway. Si falta seam soportado o falla gate R, registrar bloqueo y conservar sólo artefactos/pruebas recuperables del plugin; no presentar standalone como producto válido.

**Salida / gate:** Gate 3: ciclo real dentro de Hermes Web con proyecto/contexto autorizado, identidad correcta, edición versionada, retorno al chat/proyecto, recuperación tras caída y gateway dentro del umbral acordado. Disco instalado sin prueba runtime no cumple.

**Evidencia:** Traza de job y lifecycle sin secretos, prueba de colisión/exclusiones, métricas y comparativa de archivos/config antes y después.

**Rollback:** Desactivar/revertir sólo plugin UI/adaptador/backend añadidos conservando proyectos; restauración selectiva por manifest y hash. No sustituir entrega por standalone. No cambiar perfiles, proveedores o credenciales para hacer pasar la prueba.

**Esfuerzo orientativo:** 2–4 días técnicos orientativos, confianza baja hasta conocer extensión y runtime real.

### 4 · Endurecer calidad, seguridad y recursos

**Responsables:** Antigravity ejecuta matriz y corrige defectos autorizados; Grok Bot revisa evidencia y claims; Gustavo acepta límites operativos.

**Entrada:** MVP o adaptación funcional; controles básicos de seguridad ya presentes, no aplazados a esta fase. Para producto integrado, gate 3.

#### 4.1 · Cobertura de medios y español
Windows y grabaciones habituales: VFR/CFR, seek en cortes, A/V y captions, fuentes con áéíóúüñ, audio ausente, archivo dañado y media offline. Para FilmCraft, al menos tres grabaciones reales autorizadas y reproducción del export en dos reproductores.

#### 4.2 · Aislamiento Windows verificable
Job Objects para límites y terminación del árbol, no como barrera de seguridad. Evaluar identidad/token restringido, permisos de carpetas y AppContainer/sandbox compatible. Mantener sandbox de Chrome; sus flags no equivalen a bloqueo de red ni aislamiento de archivos.

#### 4.3 · Privacidad y egress
Prueba negativa de lectura fuera de raíz, traversal/junction, acceso a secretos y conexiones no permitidas. Enforce egress con mecanismo de SO/entorno validado que cubra procesos hijos; flags de Chrome sólo defensa adicional. Si no se demuestra aislamiento, limitar a plantillas confiables o bloquear composiciones arbitrarias.

#### 4.4 · Fallos y recuperación
Cola persistente, pausa diferida honesta, cancelación, caída de worker/supervisor, reintentos limitados, OOM/disco lleno en entorno controlado. No usar datos reales ni provocar fallos destructivos en producción. Verificar cierre de preview y cero procesos propios residuales.

#### 4.5 · Memoria y latencia
Con hardware medido: repetir baseline y render comparables, medir p95 y RSS de todo el árbol. Si no cabe 720p, evaluar 540p/proxies o abandonar automatización local; no aumentar memoria, cloud o concurrencia por cuenta propia.

#### 4.6 · Empaquetar evidencia de release
SBOM/licencias de software, build FFmpeg, fuentes, registry, marcas y medios; requisitos offline/telemetría por versión, manual, known issues y rollback ensayado. Una auditoría operativa no equivale a certificación legal o de seguridad completa.

**Salida / gate:** Gate 4: tests críticos aprobados, límites medidos y documentados, sin pérdida de datos ni fuga de secretos/procesos; licencias compatibles con uso elegido.

**Evidencia:** Reporte pass/fail por requisito, métricas reproducibles, intentos negativos de acceso, matriz de códecs, SBOM y prueba de restauración.

**Rollback:** No liberar versión fallida; volver al binario y esquema compatibles conservando proyectos originales. Restringir funciones no aislables en lugar de desactivar controles.

**Esfuerzo orientativo:** 2–4 días técnicos orientativos, confianza media; revisiones legales y correcciones profundas no incluidas.

### 5 · Entrega y distribución elegida

**Responsables:** Antigravity prepara paquete local cuando se autorice; Grok Bot documenta y revisa; Gustavo acepta y autoriza cualquier envío, publicación o compra.

**Entrada:** Gate D para la demo; Gate 4 y términos resueltos para distribuir aplicación. Son entregas diferentes.

#### 5.1 · Elegir qué se entrega
Entrega principal: plugin editor básico dentro de Hermes Web, local-first, con contexto de proyecto y manual. Entrega complementaria: MP4 demo autorizado. Distribución de aplicación o venta sólo si se pide aparte; permiso de render no equivale a revender un fork.

#### 5.2 · Preparar paquete local
Versiones fijadas, instalación aislada/reproducible si aplica, checksums, licencias/NOTICE, manual de recursos, recuperación y desinstalación selectiva. No incluir credenciales, datos de terceros ni medios sin derechos de redistribución.

#### 5.3 · Aceptación de Gustavo
Revisar vídeo o flujo de la herramienta, límites, coste y soporte. Registrar qué fue verificado en PC y qué sigue propuesto. No anunciar 1080p, offline total o Panteón completo sin pruebas.

#### 5.4 · Autorizar acción externa por separado
Antes de publicar/subir/enviar: destino, contenido y versión exacta aprobados. Antes de pagar: producto, importe y autorización. Si no hay permiso, dejar entrega local lista y detenerse.

#### 5.5 · Cerrar y mantener el plan
Archivar informe, ADR, hashes y resultados; actualizar esta Page con estado real. Nuevos motores, cloud, SaaS, colaboración o timeline profesional requieren alcance y decisión nuevos, no ampliación silenciosa.

**Salida / gate:** Gate 5: entrega local aceptada; si hubo distribución, permisos y derechos específicos registrados. Publicación no es condición para que el vídeo esté terminado.

**Evidencia:** Lista de artefactos/versiones, aceptación, licencias y aprobación externa sólo si corresponde.

**Rollback:** Conservar versión anterior y guía selectiva de desinstalación; cualquier retirada externa requiere su autorización y mecanismo oficial, no se presume automática.

**Esfuerzo orientativo:** Según plataforma y modalidad; se estima después del gate 4. No hay fecha de distribución fijada.

## Aceptación del editor en navegador

La entrega se prueba con Gustavo o una persona que no programa. Los botones/controles y el documento de proyecto deben permitir estos escenarios sin abrir terminal, HTML, JSON ni código. Se graba evidencia sólo con consentimiento y datos sintéticos.

### U1 · Crear e importar
Entrar desde la propia superficie Hermes Web sin abrir otra app; mantener proyecto activo y seleccionar explícitamente assets/guion autorizados. Importar captura/clip/audio con errores claros; ningún secreto o contexto completo implícito.

### U2 · Editar visualmente
Reproducir y hacer scrub, arrastrar/reordenar dos escenas, recortar inicio/fin y partir un clip si split quedó fijado como esencial; cambiar texto/subtítulo, volumen y formato horizontal/vertical. Undo recupera al menos la última edición.

### U3 · Guardar y recuperar
Guardar revisión determinista, cerrar y reabrir el proyecto en Hermes Web: conservar orden/cortes/textos/captions/audio/encuadre y selección de contexto. Conflictos de revisión no sobrescriben cambios. Ensayar autosave y recuperación en prueba.

### U4 · Preview y export consistentes
Previsualizar y solicitar MP4 dentro de Hermes Web. Ver cola/progreso, cancelar ensayo y exportar sin duplicados. Preview/export usan el mismo documento versionado y contexto autorizado. El resultado y su revisión vuelven al chat/proyecto correspondiente sin publicación externa.

Editor UI integrado y motor backend son capas separadas del mismo producto. No aprueban renderer CLI, Player sin controles, GUI desktop ni app que Hermes sólo abre. HyperFrames Studio sólo se reutiliza si sus componentes/UI y contrato de contexto pueden integrarse legal y técnicamente dentro de Hermes Web; si no, controles mínimos integrados. Sin extensión UI viable: bloqueo y propuesta versionada para aprobación.

## Pruebas y condiciones de parada

Son criterios propuestos para acordar y medir, no resultados observados. El fixture, equipo, versión y carga se registran para que el pass/fail sea reproducible. Ajustar un umbral requiere justificación explícita, no esconder una prueba fallida.

| Prueba | Objetivo propuesto | Parada / respuesta |
| --- | --- | --- |
| Sincronía y seek | A/V <=1 frame en fixture con referencia; cortes/captions correctos con VFR y proxy CFR. | Desfase >2 frames persistente tras corrección documentada: rechazar candidato. Entre 1 y 2 no aprueba; investigar. |
| Recursos + gateway | Sin OOM ni paginación sostenida; p95 <=20% sobre baseline comparable; RSS del árbol y margen registrados. | Si falla 720p, repetir a 540p/proxy. Si sigue degradando, descartar automatización local o cambiar alcance. |
| Cancelación | Árbol propio liberado y estado terminal correcto; objetivo inicial <=10 s desde cancelación, a validar por motor. | Huérfanos, borrado ajeno o duplicados: bloqueo hasta corregir. Nunca kill global de Chrome/Node. |
| Pause y recovery | Pausa diferida visible, checkpoint íntegro; reinicio/reintento sin perder proyecto ni duplicar salida. | Si motor no permite pausa fiable, decirlo y usar cancel/restart; no marcar soporte inexistente. |
| UX y guardado | Todas las tareas críticas y reabrir sin pérdida; 80% ponderado es pista para reutilizar. | Carencia crítica pesa más que porcentaje. Construir UI sólo si necesidad y coste están aprobados. |
| Offline y aislamiento | Export de prueba sin egress no permitido ni acceso a secretos/fuera de raíz. | Red obligatoria: declarar no apto para offline estricto; no evadir licencia. Aislamiento fallido bloquea código arbitrario. |
| Compatibilidad | 3 grabaciones habituales para FilmCraft; export reproducible en dos reproductores y parámetros correctos. | Formato habitual incompatible no resuelto: limitar soporte o descartar para MVP. |
| Privacidad y derechos | Cero secretos/datos de terceros en capturas, logs y entregables; activos y consentimiento identificados. | Cualquier fuga o derecho desconocido: detener entrega y corregir, no publicar. |
| Integración | Identidad namespaced, exclusiones y ciclo Panteón reales; cola sobrevive desconexión Hermes. | Suite aislada o sólo archivos instalados: no cumple gate runtime. |
| Salida y rollback | Duración/fps/resolución/audio verificados; staging atómico; restauración ensayada. | MP4 parcial o proyecto corrupto: no release; conservar originales y volver a versión compatible. |

Comparar frames/audio con tolerancias documentadas, no prometer MP4 byte-idéntico. Umbral de memoria se fija con datos reales; no se inventa un número universal para 8 GB. En el spike: máximo propuesto 1–3 días, un job y hasta 10 GB temporales si están disponibles; coste externo cero. Si se agota el timebox sin candidato apto, reportar bloqueo y siguiente alternativa del editor web; la demo puede seguir en paralelo, pero no cumple la entrega principal.

## Riesgos y decisiones pendientes

| Prioridad | Riesgo | Respuesta |
| --- | --- | --- |
| P0 | Exponer datos o ejecutar composición no confiable con acceso al usuario. | Consentimiento, perfil sintético, mínimos permisos y prueba negativa; detener si no se aísla. |
| P0 | Licencia incompatible con distribución de editor. | Resolver por tag/uso antes de producto; GSAP pendiente y Remotion separado de permiso para MP4. |
| P0 integración | Dar Hermes por reparado sin ciclo real. | Gate R independiente; no demostrar como terminado lo pendiente. |
| P1 | Memoria, VFR/seek y compatibilidad de codecs. | Fixtures reales, proxies CFR y stop conditions; alternativa editor existente. |
| P1 | WebUI sin extensión o skill/CLI desalineadas. | Bloqueo UI y propuesta compatible/versionada para aprobación; no app externa como fallback. |
| P2 | ETA imprecisa, assets/telemetría y mantenimiento. | Progreso por etapa, licencias/SBOM, reporting compatible y actualizaciones verificadas. |

1. Supuesto a aclarar sin bloquear el plan: ¿«heat fix» era HyperFrames u otra herramienta? El editor web ya está confirmado; si era otra base se añade al análisis antes de elegir motor.
2. Alcance aprobado: plugin editor esencial dentro de Hermes Web, una continuidad con navegador y contexto del proyecto. No preguntar otra vez editor versus demos ni ofrecer app separada. Venta/distribución y términos se deciden aparte; no son autorización de despliegue.
3. Consentimiento previo a capturar: qué ventanas/materiales y qué plugins reales se pueden mostrar. Mientras tanto se trabaja con medios ya autorizados o storyboard.

Las incógnitas técnicas —hardware, extensión, versiones, formatos y licencias exactas— las resuelve Antigravity en la etapa autorizada, sin trasladar a Gustavo un interrogatorio técnico ni abrir nuevos trabajos ahora.

## Handoff futuro a Antigravity

La revisión ya terminó. Estas instrucciones quedan listas para una ejecución posterior, sólo de la fase que Gustavo autorice; no se ha enviado otra tarea ni se inicia trabajo en la PC desde esta Page.

### H.1 · Leer el paquete y fijar etapa
Leer esta versión del plan, PROPUESTA-PARA-ANTIGRAVITY.md, FUENTES.md y EVALUACION-ANTIGRAVITY-OPUS55.md. Informar fase autorizada, raíz de trabajo, archivos permitidos, límites y criterio de salida. Si el permiso no cubre la acción, detener esa acción.

### H.2 · Resolver hechos antes de cambiar
0R reparación; 0 API/extensión UI real y contexto; D demo auxiliar; 1 componentes/motor integrables; 2 plugin editor dentro de Hermes Web; 3 orquestación completa. Mantener 8 fases y alcance esencial. Si falta soporte UI, documentar bloqueo y propuesta compatible/versionada; no instalar tres bases ni entregar standalone. Comparar hashes y preservar cambios locales.

### H.3 · Ejecutar la fase acotada
Sólo tras aprobación: cambios mínimos respaldados, entorno de prueba y recursos limitados. Registrar versión de Antigravity y modelo realmente usado, sin sustitución silenciosa; la revisión previa fue Opus 5.5 Medium. Nada de compras, modelos nuevos, cloud, cron, notificaciones, capturas reales o publicación por inferencia. No ampliar permisos ni eludir controles.

### H.4 · Probar y reportar
Entregar comandos/resultados, versiones, mediciones, pass/fail, artefactos locales, omisiones y rollback. Distinguir propuesto, documentado upstream, probado aislado, instalado, cargado runtime y extremo a extremo.

### H.5 · Cerrar gate y esperar siguiente decisión
Recomendar avanzar, reutilizar, recortar extras profesionales o parar por bloqueo con evidencia; mantener obligatorio el plugin editor dentro de Hermes Web con contexto compartido explícito. Grok Bot revisa y actualiza esta Page; no pedir una nueva revisión de viabilidad completa si basta el resultado de la fase. La siguiente fase no queda automáticamente autorizada.

Condiciones de recuperación: no reset/clean ni reversión inversa a ciegas; restauración selectiva por hashes y backups. Ningún reinicio que interrumpa tareas, cambio de perfiles/proveedores/secretos o envío externo se incluye por defecto. Los permisos anteriores sobre reparación no se interpretan como autorización nueva para vídeo.

## Fuentes y límites de evidencia

Fuentes leídas el 8 de noviembre de 2026, America/Caracas. Hay snapshots y metadatos en el paquete local. README/main puede adelantarse a release: comprobar funcionalidades/licencias en el tag que se seleccione. Los errores 403 de algunos .md de Remotion no significan inexistencia; las páginas y resultados oficiales se consultaron por WebFetch/WebSearch.

**Archivos de trabajo:** /workspace/hermes-video-proposal/ · propuesta preliminar, FUENTES.md, sources/, evaluación de Antigravity y PLAN-CONSOLIDADO.md. Son archivos del box, no rutas de la PC Windows.

**Qué añadió la revisión:** Demos como apoyo D, reparación 0R separada, VFR/CFR/seek, aislamiento Windows y GSAP como riesgo a verificar. Gustavo confirmó editor esencial dentro de Hermes Web y aprobó el resto: UX decide qué reutilizar, no sustituir por app externa. API UI y contrato de contexto deben verificarse; no están demostrados.

**Qué se matizó al consolidar:** Job Objects no son sandbox; flags Chrome no bloquean red de forma suficiente. GSAP no se declara incompatibilidad probada. Remotion gratuito elegible no significa redistribución libre ni coste obligatorio para Gustavo. 80% UX y umbrales de tests son propuestas, no mediciones.

**No verificado aquí:** Hardware y benchmarks, runtime actual de Hermes, codecs en la PC, extensión WebUI, licencia GSAP exacta, derechos de futuros medios y fecha/reglas del concurso Nous. No hay nuevos despliegues ni tareas externas.

## Enlaces de fuentes

- [HyperFrames: repositorio, CLI, Studio y dependencias](https://github.com/heygen-com/hyperframes)
- [HyperFrames v0.9.23](https://github.com/heygen-com/hyperframes/releases/tag/v0.9.23)
- [Skill opcional oficial de HyperFrames para Hermes](https://hermes-agent.nousresearch.com/docs/user-guide/skills/optional/creative/creative-hyperframes)
- [FilmCraft: GUI, Rust, estado y licencias](https://github.com/storytold/filmcraft)
- [FilmCraft v0.18.0](https://github.com/storytold/filmcraft/releases/tag/v0.18.0)
- [FilmCraft: atribución de activos y fuentes](https://github.com/storytold/filmcraft/blob/main/ATTRIBUTION.md)
- [FilmCraft: control y MCP](https://github.com/storytold/filmcraft/blob/main/docs/control-protocol.md)
- [Remotion License](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md)
- [Remotion v4.0.541](https://github.com/remotion-dev/remotion/releases/tag/v4.0.541)
- [Remotion Player](https://www.remotion.dev/docs/player)
- [Remotion renderer](https://www.remotion.dev/docs/renderer)
- [Remotion: licencia y precios FAQ](https://www.remotion.dev/docs/license/faq)
- [Remotion: términos publicados](https://www.remotion.dev/docs/terms)
- [Remotion: telemetría y versiones](https://www.remotion.dev/docs/licensing/)
- [Editor Starter: producto y licencia separados](https://www.remotion.dev/docs/editor-starter)
- [Remotion: Chrome Headless Shell](https://www.remotion.dev/docs/miscellaneous/chrome-headless-shell)
- [Remotion 4: FFmpeg integrado](https://www.remotion.dev/blog/4-0)
