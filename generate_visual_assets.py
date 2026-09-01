from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = Path("outputs/business_plan_20260831/visuals")
OUT.mkdir(parents=True, exist_ok=True)


W, H = 1600, 900
BLUE = (31, 111, 235)
NAVY = (20, 33, 61)
CYAN = (16, 184, 217)
GREEN = (22, 163, 74)
ORANGE = (245, 158, 11)
PURPLE = (124, 58, 237)
BG = (239, 247, 255)
INK = (17, 24, 39)
MUTED = (82, 98, 118)
WHITE = (255, 255, 255)
LINE = (197, 216, 242)


def font(size, bold=False):
    names = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def rounded(draw, xy, r, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)


def logo(draw, x, y, scale=1.0):
    pts1 = [(x+0*scale,y+36*scale),(x+36*scale,y),(x+96*scale,y+60*scale),(x+60*scale,y+96*scale)]
    pts2 = [(x+38*scale,y+74*scale),(x+96*scale,y+16*scale),(x+60*scale,y-20*scale),(x+2*scale,y+38*scale)]
    pts3 = [(x+112*scale,y+12*scale),(x+154*scale,y-28*scale),(x+226*scale,y-28*scale),(x+226*scale,y+8*scale),(x+160*scale,y+8*scale),(x+130*scale,y+42*scale)]
    pts4 = [(x+112*scale,y+82*scale),(x+154*scale,y+122*scale),(x+226*scale,y+122*scale),(x+226*scale,y+86*scale),(x+160*scale,y+86*scale),(x+130*scale,y+52*scale)]
    pts5 = [(x+228*scale,y+48*scale),(x+264*scale,y+12*scale),(x+300*scale,y+48*scale),(x+264*scale,y+84*scale)]
    draw.polygon(pts1, fill=(63, 102, 181))
    draw.polygon(pts2, fill=(63, 102, 181))
    draw.polygon(pts3, fill=CYAN)
    draw.polygon(pts4, fill=CYAN)
    draw.polygon(pts5, fill=(63, 102, 181))


