"""Regresiones de la interfaz del pane (Playwright + Chrome), v0.4 «pulido».

Cubre los fallos encontrados en la auditoría de la UI:
  · el panel derecho no hacía scroll a ≥1100 px (Filtros, Audio, Logo inalcanzables)
  · los campos numéricos no dejaban escribir decimales ni números de 2 cifras
  · deshacer retrocedía una letra por paso
  · Exportar quedaba deshabilitado tras cada edición
  · clic en un clip / en la regla no movía el cursor al punto pulsado
  · faltaba eliminar, renombrar y la posición del texto
  · la duración mostrada ignoraba velocidad y transiciones
  · en paneles de ~900 px el panel de propiedades estaba oculto

Variables: VE_HARNESS (servidor estático de plugin/, def. http://127.0.0.1:8795),
VE_SVC (servicio, def. http://127.0.0.1:8780), VE_TOKEN o VE_TOKEN_FILE (token del
servicio), VE_MEDIA (carpeta concedida con intro.mp4, demo.mp4, tutorial.mp4 y
cierre.png), VE_CHROME (ruta de Chrome). Crea y borra sus propios proyectos.
No corre en el CI normal: necesita playwright y un navegador."""
import json, os, subprocess, sys, tempfile, time, urllib.error, urllib.request as u
from pathlib import Path
from playwright.sync_api import sync_playwright

HARNESS = os.environ.get('VE_HARNESS', 'http://127.0.0.1:8795')
SVC = os.environ.get('VE_SVC', 'http://127.0.0.1:8780')
MEDIA = os.environ.get('VE_MEDIA', '')
CHROME = os.environ.get('VE_CHROME', '/usr/bin/google-chrome')


def token():
    if os.environ.get('VE_TOKEN'):
        return os.environ['VE_TOKEN'].strip()
    path = os.environ.get('VE_TOKEN_FILE') or str(Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'hermes' / 'video-editor' / 'service.token')
    return Path(path).read_text(encoding='utf-8').strip()


TOKEN = token()


def call(method, path, body=None):
    req = u.Request(SVC + path, data=None if body is None else json.dumps(body).encode(), method=method,
                    headers={'Content-Type': 'application/json', 'X-VE-Token': TOKEN})
    try:
        with u.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


CREATED = []


def make_project(title):
    status, c = call('POST', '/projects', {'title': title, 'session_id': 'sess_ui', 'cwd': MEDIA})
    assert status == 201, c
    pid = c['projectId']; CREATED.append(pid)
    for name in ('intro.mp4', 'demo.mp4', 'tutorial.mp4', 'cierre.png'):
        status, body = call('POST', f'/projects/{pid}/media', {'path': f'{MEDIA}/{name}'.replace('\\', '/')})
        assert status == 201, (name, body)
    status, cur = call('GET', f'/projects/{pid}')
    d = cur['project']
    d['scenes'][0]['text'] = [{'at': 0.0, 'until': 2.8, 'position': 'bottom', 'content': 'Hola'}]
    d['scenes'][1]['transition'] = 'fade-0.3'
    status, r = call('PUT', f'/projects/{pid}', {'revision': cur['revision'], 'project': d})
    assert status == 200, r
    return pid


def doc(pid):
    return call('GET', f'/projects/{pid}')[1]['project']


RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print(('PASS' if ok else 'FAIL'), name, detail, flush=True)


def open_pane(p, pid, w=1280, h=800):
    b = p.chromium.launch(executable_path=CHROME, args=['--no-sandbox'])
    ctx = b.new_context(viewport={'width': w, 'height': h})
    ctx.add_init_script(f"window.__VE_TOKEN__='{TOKEN}'")
    pg = ctx.new_page()
    errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto(f'{HARNESS}/harness/index.html?svc={SVC}&open={pid}')
    pg.wait_for_selector('.ve-clip', timeout=20000)
    pg.wait_for_timeout(600)
    return b, pg, errs


