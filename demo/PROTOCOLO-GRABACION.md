# VIDEO-EDITOR · Demo D · Protocolo de grabación de uso real (consentimiento de Gustavo, 8-nov-2026)

Gustavo autorizó grabar «un uso real en vivo» con material propio. Reglas para que la captura sea honesta y no filtre datos.

## Qué se graba
- **Solo la ventana de la app Hermes** (o el pane del editor cuando exista), no el escritorio completo.
- Resolución 1280x720 o la nativa de la ventana; 30 fps; H.264; sin audio del sistema (audio sintético o voz autorizada después).
- Duración objetivo: 60–90 s por toma; máximo 3 tomas.

## Antes de grabar (checklist que el Padre verifica en pantalla)
- [ ] Cerrar/minimizar Telegram, correo, navegador con sesiones, gestor de contraseñas, wallets.
- [ ] Sin notificaciones: modo No molestar activo.
- [ ] Proyecto de prueba con datos sintéticos («Demo VIDEO-EDITOR»), no el vault real ni chats privados.
- [ ] Barra de tareas sin títulos sensibles; ventanas emergentes cerradas.
- [ ] Tormen da la orden «graba» en el momento; el Padre no graba por iniciativa propia.

## Comando (ventana específica si hay título; si no, pantalla completa)
```bash
# ventana por título exacto (preferido)
ffmpeg -y -f gdigrab -framerate 30 -i title="Hermes" -t 90 -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p "$OUT/demo-toma1.mp4"
# fallback pantalla completa (solo si la ventana no se puede aislar)
ffmpeg -y -f gdigrab -framerate 30 -i desktop -t 90 -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p "$OUT/demo-toma1.mp4"
```
Verificado en esta PC: `gdigrab` responde OK (1 frame a null, sin guardar imagen).

## Después de grabar
1. `ffprobe` para duración/fps/resolución (evidencia en el reporte).
2. Revisión de 6 frames clave (inicio/medio/fin) buscando datos sensibles antes de usar el clip.
3. El MP4 queda en `video-editor/demo/`; **no se publica ni se envía** sin autorización aparte (J3).
4. Si aparece cualquier dato privado: se descarta la toma y se repite.

## Storyboard del demo (D.2 del plan)
45–90 s: problema (montar un vídeo requiere salir de Hermes) → acción real (pane editor: importar, reordenar, trim, texto) → resultado (MP4 exportado y devuelto al chat) → límites (720p/30, un job, sin publicación automática).
