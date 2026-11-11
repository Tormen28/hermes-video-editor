import sys, json, time
sys.path.insert(0, r"C:\Users\EgtYP\AppData\Local\hermes\fleet-workspace\video-editor\core\scripts")
import os
os.environ["VE_TOKEN_FILE"]=r"C:\Users\EgtYP\hermes-work\editor-audit\smoke\service.token"
from ve_client import call
from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:8791"
tok=open(os.environ["VE_TOKEN_FILE"]).read().strip()
# project with two real clips
s,p=call(BASE,"POST","/projects",{"title":"Prueba manual"}); pid=p["projectId"]
for c in ("clips/clipA.mp4","clips/clipB.mp4"):
    s,r=call(BASE,"POST",f"/projects/{pid}/media",{"path":c}); assert s==201,(s,r)
print("project",pid)
with sync_playwright() as pw:
    b=pw.chromium.launch(channel="msedge",headless=True)
    pg=b.new_page(viewport={"width":1500,"height":900})
    pg.add_init_script(f"window.__VE_TOKEN__='{tok}'")
    logs=[]
    pg.on("console",lambda m: logs.append(m.type+": "+m.text[:200]))
    pg.on("pageerror",lambda e: logs.append("PAGEERROR "+str(e)[:300]))
    pg.goto(f"http://127.0.0.1:8800/harness/index.html?svc={BASE}&open={pid}")
    time.sleep(4)
    pg.screenshot(path="pane1.png")
    btns=pg.eval_on_selector_all("button,[role=button],input,select,textarea","els=>els.map(e=>(e.tagName+'|'+(e.getAttribute('aria-label')||'')+'|'+(e.title||'')+'|'+(e.innerText||e.value||'').slice(0,40)).replace(/\\n/g,' '))")
    print("\n".join(btns[:120]))
    print("\n".join(logs[:20]))
    b.close()