import os, math, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS, DUR = 1920, 1080, 30, 36.0
OUT = os.path.dirname(os.path.abspath(__file__))
WHITE, MUTED = (246, 248, 251), (150, 158, 178)
AMBER = (242, 179, 61)
TEAL = (63, 208, 201)
VIOLET = (167, 139, 250)
BG_TOP, BG_BOT = (8, 11, 17), (20, 26, 37)

F = "C:/Windows/Fonts/"
def font(name, size):
    for c in (F + name, F + "segoeui.ttf"):
        if os.path.exists(c):
            try: return ImageFont.truetype(c, size)
            except Exception: pass
    return ImageFont.load_default()

F_KICK = font("segoeuib.ttf", 26); F_H1 = font("segoeuib.ttf", 104)
F_H1s = font("segoeuib.ttf", 84); F_TAG = font("segoeui.ttf", 40)
F_BUL = font("segoeui.ttf", 40); F_MONO = font("consola.ttf", 34)
F_SMALL = font("segoeui.ttf", 30); F_FOOT = font("consola.ttf", 26)
F_NUM = font("segoeuib.ttf", 24)

VIDEOS = {
 "hermes-bots-030": dict(
   num="01", kicker="HERMES PLUGINS", title="Hermes Bots", tag="A bot chat that remembers.",
   accent=TEAL,
   bullets=["Short answers — no wall of reasoning",
            "A guard that blocks secrets, deletes and risky pushes",
            "Memory: decisions, project state, lessons. Local."],
   proof="Delegations come back to the same chat.",
   install="hermes plugins install bot-chat-agent",
   foot="hermes-bot-chat-agent  ·  0.3.0  ·  MIT",
   cta="github.com/Tormen28/hermes-bot-chat-agent"),
 "argos-110": dict(
   num="02", kicker="HERMES PLUGINS", title="ARGOS", tag="Hands on a live Godot editor.",
   accent=AMBER,
   bullets=["27 MCP tools, real editor undo",
            "Scene tree, node creation, property reads",
            "Play, stop, screenshot, iterate"],
   proof="It builds, runs, looks — then fixes.",
   install="hermes plugins install argos",
   foot="argos  ·  1.1.0  ·  MIT",
   cta="github.com/Tormen28/argos"),
 "video-editor-034": dict(
   num="03", kicker="HERMES PLUGINS", title="Video Editor", tag="Cut real video inside Hermes.",
   accent=VIOLET,
   bullets=["Timeline, text, colour, speed, transitions",
            "One pass — no cloud, no uploads",
            "MP4 exported by local FFmpeg"],
   proof="A pane inside Hermes — not another app.",
   install="github.com/Tormen28/hermes-video-editor",
   foot="hermes-video-editor  ·  0.3.4  ·  MIT",
   cta="github.com/Tormen28/hermes-video-editor"),
}

SCENES = [(0.0, 5.5, "intro"), (5.5, 11.5, "what"), (11.5, 19.5, "bullets"),
          (19.5, 26.5, "install"), (26.5, 32.0, "proof"), (32.0, 36.0, "cta")]

def ease(t):
    t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 3

def ease_io(t):
    t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)

# --- precomputed layers -------------------------------------------------
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
grad = (yy / H)[..., None]
BASE = np.array(BG_TOP, np.float32) * (1 - grad) + np.array(BG_BOT, np.float32) * grad
dx = (xx - W / 2) / (W / 2); dy = (yy - H / 2) / (H / 2)
VIGN = np.clip(1 - 0.55 * (dx ** 2 + dy ** 2) / 2, 0.25, 1.0)[..., None]

# rejilla 1/4 para los orbes (mucho más rápido)
yy4, xx4 = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32)
yy4 *= 4; xx4 *= 4

