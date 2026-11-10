"""Prueba de arrastre/edición del pane en el banco de pruebas (Playwright + Chrome).
Variables: VE_PID (proyecto con 3 escenas), VE_SVC (servicio), VE_HARNESS (servidor estático de plugin/).
No corre en el CI normal: necesita playwright y un navegador."""
import json, time, urllib.request as u, subprocess
from playwright.sync_api import sync_playwright
import os
HARNESS=os.environ.get('VE_HARNESS','http://127.0.0.1:8795')
pid=os.environ['VE_PID']; SVC=os.environ.get('VE_SVC','http://127.0.0.1:8780')
def get(p): return json.loads(u.urlopen(SVC+p).read())
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--no-sandbox'])
    pg=b.new_page(viewport={'width':1280,'height':800})
    errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)))
    pg.goto(f"{HARNESS}/harness/index.html?svc={SVC}&open={pid}"); pg.wait_for_selector('.ve-clip')
    # text on scene 1
    pg.locator('.ve-clip').nth(0).click()
    ta=pg.locator('textarea').first; ta.fill('Hola Hermes Bots'); time.sleep(0.3)
    # volume slider of scene
    sl=pg.locator('input[type=range]').first
    print('range count',pg.locator('input[type=range]').count(), [pg.locator('input[type=range]').nth(i).get_attribute('aria-label') for i in range(pg.locator('input[type=range]').count())])
    pg.get_by_label('Volumen de la escena').fill('40'); time.sleep(0.3)
    pg.screenshot(path='e2e-1.png')
    # find volume range via label
    vol=pg.get_by_role('slider').filter(has_text='').first
    pg.keyboard.press('Control+s'); time.sleep(2)
    d=get(f'/projects/{pid}')['project']; print('server vol',[s['audio']['volume'] for s in d['scenes']][:1], 'rev',get(f'/projects/{pid}')['revision'])
    # export
    btn=pg.get_by_role('button',name='Exportar')
    print('export btns',btn.count(), btn.first.is_enabled())
    btn.first.click(); time.sleep(0.8)
    pg.get_by_role('dialog').get_by_role('button',name='Exportar').click(); time.sleep(1)
    pg.screenshot(path='e2e-2.png')
    deadline=time.time()+120; job=None
    while time.time()<deadline:
        jobs=get('/jobs'); lst=jobs.get('jobs') if isinstance(jobs,dict) else jobs
        job=lst[0] if lst else None
        if job and job.get('state') in ('succeeded','failed','cancelled'): break
        time.sleep(1)
    print('job',{k:job.get(k) for k in ('jobId','state','stage','error','bytes')})
    time.sleep(1.5); pg.screenshot(path='e2e-3.png')
    if job and job['state']=='succeeded':
        out=u.urlopen(SVC+f"/jobs/{job['jobId']}/output").read(); open('out.mp4','wb').write(out)
        print(subprocess.run(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_name,width,height','-of','csv=p=0','out.mp4'],capture_output=True,text=True).stdout)
    print('errs',errs)
    b.close()
