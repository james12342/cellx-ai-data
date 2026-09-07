from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs" / "marketing_video"
PITCH = ROOT / "outputs" / "business_plan_20260831"
VIS = PITCH / "visuals"
LOGO = ROOT / "rdp-marketing-site" / "assets" / "logo.png"

W, H = 1920, 1080
BG = "#EEF6FF"
NAVY = "#14213D"
BLUE = "#1F6FEB"
CYAN = "#10B8D9"
GREEN = "#16A34A"
ORANGE = "#F59E0B"
PURPLE = "#7C3AED"
MUTED = "#526276"
WHITE = "#FFFFFF"
LINE = "#C7D8F2"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for candidate in candidates:
        p = Path(candidate)
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


F = {
    "brand": font(30, True),
    "kicker": font(30, True),
    "hero": font(76, True),
    "title": font(58, True),
    "subtitle": font(34),
    "body": font(30),
    "small": font(24),
    "tiny": font(20),
}


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for word in words:
        test = f"{cur} {word}".strip()
        if draw.textbbox((0, 0), test, font=fnt)[2] <= width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, fnt: ImageFont.FreeTypeFont, fill: str, width: int | None = None, spacing: int = 10):
    x, y = xy
    lines = value.split("\n") if width is None else wrap_text(draw, value, fnt, width)
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        bbox = draw.textbbox((x, y), line, font=fnt)
        y += bbox[3] - bbox[1] + spacing
    return y


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str = LINE, radius: int = 22, width: int = 3):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def paste_contain(canvas: Image.Image, src_path: Path, box: tuple[int, int, int, int], bg: str | None = WHITE):
    src = Image.open(src_path).convert("RGBA")
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    scale = min(bw / src.width, bh / src.height)
    nw, nh = int(src.width * scale), int(src.height * scale)
    src = src.resize((nw, nh), Image.LANCZOS)
    layer = Image.new("RGBA", (bw, bh), bg or (0, 0, 0, 0))
    layer.alpha_composite(src, ((bw - nw) // 2, (bh - nh) // 2))
    canvas.alpha_composite(layer, (x1, y1))


def brand(draw: ImageDraw.ImageDraw, canvas: Image.Image):
    if LOGO.exists():
        logo = Image.open(LOGO).convert("RGBA")
        logo.thumbnail((64, 64), Image.LANCZOS)
        canvas.alpha_composite(logo, (86, 56))
    text(draw, (164, 67), "Cell AI Data", F["brand"], NAVY)
    draw.rounded_rectangle((1600, 54, 1784, 104), radius=25, fill=BLUE)
    text(draw, (1640, 66), "AI Workflow", F["small"], WHITE)


def add_footer(draw: ImageDraw.ImageDraw, seconds: str):
    text(draw, (88, 1000), seconds, F["tiny"], "#94A3B8")
    text(draw, (1476, 1000), "cellaidata.com", F["tiny"], "#527083")


def make_scene(idx: int, spec: dict) -> Path:
    canvas = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    brand(draw, canvas)

    text(draw, (88, 170), spec["kicker"], F["kicker"], spec.get("color", BLUE))
    title_font = spec.get("title_font", F["hero"] if spec.get("hero") else F["title"])
    title_end = text(draw, (88, 226), spec["title"], title_font, NAVY, width=760)
    body_y = max(365, title_end + 20)
    text(draw, (92, body_y), spec["body"], F["subtitle"], MUTED, width=730, spacing=14)

    if "image" in spec:
        rounded(draw, (860, 190, 1800, 790), WHITE, LINE, 24)
        paste_contain(canvas, Path(spec["image"]), (884, 214, 1776, 766), WHITE)
    elif "bullets" in spec:
        x, y = 900, 250
        for i, (label, desc, color) in enumerate(spec["bullets"]):
            yy = y + i * 160
            draw.ellipse((x, yy, x + 70, yy + 70), fill=color)
            text(draw, (x + 26, yy + 17), str(i + 1), F["small"], WHITE)
            text(draw, (x + 96, yy - 2), label, F["subtitle"], NAVY)
            text(draw, (x + 96, yy + 52), desc, F["small"], MUTED, width=610)

    if "bottom" in spec:
        rounded(draw, (150, 860, 1770, 948), "#EAF3FF", "#BFD3F3", 26)
        text(draw, (205, 888), spec["bottom"], F["subtitle"], BLUE, width=1510)

    add_footer(draw, spec.get("time", ""))
    path = OUT / f"scene_{idx:02d}.png"
    canvas.convert("RGB").save(path, quality=95)
    return path


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    scenes = [
        {
            "kicker": "PRODUCT MARKETING",
            "title": "Build workflows that save time and earn more",
            "body": "Cell AI Data helps teams turn repetitive work into visual AI workflows, reusable templates, and sellable business assets.",
            "image": PITCH / "slide-01.png",
            "bottom": "Big Save. Big Fast. Big Flexible. And Even More Earn.",
            "hero": True,
            "time": "0:00-0:06",
        },
        {
            "kicker": "THE PAIN",
            "title": "Manual work slows every small business",
            "body": "Teams copy data between websites, spreadsheets, email, CRM, and internal systems. AI can help, but it needs workflow context.",
            "bullets": [
                ("Disconnected tools", "Useful data sits in too many places.", BLUE),
                ("Slow custom software", "Traditional development takes too long.", ORANGE),
                ("AI without action", "Answers still need to become work.", PURPLE),
            ],
            "time": "0:06-0:12",
        },
        {
            "kicker": "WORKFLOW DEMO",
            "title": "Drag, connect, test, and run",
            "body": "Users build a process visually with script nodes, AI nodes, CellX database nodes, transform steps, and Gmail delivery.",
            "image": PITCH / "slide-05.png",
            "bottom": "A real demo runs from listings to AI analysis to client email.",
            "time": "0:12-0:18",
        },
        {
            "kicker": "AI ANALYSIS",
            "title": "OpenAI turns raw listings into recommendations",
            "body": "The workflow sends a small, controlled dataset to the model, then returns strengths, concerns, scores, and customer-ready summaries.",
            "image": PITCH / "slide-08.png",
            "time": "0:18-0:24",
        },
        {
            "kicker": "CELLX DATABASE",
            "title": "Results become reusable business data",
            "body": "The same workflow writes structured rows into CellX tables so teams can search, update, export, and reuse the output later.",
            "image": PITCH / "slide-04.png",
            "bottom": "AI output becomes operational data, not a one-time chat answer.",
            "time": "0:24-0:30",
        },
        {
            "kicker": "CUSTOMER EMAIL",
            "title": "Personalized recommendations go to each client",
            "body": "Cell AI Data can query client records, merge names and emails, and send personalized Gmail messages with audit logging.",
            "bullets": [
                ("Fetch client rows", "Read customer names and email addresses.", GREEN),
                ("Merge recommendation", "Use AI output as email content.", PURPLE),
                ("Send and log", "Deliver through Gmail and keep history.", ORANGE),
            ],
            "time": "0:30-0:36",
        },
        {
            "kicker": "MARKETPLACE",
            "title": "Customers can sell mature workflows",
            "body": "A realtor, e-commerce operator, or agency can package a proven workflow as a template. Other users can buy, import, and customize it.",
            "image": PITCH / "slide-06.png",
            "bottom": "The platform takes commission while creators earn from reusable expertise.",
            "time": "0:36-0:42",
        },
        {
            "kicker": "BUSINESS MODEL",
            "title": "Four ways to monetize",
            "body": "Subscriptions, setup services, premium templates, and marketplace commission turn one workflow product into a platform business.",
            "image": PITCH / "slide-09.png",
            "time": "0:42-0:48",
        },
        {
            "kicker": "MVP STATUS",
            "title": "Already deployed, already demoable",
            "body": "The project includes a public site, AWS deployment, workflow tabs, template browsing, marketplace preview, node testing, and live integrations.",
            "image": PITCH / "slide-10.png",
            "bottom": "Built for real customer pilots, not just a mockup.",
            "time": "0:48-0:54",
        },
        {
            "kicker": "CALL TO ACTION",
            "title": "Turn one operator into an AI-augmented team",
            "body": "Start with a painful workflow. Prove ROI. Package the repeatable process. Scale through templates and marketplace distribution.",
            "image": PITCH / "slide-13.png",
            "bottom": "Visit cellaidata.com and try the workflow demo.",
            "title_font": font(66, True),
            "time": "0:54-1:00",
        },
    ]

    image_paths = [make_scene(i + 1, scene) for i, scene in enumerate(scenes)]
    concat = OUT / "cell_ai_data_marketing_video_concat.txt"
    with concat.open("w", encoding="utf-8") as f:
        for image_path in image_paths:
            f.write(f"file '{image_path.as_posix()}'\n")
            f.write("duration 6\n")
        f.write(f"file '{image_paths[-1].as_posix()}'\n")

    output = OUT / "cell_ai_data_workflow_marketplace_marketing_60s.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat),
        "-t",
        "60",
        "-vf",
        "fps=30,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
        str(output),
    ]
    subprocess.run(cmd, check=True)
    print(output.resolve())


if __name__ == "__main__":
    main()