def orb(center, radius, color, strength):
    cx, cy = center
    g = np.exp(-(((xx4 - cx) ** 2 + (yy4 - cy) ** 2) / (2 * radius ** 2))).astype(np.float32)
    g = np.asarray(Image.fromarray((np.clip(g, 0, 1) * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR), np.float32) / 255.0
    return (g * strength)[..., None] * np.array(color, np.float32)

def tw(f, s): b = f.getbbox(s); return b[2] - b[0]
def text_c(d, s, f, y, col, a):
    d.text(((W - tw(f, s)) / 2, y), s, font=f, fill=col + (int(a),))

def wipe(a_img, b_img, k):
    """soft horizontal wipe between two RGBA images"""
    w = W
    m = int(w * k)
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    md.rectangle([0, 0, m, H], fill=255)
    if 0 < m < w:
        md.rectangle([m - 40, 0, m, H], fill=120)
    mask = mask.filter(ImageFilter.GaussianBlur(18))
    out = a_img.copy(); out.paste(b_img, (0, 0), mask)
    return out

def scene_img(name, cfg, tl, end, acc):
    t = tl
    f = lambda x: ease(x)
    a = f(min(t / 0.5, max(0.0, end - (t + (end - SCENES[[s[2] for s in SCENES].index(name)][0]))) / 0.5 + 9) if False else min(t / 0.5, 1))
    # fade in only; out handled by wipe/black at end
    a = ease(t / 0.5)
    rise = int(40 * (1 - ease(t / 0.8)))

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    if name == "intro":
        kick = f"{cfg['kicker']}  ·  {cfg['num']}"
        text_c(d, kick, F_KICK, 300 + rise, acc, 255 * a)
        text_c(d, cfg["title"], F_H1, 350 + rise, WHITE, 255 * a)
        text_c(d, cfg["tag"], F_TAG, 500 + rise, MUTED, 255 * a)
        wdt = int(360 * ease(t / 1.1))
        d.rectangle([(W - wdt) // 2, 610, (W + wdt) // 2, 616], fill=acc + (int(255 * a),))

    elif name == "what":
        text_c(d, "WHAT A PLUGIN IS", F_KICK, 250, acc, 255 * a)
        text_c(d, "A small extension you install by name.", font("segoeuib.ttf", 58), 300, WHITE, 255 * a)
        chips = ["runs inside Hermes", "adds one capability", "remove anytime"]
        total = 3 * 470 + 2 * 40
        x = (W - total) // 2
        for i, c in enumerate(chips):
            k = ease((t - 0.5 - i * 0.18) / 0.6)
            y = 470 + int(20 * (1 - k))
            box = [x, y, x + 470, y + 92]
            d.rounded_rectangle(box, radius=46, outline=acc + (int(200 * k),), width=2)
            fnt = F_SMALL
            d.text((x + (470 - tw(fnt, c)) / 2, y + 28), c, font=fnt, fill=WHITE + (int(240 * k),))
            x += 510

    elif name == "bullets":
        text_c(d, "WHAT IT DOES", F_KICK, 210, acc, 255 * a)
        y = 320
        for i, b in enumerate(cfg["bullets"]):
            k = ease((t - 0.35 - i * 0.22) / 0.6)
            xx0 = 330 + int(50 * (1 - k))
            d.ellipse([xx0, y + 12, xx0 + 14, y + 26], fill=acc + (int(255 * k),))
            d.text((xx0 + 40, y), b, font=F_BUL, fill=WHITE + (int(245 * k),))
            y += 122
        d.text((330, 800), cfg["foot"], font=F_FOOT, fill=MUTED + (int(220 * a),))

    elif name == "install":
        text_c(d, "HOW YOU USE IT", F_KICK, 240, acc, 255 * a)
        # terminal card
        card = [280, 320, W - 280, 620]
        d.rounded_rectangle(card, radius=26, fill=(14, 18, 26, int(230 * a)), outline=(48, 58, 76, int(220 * a)), width=2)
        for i, col in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
            d.ellipse([316 + i * 34, 352, 336 + i * 34, 372], fill=col + (int(230 * a),))
        cmd = cfg["install"]
        n = int(max(0, t - 0.6) * 26)
        shown = cmd[:n]
        d.text((330, 430), "$ " + shown, font=F_MONO, fill=TEAL + (255,))
        if int(t * 3) % 2 == 0:
            cx0 = 330 + tw(F_MONO, "$ " + shown) + 6
            d.rectangle([cx0, 428, cx0 + 16, 474], fill=TEAL + (int(220 * a),))
        text_c(d, "then open  Desktop  →  Plugins", F_SMALL, 660, MUTED, 255 * a)

    elif name == "proof":
        text_c(d, "THE POINT", F_KICK, 330, acc, 255 * a)
        text_c(d, cfg["proof"], F_H1s, 390, WHITE, 255 * a)
        text_c(d, "Local. No cloud account. No upload.", F_TAG, 540, MUTED, 255 * a)

    else:
        text_c(d, "OPEN SOURCE  ·  MIT", F_KICK, 350, acc, 255 * a)
        text_c(d, cfg["cta"], font("segoeuib.ttf", 62), 400, WHITE, 255 * a)
        text_c(d, "Built with Hermes", F_KICK, 540, AMBER, 255 * a)
        text_c(d, cfg["foot"], F_FOOT, 760, MUTED, 210 * a)

    return ov

def compose(cfg, t):
    acc = cfg["accent"]
    # moving lights
    night = BASE.copy()
    p = t / DUR
    night += orb((W * (0.22 + 0.05 * math.sin(p * 5)), H * (0.30 + 0.04 * math.cos(p * 4))), 420, acc, 0.16)
    night += orb((W * (0.80 - 0.05 * math.cos(p * 4)), H * (0.72 + 0.03 * math.sin(p * 6))), 520, AMBER, 0.09)
    night += orb((W * 0.5, H * 1.15), 700, (40, 70, 120), 0.10)
    # light sweep
    ang = -0.35
    dist = (xx * math.cos(ang) + yy * math.sin(ang))
    pos = -600 + ((t * 190) % (DUR * 190))
    band = np.exp(-((dist - pos) ** 2) / (2 * 260.0 ** 2))
    night += (band[..., None] * 0.045 * np.array((255, 250, 240), np.float32))
    night *= VIGN
    img = Image.fromarray(np.clip(night, 0, 255).astype(np.uint8), "RGB").convert("RGBA")

    # scene (with wipe at boundaries)
    idx = max(i for i, s in enumerate(SCENES) if s[0] <= t)
    s0, e0, nm = SCENES[idx]
    cur = scene_img(nm, cfg, t - s0, e0, acc)
    TR = 0.45
    if t - s0 < TR and idx > 0:
        prev = scene_img(SCENES[idx - 1][2], cfg, (t - SCENES[idx - 1][0]), SCENES[idx - 1][1], acc)
        cur = wipe(prev, cur, ease((t - s0) / TR))
    img.alpha_composite(cur)

    # grano suave (mitad de resolución: mismo aspecto, mucho más rápido)
    s = 3
    g = np.random.default_rng().normal(0, 3.2, (H // s, W // s)).astype(np.float32)
    g = np.asarray(Image.fromarray(np.clip(g * 10 + 128, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR), np.float32)
    arr = np.clip(np.asarray(img.convert("RGB"), np.float32) + ((g - 128) / 10)[..., None], 0, 255).astype(np.uint8)
    out = Image.fromarray(arr, "RGB")
    d = ImageDraw.Draw(out)
    d.rectangle([0, H - 6, W, H], fill=(22, 28, 38))
    d.rectangle([0, H - 6, int(W * t / DUR), H], fill=acc)
    return out

only = set(sys.argv[1:])
for key, cfg in VIDEOS.items():
    if only and key not in only:
        continue
    fr = os.path.join(OUT, key, "frames"); os.makedirs(fr, exist_ok=True)
    n = int(DUR * FPS)
    for i in range(n):
        dest = os.path.join(fr, f"f{i:05d}.jpg")
        if os.path.exists(dest):
            continue                      # reanudable: no re-renderiza lo hecho
        compose(cfg, i / FPS).save(dest, "JPEG", quality=92)
    print(key, "ok", n)
