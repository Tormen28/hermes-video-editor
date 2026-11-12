import os, math, sys
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, DUR = 1280, 720, 30, 39.0
OUT = os.path.dirname(os.path.abspath(__file__))
FR = os.path.join(OUT, "frames")
os.makedirs(FR, exist_ok=True)

BG = (10, 14, 20)
BG2 = (16, 22, 31)
WHITE = (245, 247, 250)
MUTED = (139, 147, 167)
AMBER = (242, 179, 61)
TEAL = (63, 208, 201)
LINE = (36, 45, 60)

F = "C:/Windows/Fonts/"
def font(name, size):
    for cand in (F + name, F + "segoeui.ttf", F + "arial.ttf"):
        if os.path.exists(cand):
            try: return ImageFont.truetype(cand, size)
            except Exception: pass
    return ImageFont.load_default()

f_kick  = font("segoeuib.ttf", 18)
f_h1    = font("segoeuib.ttf", 74)
f_h2    = font("segoeuib.ttf", 52)
f_sub   = font("segoeui.ttf", 26)
f_bul   = font("segoeui.ttf", 27)
f_num   = font("segoeuib.ttf", 20)
f_foot  = font("consola.ttf", 19)
f_small = font("segoeui.ttf", 20)

SCENES = [
    (0.0, 5.2, "title"),
    (5.2, 13.2, "bot"),
    (13.2, 21.2, "argos"),
    (21.2, 29.2, "video"),
    (29.2, 34.0, "loop"),
    (34.0, 39.0, "cta"),
]

def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3

def bg(d):
    # vertical gradient + soft glow
    for y in range(0, H, 4):
        k = y / H
        c = tuple(int(BG[i] + (BG2[i] - BG[i]) * k) for i in range(3))
        d.rectangle([0, y, W, y + 4], fill=c)
    for r in range(420, 0, -8):
        a = int(10 * (1 - r / 420))
        d.ellipse([W - 380 - r, -200 - r // 3, W - 380 + r, -200 + r // 3],
                  outline=(60, 80, 110, a))

def text_w(fnt, s):
    b = fnt.getbbox(s)
    return b[2] - b[0]

def center(d, s, fnt, y, color, alpha=255):
    x = (W - text_w(fnt, s)) / 2
    d.text((x, y), s, font=fnt, fill=color + (alpha,) if len(color) == 3 else color)

def draw_scene(idx, name, t_local, t_total):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img, "RGBA")
    bg(d)
    # scene fade
    fade = min(ease_out(t_local / 0.5), ease_out((SCENES[idx][1] - t_total) / 0.5))
    a = int(255 * fade)
    rise = int(26 * (1 - ease_out(t_local / 0.7)))

    # frame furniture
    d.rectangle([64, 56, 64 + int(56 * ease_out(t_local / 0.8)), 60], fill=AMBER + (a,))

    if name == "title":
        center(d, "HERMES  ·  LOCAL PLUGINS", f_kick, 128 + rise, AMBER, a)
        center(d, "Talk. Build. Edit.", f_h1, 210 + rise, WHITE, a)
        center(d, "Three plugins. One machine. Nothing leaves it.", f_sub, 330 + rise, MUTED, a)
        # three chips
        chips = [("BOT CHAT", TEAL), ("GODOT", AMBER), ("VIDEO", TEAL)]
        total = sum(text_w(f_num, c[0]) + 56 for c in chips) + 40
        x = (W - total) / 2
        for label, col in chips:
            w = text_w(f_num, label) + 56
            d.rounded_rectangle([x, 430, x + w, 478], radius=24, outline=col + (int(a * 0.8),), width=2)
            d.text((x + 28, 440), label, font=f_num, fill=col + (a,))
            x += w + 20

    elif name == "bot":
        center(d, "01  —  BOT CHAT", f_kick, 110 + rise, TEAL, a)
        center(d, "A conversation you can trust", f_h2, 168 + rise, WHITE, a)
        bullets = ["Short, focused answers — no wall of reasoning",
                   "Guard blocks secrets, deletes and risky pushes",
                   "Presets: strict · default · relaxed"]
        y = 300
        for b in bullets:
            d.ellipse([300, y + 12, 312, y + 24], fill=TEAL + (a,))
            d.text((334, y), b, font=f_bul, fill=WHITE + (int(a * 0.92),))
            y += 58
        d.text((300, 520), "It only blocks. It never approves.", font=f_sub, fill=AMBER + (a,))
        d.text((300, 610), "hermes-bot-chat-agent  ·  0.2.0  ·  MIT", font=f_foot, fill=MUTED + (a,))

    elif name == "argos":
        center(d, "02  —  ARGOS", f_kick, 110 + rise, AMBER, a)
        center(d, "Hands on a live Godot editor", f_h2, 168 + rise, WHITE, a)
        bullets = ["27 MCP tools, real editor undo",
                   "Scene tree · create nodes · read properties",
                   "Play, stop, screenshot, iterate"]
        y = 300
        for b in bullets:
            d.ellipse([300, y + 12, 312, y + 24], fill=AMBER + (a,))
            d.text((334, y), b, font=f_bul, fill=WHITE + (int(a * 0.92),))
            y += 58
        d.text((300, 520), "The agent stops describing and starts building.", font=f_sub, fill=TEAL + (a,))
        d.text((300, 610), "argos  ·  1.1.0  ·  MIT", font=f_foot, fill=MUTED + (a,))

    elif name == "video":
        center(d, "03  —  VIDEO EDITOR", f_kick, 110 + rise, TEAL, a)
        center(d, "Cut real video. Locally.", f_h2, 168 + rise, WHITE, a)
        bullets = ["Timeline, text, colour, speed, transitions",
                   "One pass, no cloud, no uploads",
                   "MP4 exported by local FFmpeg"]
        y = 300
        for b in bullets:
            d.ellipse([300, y + 12, 312, y + 24], fill=TEAL + (a,))
            d.text((334, y), b, font=f_bul, fill=WHITE + (int(a * 0.92),))
            y += 58
        d.text((300, 520), "A pane inside Hermes — not another app.", font=f_sub, fill=AMBER + (a,))
        d.text((300, 610), "hermes-video-editor  ·  0.3.4  ·  MIT", font=f_foot, fill=MUTED + (a,))

    elif name == "loop":
        center(d, "ONE LOOP", f_kick, 150 + rise, AMBER, a)
        center(d, "It talks. It builds.", f_h1, 214 + rise, WHITE, a)
        center(d, "It ships the video.", f_h1, 300 + rise, WHITE, a)
        center(d, "All local. No cloud. MIT.", f_sub, 430 + rise, TEAL, a)

    elif name == "cta":
        center(d, "ALL THREE, OPEN SOURCE", f_kick, 186 + rise, TEAL, a)
        center(d, "github.com/Tormen28", f_h1, 240 + rise, WHITE, a)
        center(d, "hermes-bot-chat-agent  ·  argos  ·  hermes-video-editor", f_small, 356 + rise, MUTED, a)
        center(d, "Built with Hermes", f_kick, 470, AMBER, a)

    # progress bar
    p = t_total / DUR
    d.rectangle([0, H - 5, W, H], fill=(24, 30, 40))
    d.rectangle([0, H - 5, int(W * p), H], fill=AMBER)

    img.save(os.path.join(FR, f"f{int(round(t_total * FPS)):05d}.png"), "PNG")

n = int(DUR * FPS)
for i in range(n):
    t = i / FPS
    for idx, (s, e, name) in enumerate(SCENES):
        if s <= t < e:
            draw_scene(idx, name, t - s, t)
            break
print("frames:", n, "->", FR)
