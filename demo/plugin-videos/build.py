import os, sys
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, DUR = 1280, 720, 30, 29.0
OUT = os.path.dirname(os.path.abspath(__file__))
BG, BG2 = (10, 14, 20), (16, 22, 31)
WHITE, MUTED = (245, 247, 250), (139, 147, 167)
AMBER = (242, 179, 61)
TEAL = (63, 208, 201)
Violet = (167, 139, 250)

F = "C:/Windows/Fonts/"
def font(name, size):
    for c in (F + name, F + "segoeui.ttf"):
        if os.path.exists(c):
            try: return ImageFont.truetype(c, size)
            except Exception: pass
    return ImageFont.load_default()

f_kick = font("segoeuib.ttf", 18); f_h1 = font("segoeuib.ttf", 62)
f_h2 = font("segoeuib.ttf", 46); f_sub = font("segoeui.ttf", 25)
f_bul = font("segoeui.ttf", 27); f_foot = font("consola.ttf", 19)

VIDEOS = {
 "bot": dict(kicker="HERMES BOTS  ·  0.3.0", title="A bot chat that remembers.",
   accent=TEAL,
   bullets=["Short answers — no wall of reasoning",
            "Guard blocks secrets, deletes and risky pushes",
            "Memory: decisions, project state, lessons"],
   proof="Delegations come back to the same chat.",
   foot="hermes-bot-chat-agent  ·  0.3.0  ·  MIT",
   cta="github.com/Tormen28/hermes-bot-chat-agent"),
 "argos": dict(kicker="ARGOS  ·  1.1.0", title="Hands on a live Godot editor.",
   accent=AMBER,
   bullets=["27 MCP tools, real editor undo",
            "Scene tree, node creation, property reads",
            "Play, stop, screenshot, iterate"],
   proof="It builds, runs, looks — then fixes.",
   foot="argos  ·  1.1.0  ·  MIT",
   cta="github.com/Tormen28/argos"),
 "video": dict(kicker="VIDEO EDITOR  ·  0.3.4", title="Cut real video inside Hermes.",
   accent=Violet,
   bullets=["Timeline, text, colour, speed, transitions",
            "One pass — no cloud, no uploads",
            "MP4 exported by local FFmpeg"],
   proof="A pane inside Hermes — not another app.",
   foot="hermes-video-editor  ·  0.3.4  ·  MIT",
   cta="github.com/Tormen28/hermes-video-editor"),
}

SCENES = [(0.0, 5.0, "intro"), (5.0, 13.5, "bullets"), (13.5, 21.0, "proof"), (21.0, 29.0, "cta")]

def ease(t):
    t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 3

def tw(f, s): b = f.getbbox(s); return b[2] - b[0]
def center(d, s, f, y, col, a):
    d.text(((W - tw(f, s)) / 2, y), s, font=f, fill=col + (a,))

def grad(d):
    for y in range(0, H, 4):
        k = y / H
        d.rectangle([0, y, W, y + 4], fill=tuple(int(BG[i] + (BG2[i] - BG[i]) * k) for i in range(3)))

def scene(name, cfg, tl, tt, acc, end):
    img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img, "RGBA"); grad(d)
    a = int(255 * min(ease(tl / 0.45), ease(max(0.0, end - tt) / 0.45)))
    rise = int(24 * (1 - ease(tl / 0.65)))
    d.rectangle([64, 56, 64 + int(56 * ease(tl / 0.8)), 60], fill=acc + (255,))

    if name == "intro":
        center(d, cfg["kicker"], f_kick, 140 + rise, acc, a)
        center(d, cfg["title"], f_h1, 200 + rise, WHITE, a)
        center(d, "Local. Open source. MIT.", f_sub, 300 + rise, MUTED, a)
        w = int(220 * ease(tl / 0.9))
        d.rectangle([(W - w) // 2, 390, (W + w) // 2, 394], fill=acc + (a,))
    elif name == "bullets":
        center(d, "WHAT IT DOES", f_kick, 108 + rise, acc, a)
        y = 190
        for b in cfg["bullets"]:
            d.ellipse([240, y + 12, 252, y + 24], fill=acc + (a,))
            d.text((276, y), b, font=f_bul, fill=WHITE + (int(a * 0.93),))
            y += 78
        d.text((240, 470), cfg["proof"], font=f_sub, fill=acc + (a,))
        d.text((240, 600), cfg["foot"], font=f_foot, fill=MUTED + (a,))
    elif name == "proof":
        center(d, "HOW IT FEELS", f_kick, 150 + rise, acc, a)
        center(d, "You ask. It works. It shows you.", f_h2, 210 + rise, WHITE, a)
        center(d, "No cloud account. No upload. No watermark.", f_sub, 300 + rise, MUTED, a)
        center(d, "Everything runs on your machine.", f_sub, 350 + rise, WHITE, a)
    else:
        center(d, "OPEN SOURCE  ·  MIT", f_kick, 186 + rise, acc, a)
        center(d, cfg["cta"], font("segoeuib.ttf", 44), 240 + rise, WHITE, a)
        center(d, "Built with Hermes", f_kick, 380, AMBER, a)

    d.rectangle([0, H - 5, W, H], fill=(24, 30, 40))
    d.rectangle([0, H - 5, int(W * tt / DUR), H], fill=acc)
    return img

for key, cfg in VIDEOS.items():
    fr = os.path.join(OUT, key, "frames"); os.makedirs(fr, exist_ok=True)
    n = int(DUR * FPS)
    for i in range(n):
        t = i / FPS
        for s, e, nm in SCENES:
            if s <= t < e:
                scene(nm, cfg, t - s, t, cfg["accent"], e).save(
                    os.path.join(fr, f"f{i:05d}.png"), "PNG")
                break
    print(key, "frames:", n)
