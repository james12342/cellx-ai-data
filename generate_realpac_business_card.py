from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs" / "realpac_business_card"
WHATSAPP_QR = OUT / "whatsapp_qr.png"
WECHAT_QR = OUT / "wechat_qr.png"
DPI = 300
W, H = int(3.5 * DPI), int(2 * DPI)

NAVY = "#101B34"
BLUE = "#1F6FEB"
CYAN = "#10B8D9"
RED = "#D71920"
INK = "#172033"
MUTED = "#516079"
LIGHT = "#EEF6FF"
LINE = "#C7D8F2"
WHITE = "#FFFFFF"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def logo_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/georgiab.ttf",
        "C:/Windows/Fonts/timesbd.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


F = {
    "company": font(62, True),
    "name": font(50, True),
    "role": font(30, True),
    "label": font(23, True),
    "body": font(27),
    "small": font(22),
    "service": font(25, True),
    "pill": font(30, True),
    "tagline": font(28, True),
}


def draw_logo(canvas: Image.Image, x: int, y: int, size: int = 70) -> None:
    d = ImageDraw.Draw(canvas)
    r_font = logo_font(int(size * 0.84))
    bbox = d.textbbox((0, 0), "R", font=r_font)
    tx = x + (size - (bbox[2] - bbox[0])) // 2
    ty = y + (size - (bbox[3] - bbox[1])) // 2 - 8
    d.text((tx, ty), "R", font=r_font, fill=RED)


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, fnt: ImageFont.FreeTypeFont, fill: str) -> int:
    draw.text(xy, value, font=fnt, fill=fill)
    bbox = draw.textbbox(xy, value, font=fnt)
    return bbox[3]


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str | None = None, radius: int = 18, width: int = 2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def paste_qr(canvas: Image.Image, path: Path, box: tuple[int, int, int, int]) -> None:
    if not path.exists():
        return
    qr = Image.open(path).convert("RGBA")
    x1, y1, x2, y2 = box
    size = min(x2 - x1, y2 - y1)
    qr = qr.resize((size, size), Image.Resampling.NEAREST)
    canvas.alpha_composite(qr, (x1, y1))


def make_front() -> Image.Image:
    canvas = Image.new("RGBA", (W, H), WHITE)
    draw = ImageDraw.Draw(canvas)

    draw.rectangle((0, 0, 42, H), fill=BLUE)
    draw.rectangle((42, 0, 56, H), fill=CYAN)
    draw.polygon([(W - 220, 0), (W, 0), (W, 150), (W - 130, 95)], fill=LIGHT)
    draw.polygon([(W - 140, H), (W, H), (W, H - 150)], fill="#E1F3FB")

    draw_logo(canvas, 96, 58, 84)
    text(draw, (194, 60), "Realpac, Inc.", F["company"], NAVY)
    draw.line((194, 136, 488, 136), fill=RED, width=5)
    text(draw, (194, 156), "Software, AI & Business Automation", F["tagline"], NAVY)

    text(draw, (96, 248), "James Huang", F["name"], INK)
    text(draw, (98, 312), "CEO", F["role"], BLUE)

    rows = [
        ("PHONE", "(626) 383-3666"),
        ("EMAIL", "workad_009@icloud.com"),
        ("WEB", "www.cellaidata.com"),
    ]
    y = 386
    for label, value in rows:
        text(draw, (98, y), label, F["label"], BLUE)
        text(draw, (208, y - 3), value, F["body"], INK)
        y += 50

    text(draw, (648, 326), "WhatsApp", F["label"], BLUE)
    text(draw, (850, 326), "WeChat", F["label"], BLUE)
    paste_qr(canvas, WHATSAPP_QR, (624, 360, 794, 530))
    paste_qr(canvas, WECHAT_QR, (818, 360, 988, 530))
    return canvas.convert("RGB")


def make_back() -> Image.Image:
    canvas = Image.new("RGBA", (W, H), LIGHT)
    draw = ImageDraw.Draw(canvas)

    draw.rectangle((0, 0, W, 86), fill=BLUE)
    draw_logo(canvas, 74, 14, 60)
    text(draw, (140, 25), "Realpac, Inc.", F["role"], WHITE)
    text(draw, (726, 27), "www.cellaidata.com", F["body"], WHITE)

    text(draw, (76, 122), "What We Build", F["name"], NAVY)
    draw.line((76, 188, 352, 188), fill=RED, width=5)

    services = [
        "Software & hardware integration development",
        "Website and web application development",
        "Mobile app development",
        "Data collection, automation, and analytics",
        "Advertising delivery and campaign automation",
        "AI training and enterprise AI implementation",
    ]

    positions = [
        (76, 226),
        (76, 336),
        (76, 446),
        (414, 226),
        (414, 336),
        (414, 446),
    ]
    for service, (x1, y) in zip(services, positions):
        draw.ellipse((x1, y + 6, x1 + 14, y + 20), fill=BLUE)
        line_y = y
        if service.startswith("AI training"):
            lines = ["AI training & enterprise", "AI implementation"]
        else:
            lines = wrap(service, width=21)
        for line in lines:
            text(draw, (x1 + 28, line_y), line, F["service"], INK)
            line_y += 31

    text(draw, (806, 248), "From idea", F["role"], BLUE)
    text(draw, (806, 292), "to workflow,", F["role"], NAVY)
    text(draw, (806, 336), "From data", F["role"], BLUE)
    text(draw, (806, 380), "to growth.", F["role"], NAVY)
    text(draw, (806, 438), "Build faster", F["service"], INK)
    text(draw, (806, 469), "with AI.", F["service"], INK)

    draw.rectangle((0, H - 22, W, H), fill=CYAN)
    return canvas.convert("RGB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    front = make_front()
    back = make_back()

    front_path = OUT / "realpac_business_card_front.png"
    back_path = OUT / "realpac_business_card_back.png"
    front_2x_path = OUT / "realpac_business_card_front_2x.png"
    back_2x_path = OUT / "realpac_business_card_back_2x.png"
    pdf_path = OUT / "realpac_business_card_print.pdf"

    front.save(front_path, dpi=(DPI, DPI), quality=95)
    back.save(back_path, dpi=(DPI, DPI), quality=95)
    front.resize((W * 2, H * 2), Image.LANCZOS).save(front_2x_path, dpi=(DPI * 2, DPI * 2), quality=95)
    back.resize((W * 2, H * 2), Image.LANCZOS).save(back_2x_path, dpi=(DPI * 2, DPI * 2), quality=95)
    front.save(pdf_path, "PDF", resolution=DPI, save_all=True, append_images=[back])

    print(front_path.resolve())
    print(back_path.resolve())
    print(front_2x_path.resolve())
    print(back_2x_path.resolve())
    print(pdf_path.resolve())


if __name__ == "__main__":
    main()
