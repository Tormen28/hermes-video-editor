"""Prueba de arrastre/edición del pane en el banco de pruebas (Playwright + Chrome).
Variables: VE_PID (proyecto con 3 escenas), VE_SVC (servicio), VE_HARNESS (servidor estático de plugin/).
No corre en el CI normal: necesita playwright y un navegador."""
import json, sys, time, urllib.request as u
from playwright.sync_api import sync_playwright
import os
HARNESS=os.environ.get('VE_HARNESS','http://127.0.0.1:8795')
pid=os.environ['VE_PID']
SVC=os.environ.get('VE_SVC','http://127.0.0.1:8780')
def doc():
    d=json.loads(u.urlopen(f'{SVC}/projects/{pid}').read()); return d['project']
def summary(d): return [(s['name'],s['in'],s['out']) for s in d['scenes']]
url=f"{HARNESS}/harness/index.html?svc={SVC}&open={pid}"
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    pg=b.new_page(viewport={'width':1280,'height':800})
    errs=[]; pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('console',lambda m: errs.append(m.text) if m.type=='error' else None)
    pg.goto(url); pg.wait_for_selector('.ve-clip',timeout=15000)
    print('before',summary(doc()))
    clips=pg.locator('.ve-clip'); n=clips.count(); print('clips',n)
    pg.screenshot(path='shot-0-before.png')
    # --- move: drag clip 1 onto clip 3
    b0=clips.nth(0).bounding_box(); b2=clips.nth(2).bounding_box()
    x0=b0['x']+b0['width']/2; y=b0['y']+b0['height']/2; x2=b2['x']+b2['width']/2
    pg.mouse.move(x0,y); pg.mouse.down(); 
    for i in range(1,11): pg.mouse.move(x0+(x2-x0)*i/10,y)
    pg.screenshot(path='shot-1-dragging.png')
    pg.mouse.up(); time.sleep(0.3)
    names=[pg.locator('.ve-clip .ve-clip__t').nth(i).inner_text() for i in range(3)]
    print('ui order after move',names)
    pg.screenshot(path='shot-2-moved.png')
    # --- undo
    pg.keyboard.press('Control+z'); time.sleep(0.3)
    print('ui order after undo',[pg.locator('.ve-clip .ve-clip__t').nth(i).inner_text() for i in range(3)])
    # --- trim: select clip 2, drag right handle left
    clips=pg.locator('.ve-clip'); clips.nth(1).click(); time.sleep(0.2)
    bb=clips.nth(1).bounding_box(); print('clip2 box',bb)
    hx=bb['x']+bb['width']-3; hy=bb['y']+bb['height']/2
    pg.mouse.move(hx,hy); pg.mouse.down()
    for i in range(1,9): pg.mouse.move(hx-bb['width']*0.25*i/8,hy)
    pg.screenshot(path='shot-3-trimming.png')
    pg.mouse.up(); time.sleep(0.3)
    print('dur label after trim',pg.locator('.ve-clip .ve-clip__d').nth(1).inner_text())
    # left handle
    clips=pg.locator('.ve-clip'); bb=clips.nth(1).bounding_box(); hx=bb['x']+3
    pg.mouse.move(hx,hy); pg.mouse.down()
    for i in range(1,9): pg.mouse.move(hx+bb['width']*0.2*i/8,hy)
    pg.mouse.up(); time.sleep(0.3)
    print('dur label after left trim',pg.locator('.ve-clip .ve-clip__d').nth(1).inner_text())
    pg.screenshot(path='shot-4-trimmed.png')
    # click still selects
    pg.locator('.ve-clip').nth(0).click(); time.sleep(0.2)
    print('selected class', pg.locator('.ve-clip--sel .ve-clip__t').inner_text())
    # save (Ctrl+S) and verify server
    pg.keyboard.press('Control+s'); time.sleep(2.5)
    print('server',summary(doc()))
    print('errors',errs[:5])
    b.close()