def shadow_card(base, xy, r=18):
    layer = Image.new("RGBA", base.size, (0,0,0,0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(xy, r, fill=(15, 23, 42, 34))
    layer = layer.filter(ImageFilter.GaussianBlur(12))
    base.alpha_composite(layer)
    d = ImageDraw.Draw(base)
    d.rounded_rectangle(xy, r, fill=WHITE + (255,), outline=LINE + (255,), width=2)
    return d


def save(img, name):
    img.convert("RGB").save(OUT / name, quality=95)


def hero():
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    for cx, cy, color in [(1320, 120, CYAN), (1120, 760, BLUE), (220, 740, (191, 219, 254))]:
        orb = Image.new("RGBA", (420, 420), (0,0,0,0))
        od = ImageDraw.Draw(orb)
        od.ellipse((40,40,380,380), fill=color+(40,))
        orb = orb.filter(ImageFilter.GaussianBlur(24))
        img.alpha_composite(orb, (cx-210, cy-210))
    logo(d, 78, 70, 0.42)
    d.text((80, 210), "CellX RDP", fill=NAVY, font=font(76, True))
    d.text((82, 312), "Build data apps, AI workflows, and integrations\nwithout touching the core backend.", fill=MUTED, font=font(34))
    d.rounded_rectangle((84, 455, 330, 522), 16, fill=BLUE)
    d.text((124, 472), "Start free trial", fill=WHITE, font=font(27, True))
    d.rounded_rectangle((356, 455, 630, 522), 16, fill=(255,255,255), outline=(178,204,245), width=2)
    d.text((398, 472), "Design AI Workflow", fill=BLUE, font=font(27, True))
    shadow_card(img, (900, 170, 1480, 695), 24)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((900,170,1480,218), 24, fill=NAVY)
    d.rectangle((900,194,1480,218), fill=NAVY)
    d.text((932,184), "Runtime Workflow Builder", fill=WHITE, font=font(24, True))
    node_specs = [
        ("TRIGGER", "Order Created", BLUE, 950, 285),
        ("AI", "GPT Handoff", PURPLE, 1190, 285),
        ("CARRIER", "UPS / FedEx Rate", (8,145,178), 950, 455),
        ("ACTION", "Update CellX", GREEN, 1190, 455),
    ]
    for kind, label, color, x, y in node_specs:
        d.rounded_rectangle((x,y,x+210,y+92), 8, fill=WHITE, outline=(180,205,235), width=2)
        d.rectangle((x,y,x+210,y+28), fill=color)
        d.text((x+14,y+5), kind, fill=WHITE, font=font(15, True))
        d.text((x+14,y+43), label, fill=INK, font=font(22, True))
    d.line((1160,331,1190,331), fill=(100,116,139), width=5)
    d.line((1055,377,1055,455), fill=(100,116,139), width=5)
    d.line((1160,501,1190,501), fill=(100,116,139), width=5)
    save(img, "cellx_hero_ad.png")


def architecture():
    img = Image.new("RGBA", (W, H), (245, 249, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((70, 58), "CellX Extension Architecture", fill=NAVY, font=font(54, True))
    d.text((72, 126), "A sidecar workflow layer expands the deployed backend without disrupting the core system.", fill=MUTED, font=font(27))
    cols = [
        ("Public entry", ["cellaidata.com", "Pricing", "Trial / demo", "Workflow ad"], BLUE),
        ("CellX backend", ["app.cellaidata.com", "Admin pages", "Orders + DB", "Permissions"], NAVY),
        ("Workflow sidecar", ["/workflow/", "/ext-api", "Connectors", "AI handoff"], PURPLE),
        ("External systems", ["Amazon SP-API", "FedEx / UPS", "Stripe / PayPal", "OpenAI / ChatGPT"], CYAN),
    ]
    for i, (name, items, color) in enumerate(cols):
        x = 80 + i * 375
        shadow_card(img, (x, 260, x+305, 660), 24)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((x,260,x+305,318), 24, fill=color)
        d.rectangle((x,292,x+305,318), fill=color)
        d.text((x+28, 276), name, fill=WHITE, font=font(25, True))
        for j, item in enumerate(items):
            d.ellipse((x+30, 365+j*58, x+44, 379+j*58), fill=color)
            d.text((x+60, 354+j*58), item, fill=INK, font=font(25))
        if i < 3:
            d.line((x+305,460,x+375,460), fill=(100,116,139), width=5)
            d.polygon([(x+375,460),(x+350,445),(x+350,475)], fill=(100,116,139))
    save(img, "cellx_architecture.png")


def market():
    img = Image.new("RGBA", (W, H), BG+(255,))
    d = ImageDraw.Draw(img)
    d.text((70, 58), "Market Timing", fill=NAVY, font=font(58, True))
    d.text((72, 128), "Low-code, automation, and agentic AI are converging into one buyer need.", fill=MUTED, font=font(27))
    stats = [
        ("$58.2B", "Gartner projected low-code\ntechnology market by 2029", BLUE),
        ("$50B", "Forrester AI-fueled low-code /\nDPA upside scenario by 2028", PURPLE),
        ("85%", "Deloitte: companies expecting\nto customize AI agents", GREEN),
    ]
    for i, (big, small, color) in enumerate(stats):
        x = 110 + i*470
        shadow_card(img, (x, 280, x+390, 560), 28)
        d = ImageDraw.Draw(img)
        d.text((x+42, 330), big, fill=color, font=font(64, True))
        d.text((x+42, 430), small, fill=MUTED, font=font(26))
    d.text((110, 690), "CellX = generated data apps + governed workflow + flexible AI.", fill=NAVY, font=font(34, True))
    save(img, "cellx_market_ad.png")


def workflow_ad():
    img = Image.new("RGBA", (W, H), (242, 248, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((70, 58), "From manual work to reusable AI skills", fill=NAVY, font=font(54, True))
    d.text((72, 126), "Drag apps, database actions, conditions, and AI handoffs into one operational workflow.", fill=MUTED, font=font(27))
    steps = [("Amazon\nBestsellers", BLUE), ("SKU + Price\nLookup", NAVY), ("Export\nExcel", GREEN), ("ChatGPT\nHandoff", PURPLE), ("Email\nResult", ORANGE)]
    for i, (label, color) in enumerate(steps):
        x = 110 + i*285
        d.rounded_rectangle((x,330,x+220,470), 22, fill=WHITE, outline=LINE, width=3)
        d.rounded_rectangle((x,330,x+220,370), 22, fill=color)
        d.rectangle((x,350,x+220,370), fill=color)
        d.text((x+28, 395), label, fill=INK, font=font(28, True))
        if i < len(steps)-1:
            d.line((x+220,400,x+285,400), fill=(100,116,139), width=6)
            d.polygon([(x+285,400),(x+260,383),(x+260,417)], fill=(100,116,139))
    d.rounded_rectangle((220, 625, 1380, 710), 24, fill=(255,255,255), outline=(178,204,245), width=2)
    d.text((260, 650), "Manual ChatGPT handoff avoids platform token cost and keeps human review.", fill=NAVY, font=font(30, True))
    save(img, "cellx_workflow_ad.png")


hero()
architecture()
market()
workflow_ad()
print(OUT.resolve())
