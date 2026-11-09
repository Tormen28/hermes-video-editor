# Reglas del plugin Editor de vídeo

Estas reglas son el contrato de uso. Si algo no está aquí, no se asume.

## 1 · Local primero

- El editor, la edición y el export funcionan **sin conexión y sin proveedores externos**.
- El servicio escucha solo en `127.0.0.1`; no se expone a la LAN ni a internet.
- Los medios se leen de la carpeta concedida (`mediaRoot`); no se suben a ningún sitio.
- Nada de telemetría propia.

## 2 · La generación es opcional

- Sin proveedor configurado existe el **proveedor local** (imagen/música sintéticas, gratis y sin red).
- Los proveedores externos se conectan con `VE_PROVIDER_IMAGE_URL` / `VE_PROVIDER_MUSIC_URL` (+ `_KEY`).
- Si un proveedor HTTP no está configurado, la petición devuelve **400 claro**; no hay fallback silencioso ni gasto automático.
- Las claves viven en el entorno del servicio. **Nunca** en el proyecto, el chat, el Kanban o el vault.
- Cada asset generado guarda `rights.status="generated"` y notas con proveedor, prompt y fecha.

## 3 · Dinero y permisos

- El plugin no compra, no publica, no envía mensajes y no despliega.
- Usar un proveedor de pago exige que el dueño lo configure y autorice; el plugin no decide precios ni suscripciones.
- Exportar es local y gratuito; compartir o publicar el resultado es decisión del usuario.

## 4 · Datos y originales

- Los originales no se modifican; se leen y se referencian por hash.
- El proyecto guarda la edición (documento versionado), no copias indiscriminadas de los medios.
- Borrar un proyecto o un medio exige confirmación explícita.
- No se copian chats, credenciales ni contexto completo del usuario al servicio.

## 5 · Límites declarados

- Una pista de música por proyecto; SFX por eventos con tiempo.
- El preset manda el tamaño de salida (720p, vertical, cuadrado); 1080p es experimental hasta medir recursos.
- Transiciones visuales (`xfade`); el audio entre escenas va concatenado.
- Ken Burns solo en imágenes.
- No es un editor profesional: sin multicámara, keyframes ni grading avanzado.

## 6 · Calidad y evidencia

- Un export sin `succeeded`, sin validación de resolución/duración/audio y sin archivo reproducible **no es un éxito**.
- Un MP4 parcial nunca se promociona como resultado.
- Los cambios de motor o de contrato requieren decisión registrada y pruebas; no se amplía alcance en silencio.

## 7 · Instalación y soporte

- El instalador solo copia el plugin, crea config y arranca el servicio; no toca modelos, proveedores ni canales de Hermes.
- Desinstalar conserva los datos salvo `--purge`.
- El proyecto se versiona con git; los cambios se hacen con respaldo y posibilidad de volver.

## 8 · Lo que el plugin nunca hará

- Publicar, subir o enviar material a terceros por iniciativa propia.
- Inventar una función o un resultado que no se haya ejecutado.
- Usar credenciales del usuario sin autorización explícita.
- Afirmar 1080p/offline total/Panteón completo sin prueba real.