def main():
    if not MEDIA:
        sys.exit('define VE_MEDIA con la carpeta de clips de prueba')
    with sync_playwright() as p:
        try:
            # --- panel derecho: scroll y pestañas --------------------------------
            pid = make_project('ui-A')
            b, pg, errs = open_pane(p, pid, 1280, 800)
            body = pg.locator('.ve-rail__body')
            check('R1 el cuerpo del panel hace scroll', body.evaluate('e=>getComputedStyle(e).overflowY') == 'auto')
            pg.get_by_role('tab', name='Efectos').click()
            pg.mouse.move(1100, 500); pg.mouse.wheel(0, 4000); pg.wait_for_timeout(300)
            check('R2 los filtros y el movimiento son alcanzables (scroll real)', body.evaluate('e=>e.scrollTop') > 0 or body.evaluate('e=>e.scrollHeight<=e.clientHeight'))
            pg.get_by_role('tab', name='Proyecto').click(); pg.wait_for_timeout(200)
            logo = pg.get_by_text('Importa una imagen para usarla como logo.')
            pg.locator('.ve-rail__body').evaluate('e=>e.scrollTop=e.scrollHeight'); pg.wait_for_timeout(200)
            box = pg.get_by_text('Resumen del proyecto').bounding_box()
            check('R3 pestaña Proyecto: resumen y logo visibles', box is not None and box['y'] < 800)
            # navegación con flechas entre pestañas
            pg.get_by_role('tab', name='Escena').click(); pg.get_by_role('tab', name='Escena').focus(); pg.keyboard.press('ArrowRight')
            check('R4 flecha derecha cambia de pestaña', pg.get_by_role('tab', name='Efectos').get_attribute('aria-selected') == 'true')
            pg.get_by_role('tab', name='Escena').click()

            # --- campos numéricos ---------------------------------------------------
            sal = pg.get_by_label('Salida de la escena en segundos')
            sal.click(); sal.press('Control+a'); sal.type('2.5', delay=50); pg.wait_for_timeout(200)
            check('N1 escribir 2.5 en Salida', sal.input_value() in ('2.5', '2.50'), repr(sal.input_value()))
            pg.get_by_label('Entrada de la escena en segundos').click(); pg.wait_for_timeout(200)
            check('N1b al salir muestra 2.50', sal.input_value() == '2.50', repr(sal.input_value()))
            tam = pg.get_by_label('Tamaño del texto en puntos')
            tam.click(); pg.keyboard.press('Control+a'); pg.keyboard.type('60', delay=60); pg.wait_for_timeout(200)
            check('N2 escribir 60 en Tamaño del texto', tam.input_value() == '60', repr(tam.input_value()))
            tam.press('ArrowUp'); check('N3 flecha arriba suma 1', tam.input_value() == '61', repr(tam.input_value()))
            tam.press('Control+a'); tam.type('5'); tam.press('Enter'); pg.wait_for_timeout(200)
            check('N4 un valor fuera de rango se ajusta al mínimo al salir (12)', tam.input_value() == '12', repr(tam.input_value()))
            pg.keyboard.press('Control+s'); pg.wait_for_timeout(1500)
            d = doc(pid)
            check('N5 lo escrito llega al servicio (out=2.5, size=12)', abs(d['scenes'][0]['out'] - 2.5) < 1e-6 and d['scenes'][0]['text'][0]['size'] == 12, f"out={d['scenes'][0]['out']} size={d['scenes'][0]['text'][0].get('size')}")

            # --- deshacer agrupado ------------------------------------------------
            pg.get_by_role('tab', name='Escena').click()
            ta = pg.locator('textarea').first
            ta.click(); ta.press('Control+a'); ta.type('texto largo para comprobar el deshacer agrupado', delay=12); pg.wait_for_timeout(1200)
            pg.locator('.ve-root').focus()
            steps = 0
            while steps < 80 and not pg.get_by_role('button', name='Deshacer').is_disabled():
                pg.get_by_role('button', name='Deshacer').click(); steps += 1
            check('U1 deshacer: pocos pasos tras escribir 47 letras', steps <= 6, f'{steps} pasos')
            b.close()

            # --- exportar sin esperar al autoguardado -----------------------------
            pid = make_project('ui-B')
            b, pg, errs = open_pane(p, pid)
            pg.locator('textarea').first.fill('Texto nuevo'); pg.wait_for_timeout(150)
            ex = pg.get_by_role('button', name='Exportar').first
            check('E1 Exportar sigue activo justo tras editar', ex.is_enabled())
            check('E2 el estado dice «Cambios sin guardar»', 'sin guardar' in pg.locator('.ve-auto').inner_text().lower(), pg.locator('.ve-auto').inner_text())
            ex.click(); pg.wait_for_timeout(400)
            pg.get_by_role('dialog').get_by_role('button', name='Exportar').click()
            deadline = time.time() + 150; job = None
            while time.time() < deadline:
                jobs = call('GET', '/jobs')[1]; lst = jobs.get('jobs') if isinstance(jobs, dict) else jobs
                job = next((j for j in lst if j.get('projectId') in (pid, None)), lst[0] if lst else None)
                if job and job.get('state') in ('succeeded', 'failed', 'cancelled'): break
                time.sleep(1)
            check('E3 la exportación termina bien', job and job.get('state') == 'succeeded', str(job and job.get('state')))
            check('E4 el servidor tiene el texto editado (se guardó antes de exportar)', doc(pid)['scenes'][0]['text'][0]['content'] == 'Texto nuevo')
            if job and job.get('state') == 'succeeded':
                req = u.Request(SVC + f"/jobs/{job['jobId']}/output", headers={'X-VE-Token': TOKEN})
                out = Path(tempfile.gettempdir()) / 'pane_ui_export.mp4'; out.write_bytes(u.urlopen(req).read())
                probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_name,width,height', '-of', 'json', str(out)], capture_output=True, text=True)
                info = json.loads(probe.stdout or '{}')
                dur = float(info.get('format', {}).get('duration', 0))
                shown = pg.locator('.ve-ftr__hint').inner_text()
                check('E5 el MP4 dura lo que anuncia el pie (transición solapada: 12,2 s)', abs(dur - 12.2) < 0.15, f'ffprobe={dur:.2f}s pie={shown!r}')
            b.close()

            # --- línea de tiempo --------------------------------------------------
            pid = make_project('ui-C')
            b, pg, errs = open_pane(p, pid)
            clips = pg.locator('.ve-clip'); bb = clips.nth(2).bounding_box()
            pg.mouse.click(bb['x'] + bb['width'] * 0.75, bb['y'] + bb['height'] / 2); pg.wait_for_timeout(250)
            tc = pg.locator('.ve-tc b').inner_text(); secs = int(tc[:2]) * 60 + float(tc[3:])
            check('T1 clic a ¾ del clip 3 salta a ese punto', 8.0 < secs < 8.9, tc)
            ruler = pg.locator('.ve-tl__ruler').bounding_box()
            pg.mouse.click(ruler['x'] + ruler['width'] * 0.1, ruler['y'] + 12); pg.wait_for_timeout(250)
            tc2 = pg.locator('.ve-tc b').inner_text(); secs2 = int(tc2[:2]) * 60 + float(tc2[3:])
            check('T2 clic en la regla mueve el cursor (≈1,25 s)', 0.9 < secs2 < 1.6, tc2)
            # arrastrar en la regla
            pg.mouse.move(ruler['x'] + 20, ruler['y'] + 12); pg.mouse.down(); pg.mouse.move(ruler['x'] + ruler['width'] * 0.6, ruler['y'] + 12, steps=6); pg.mouse.up(); pg.wait_for_timeout(250)
            tc3 = pg.locator('.ve-tc b').inner_text(); secs3 = int(tc3[:2]) * 60 + float(tc3[3:])
            check('T3 arrastrar en la regla (≈7,5 s)', 6.8 < secs3 < 8.2, tc3)
            check('T4 las marcas de la regla existen y son reales', pg.locator('.ve-tick').count() >= 3)
            check('T5 hay un carril de audio por escena', pg.locator('.ve-ab').count() == 4)
            b.close()

            # --- funciones que faltaban --------------------------------------------
            pid = make_project('ui-D')
            b, pg, errs = open_pane(p, pid)
            check('F1 botón «Eliminar escena»', pg.get_by_role('button', name='Eliminar escena').count() == 1)
            nombre = pg.get_by_label('Nombre de la escena'); nombre.fill('Mi intro'); pg.keyboard.press('Control+s'); pg.wait_for_timeout(1200)
            check('F2 renombrar escena (llega al servicio)', doc(pid)['scenes'][0]['name'] == 'Mi intro', doc(pid)['scenes'][0]['name'])
            pg.get_by_role('group', name='Posición del texto').get_by_role('button', name='Arriba').click(); pg.keyboard.press('Control+s'); pg.wait_for_timeout(1200)
            check('F3 posición del texto (Arriba)', doc(pid)['scenes'][0]['text'][0]['position'] == 'top')
            check('F4 la vista previa pone el texto arriba', 've-cap--top' in (pg.locator('.ve-cap').get_attribute('class') or ''))
            n0 = pg.locator('.ve-clip').count()
            pg.get_by_role('button', name='Eliminar escena').click(); pg.wait_for_timeout(300)
            check('F5 eliminar escena la quita de la línea de tiempo', pg.locator('.ve-clip').count() == n0 - 1)
            pg.get_by_role('button', name='Deshacer').click(); pg.wait_for_timeout(300)
            check('F6 deshacer la recupera', pg.locator('.ve-clip').count() == n0)
            # velocidad ×2 en una escena: la duración mostrada baja
            pg.get_by_role('tab', name='Efectos').click(); pg.wait_for_timeout(200)
            pg.locator('.ve-clip').nth(2).click(); pg.wait_for_timeout(200)
            sp = pg.get_by_label('Velocidad de la escena'); sp.focus()
            for _ in range(20): sp.press('ArrowRight')
            pg.wait_for_timeout(300)
            tot = pg.locator('.ve-tc').inner_text()
            check('F7 con velocidad ×2 la duración total baja de 12,5 s', '12.500' not in tot.split('/')[1], tot)
            b.close()

            # --- anchos del panel --------------------------------------------------
            pid = make_project('ui-E')
            b, pg, errs = open_pane(p, pid, 922, 800)
            rail_vis = pg.locator('.ve-rail').is_visible()
            check('W1 a 922 px el panel de propiedades se ve junto al vídeo', rail_vis and pg.locator('.ve-root').get_attribute('data-compact') == '0')
            b.close()
            b, pg, errs = open_pane(p, pid, 700, 800)
            check('W2 a 700 px el panel está oculto hasta pulsar «Propiedades»', not pg.locator('.ve-rail').is_visible())
            pg.get_by_role('button', name='Propiedades').click(); pg.wait_for_timeout(300)
            check('W3 …y se abre como cajón lateral', pg.locator('.ve-rail').is_visible() and pg.locator('.ve-rail').evaluate('e=>e.getBoundingClientRect().width') <= 345)
            pg.keyboard.press('Escape'); pg.wait_for_timeout(200)
            check('W4 Escape lo cierra', not pg.locator('.ve-rail').is_visible())
            b.close()
        finally:
            for pid in CREATED:
                call('DELETE', f'/projects/{pid}')
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} correctas")
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
