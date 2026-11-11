"""Pruebas de la interfaz rediseñada del pane (v0.5, «estudio oscuro»).

Comprueba, con Playwright + Chrome, lo que define el rediseño:
  · tres disposiciones según el ancho del dock (1280 / 922 / 655 px) sin desbordes
  · barra superior con Exportar como botón primario, estado de guardado y deshacer/rehacer
  · línea de tiempo de varios carriles (Vídeo, Texto, Audio, Música), regla con marcas,
    cabezal, zoom +/− y ajustar, imán al arrastrar en la regla
  · panel izquierdo de escenas/medios y cajones en anchos estrechos
  · avisos (toast) al guardar y estados vacíos

Mismas variables de entorno que pane_ui_e2e.py (VE_HARNESS, VE_SVC, VE_TOKEN,
VE_MEDIA, VE_CHROME). Crea y borra sus propios proyectos."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pane_ui_e2e as base  # noqa: E402
from pane_ui_e2e import call, check, doc, make_project, open_pane, CREATED, RESULTS  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def seconds(tc):
    return int(tc[:2]) * 60 + float(tc[3:].replace(',', '.'))


def rich_project(title):
    pid = make_project(title)
    d = doc(pid)
    names = ['Apertura', 'Demo', 'Tutorial', 'Cierre']
    for i, s in enumerate(d['scenes']):
        s['name'] = names[i]
    d['scenes'][2]['text'] = [{'at': 0.2, 'until': 3.0, 'position': 'top', 'content': 'Paso 1', 'size': 40}]
    d['scenes'][1]['audio']['volume'] = 40
    cur = call('GET', f'/projects/{pid}')[1]
    status, r = call('PUT', f'/projects/{pid}', {'revision': cur['revision'], 'project': d})
    assert status == 200, r
    return pid


def no_overflow(pg):
    return pg.evaluate("""() => {
      const root = document.querySelector('.ve-root'); const r = root.getBoundingClientRect();
      const bad = [...root.querySelectorAll('.ve-hdr, .ve-main, .ve-transport, .ve-tl')].filter(e => {
        const b = e.getBoundingClientRect(); return b.right > r.right + 1 || b.left < r.left - 1 })
      return {sw: root.scrollWidth <= root.clientWidth + 1, bad: bad.map(e => e.className)}
    }""")


def main():
    if not base.MEDIA:
        sys.exit('define VE_MEDIA con la carpeta de clips de prueba')
    with sync_playwright() as p:
        try:
            pid = rich_project('rd-A')
            # --- 1280: tres columnas ------------------------------------------------
            b, pg, errs = open_pane(p, pid, 1280, 800)
            check('D1 disposición ancha (data-layout=wide)', pg.locator('.ve-root').get_attribute('data-layout') == 'wide')
            check('D2 panel de escenas visible junto al vídeo', pg.locator('.ve-side').is_visible() and pg.locator('.ve-rail').is_visible())
            check('D3 sin desbordes horizontales a 1280', (lambda o: o['sw'] and not o['bad'])(no_overflow(pg)), str(no_overflow(pg)))
            ex = pg.get_by_role('button', name='Exportar').first
            check('D4 Exportar es el botón primario de la barra superior', 've-btn--primary' in (ex.get_attribute('class') or '') and ex.evaluate('e=>!!e.closest(".ve-hdr")'))
            check('D5 estado de guardado, deshacer y rehacer en la barra', pg.locator('.ve-hdr .ve-auto').count() == 1 and pg.get_by_role('button', name='Rehacer').count() == 1)
            # carriles
            heads = [t.strip() for t in pg.locator('.ve-lh').all_inner_texts()]
            check('D6 cuatro carriles: Vídeo, Texto, Audio, Música', heads == ['Vídeo', 'Texto', 'Audio', 'Música'], str(heads))
            check('D7 hay un bloque de texto por escena con texto (escena 1 y 3)', pg.locator('.ve-txb').count() == 2, str(pg.locator('.ve-txb').count()))
            check('D8 el carril de audio tiene un bloque por escena', pg.locator('.ve-ab').count() == 4)
            check('D9 cada clip lleva miniaturas', pg.locator('.ve-clip').first.locator('.ve-thumb').count() >= 1)
            check('D10 el cabezal existe', pg.locator('.ve-playhead').count() == 1)
            check('D11 la regla marca segundos (≥4 marcas)', pg.locator('.ve-tick').count() >= 4)
            # clic en el bloque de texto → selecciona esa escena y salta a su inicio
            pg.locator('.ve-txb').nth(1).click(); pg.wait_for_timeout(300)
            check('D12 clic en un texto selecciona su escena (Tutorial)', pg.locator('.ve-clip--sel .ve-clip__t').inner_text() == 'Tutorial')
            # zoom
            w0 = pg.locator('.ve-tl__inner').evaluate('e=>e.getBoundingClientRect().width')
            pg.get_by_role('button', name='Acercar').click(); pg.get_by_role('button', name='Acercar').click(); pg.wait_for_timeout(300)
            w1 = pg.locator('.ve-tl__inner').evaluate('e=>e.getBoundingClientRect().width')
            check('D13 «Acercar» ensancha la línea de tiempo (225 %)', w1 > w0 * 2 and pg.locator('.ve-zoom__v').inner_text().strip() == '225 %', f'{w0:.0f}→{w1:.0f} {pg.locator(".ve-zoom__v").inner_text()}')
            check('D14 con zoom hay desplazamiento horizontal', pg.locator('.ve-tl__scroll').evaluate('e=>e.scrollWidth>e.clientWidth'))
            pg.get_by_role('button', name='Ajustar a la ventana').click(); pg.wait_for_timeout(250)
            w2 = pg.locator('.ve-tl__inner').evaluate('e=>e.getBoundingClientRect().width')
            check('D15 «Ajustar» vuelve al 100 %', abs(w2 - w0) < 2 and pg.locator('.ve-zoom__v').inner_text().strip() == '100 %')
            # imán: soltar a ≤7 px de un borde de escena salta exactamente al borde (3,0 s)
            ruler = pg.locator('.ve-tl__ruler').bounding_box(); total = 12.2
            x3 = ruler['x'] + ruler['width'] * (3.0 / 12.5) + 4   # ~4 px a la derecha del borde
            pg.mouse.click(x3, ruler['y'] + 12); pg.wait_for_timeout(250)
            tc = pg.locator('.ve-tc b').inner_text()
            check('D16 imán: a 4 px del borde el cursor cae en el borde de la escena', abs(seconds(tc) - 3.0) < 0.02, tc)
            pg.keyboard.down('Alt'); pg.mouse.click(x3, ruler['y'] + 12); pg.keyboard.up('Alt'); pg.wait_for_timeout(250)
            tc = pg.locator('.ve-tc b').inner_text()
            check('D17 Alt desactiva el imán', abs(seconds(tc) - 3.0) > 0.02, tc)
            # reproducir / pausar
            pg.get_by_role('button', name='Reproducir').click(); pg.wait_for_timeout(300)
            check('D18 el botón de reproducción cambia a «Pausar»', pg.get_by_role('button', name='Pausar').count() == 1)
            pg.get_by_role('button', name='Pausar').click()
            # toast al guardar a mano
            pg.get_by_label('Nombre de la escena').fill('Intro nueva'); pg.get_by_role('button', name='Guardar').first.click(); pg.wait_for_timeout(500)
            check('D19 aviso «Guardado» al guardar', pg.locator('.ve-toast').count() == 1 and 'Guardado' in pg.locator('.ve-toast').inner_text())
            pg.wait_for_timeout(2600)
            check('D20 el aviso desaparece solo', pg.locator('.ve-toast').count() == 0)
            # panel izquierdo: medios
            pg.get_by_role('button', name='Medios', exact=True).click(); pg.wait_for_timeout(300)
            check('D21 pestaña Medios lista los archivos del proyecto (≥4)', pg.locator('.ve-lib__item').count() >= 4, str(pg.locator('.ve-lib__item').count()))
            n0 = pg.locator('.ve-clip').count()
            pg.get_by_role('button', name='Añadir intro.mp4 como escena').click(); pg.wait_for_timeout(900)
            check('D22 «+» añade el medio como escena nueva', pg.locator('.ve-clip').count() == n0 + 1, f'{n0}→{pg.locator(".ve-clip").count()}')
            check('D23 sin errores de página', not errs, str(errs))
            b.close()

            # --- 922: dos columnas, panel izquierdo en cajón ---------------------------
            b, pg, errs = open_pane(p, pid, 922, 800)
            check('D24 a 922 px: disposición media, propiedades visibles, panel izquierdo oculto', pg.locator('.ve-root').get_attribute('data-layout') == 'mid' and pg.locator('.ve-rail').is_visible() and not pg.locator('.ve-side').is_visible())
            check('D25 sin desbordes horizontales a 922', (lambda o: o['sw'] and not o['bad'])(no_overflow(pg)), str(no_overflow(pg)))
            pg.get_by_role('button', name='Medios y escenas').click(); pg.wait_for_timeout(350)
            check('D26 el cajón «Medios y escenas» se abre a la izquierda', pg.locator('.ve-side').is_visible() and pg.locator('.ve-side').evaluate('e=>e.getBoundingClientRect().left') <= 1)
            pg.keyboard.press('Escape'); pg.wait_for_timeout(300)
            check('D27 Escape cierra el cajón', not pg.locator('.ve-side').is_visible())
            b.close()

            # --- 655: una columna, dos cajones ----------------------------------------
            b, pg, errs = open_pane(p, pid, 655, 800)
            check('D28 a 655 px: disposición estrecha, sin paneles laterales fijos', pg.locator('.ve-root').get_attribute('data-layout') == 'narrow' and not pg.locator('.ve-rail').is_visible() and not pg.locator('.ve-side').is_visible())
            check('D29 sin desbordes horizontales a 655', (lambda o: o['sw'] and not o['bad'])(no_overflow(pg)), str(no_overflow(pg)))
            vis = pg.evaluate("""() => ['.ve-hdr','.ve-stage','.ve-transport','.ve-tl'].map(s => { const e=document.querySelector(s); const b=e.getBoundingClientRect(); return [s, Math.round(b.height)] })""")
            check('D30 vista previa, transporte y línea de tiempo caben en 800 px de alto', all(h > 0 for _, h in vis) and pg.locator('.ve-tl').evaluate('e=>e.getBoundingClientRect().bottom') <= 801, str(vis))
            pg.get_by_role('button', name='Propiedades').click(); pg.wait_for_timeout(300)
            check('D31 «Propiedades» abre el cajón derecho', pg.locator('.ve-rail').is_visible())
            pg.keyboard.press('Escape'); pg.wait_for_timeout(250)
            pg.get_by_role('button', name='Medios y escenas').click(); pg.wait_for_timeout(300)
            check('D32 «Medios y escenas» abre el cajón izquierdo', pg.locator('.ve-side').is_visible())
            pg.locator('.ve-scene').nth(2).click(); pg.wait_for_timeout(300)
            check('D33 elegir una escena en el cajón la selecciona y lo cierra', not pg.locator('.ve-side').is_visible() and pg.locator('.ve-clip--sel .ve-clip__t').inner_text() == 'Tutorial')
            b.close()

            # --- estados vacíos --------------------------------------------------------
            b = p.chromium.launch(executable_path=base.CHROME, args=['--no-sandbox'])
            ctx = b.new_context(viewport={'width': 1280, 'height': 800})
            ctx.add_init_script(f"window.__VE_TOKEN__='{base.TOKEN}'")
            pg = ctx.new_page(); pg.goto(f'{base.HARNESS}/harness/index.html?svc={base.SVC}'); pg.wait_for_selector('.ve-es', timeout=15000); pg.wait_for_timeout(300)
            box = pg.locator('.ve-es').bounding_box()
            check('D34 sin proyecto: el estado vacío queda centrado', box is not None and 400 < box['x'] + box['width'] / 2 < 880, str(box))
            b.close()
        finally:
            for pid in CREATED:
                call('DELETE', f'/projects/{pid}')
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} correctas")
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
