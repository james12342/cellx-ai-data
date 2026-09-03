from pathlib import Path
import math
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path.home() / ".codex" / "generated_images" / "01a05971-3007-7452-9982-d4e78e23eb17" / "call_2Oc4383kiTS9Lp69iZQkdxaL.png"
OUT_DIR = ROOT / "outputs" / "dog_ad_video"
FRAMES = OUT_DIR / "frames"
VIDEO = OUT_DIR / "dog_ad_20s.mp4"

WIDTH = 1280
HEIGHT = 720
FPS = 30
DURATION = 20
TOTAL_FRAMES = FPS * DURATION


def font(size, bold=False):
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


TITLE = font(58, True)
SUBTITLE = font(30, False)
SMALL = font(24, False)
BRAND = font(26, True)

SCENES = [
    (0, 5, "每一次奔跑", "都是它说爱你的方式"),
    (5, 10, "天然营养", "给毛孩子更亮的眼睛和更快乐的尾巴"),
    (10, 15, "活力陪伴", "从清晨散步到夜晚回家，都安心"),
    (15, 20, "PawJoy 宠物关爱", "让每一天，都有它的笑脸"),
]


def cover_crop(img, width, height):
    scale = max(width / img.width, height / img.height)
    new_size = (math.ceil(img.width * scale), math.ceil(img.height * scale))
    resized = img.resize(new_size, Image.Resampling.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def draw_centered(draw, text, y, font_obj, fill):
    bbox = draw.textbbox((0, 0), text, font=font_obj)
    x = (WIDTH - (bbox[2] - bbox[0])) // 2
    draw.text((x, y), text, font=font_obj, fill=fill)


def rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def frame_at(base, index):
    t = index / FPS
    progress = index / max(1, TOTAL_FRAMES - 1)
    zoom = 1.0 + 0.085 * progress
    crop_w = int(WIDTH / zoom)
    crop_h = int(HEIGHT / zoom)
    cx = WIDTH // 2 + int(26 * math.sin(progress * math.pi * 1.3))
    cy = HEIGHT // 2 + int(12 * math.sin(progress * math.pi * 0.8))
    left = max(0, min(WIDTH - crop_w, cx - crop_w // 2))
    top = max(0, min(HEIGHT - crop_h, cy - crop_h // 2))
    img = base.crop((left, top, left + crop_w, top + crop_h)).resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0, 0, WIDTH, HEIGHT), fill=(0, 0, 0, 34))
    draw.rectangle((0, int(HEIGHT * 0.52), WIDTH, HEIGHT), fill=(0, 0, 0, 88))

    scene = SCENES[-1]
    for item in SCENES:
        if item[0] <= t < item[1]:
            scene = item
            break
    local = min(1, max(0, (t - scene[0]) / max(0.01, scene[1] - scene[0])))
    fade = min(1, local * 2.7, (1 - local) * 3.2 if scene[1] < DURATION else 1)
    alpha = int(255 * max(0.18, fade))

    rounded_rect(draw, (56, 48, 232, 92), 18, fill=(255, 255, 255, 210))
    draw.text((78, 58), "PawJoy", font=BRAND, fill=(20, 67, 55, 255))

    draw_centered(draw, scene[2], 450, TITLE, (255, 255, 255, alpha))
    draw_centered(draw, scene[3], 528, SUBTITLE, (238, 255, 247, alpha))

    if t >= 15:
        pulse = int(10 * math.sin((t - 15) * math.pi * 2))
        rounded_rect(draw, (492 - pulse, 604, 788 + pulse, 658), 26, fill=(25, 167, 111, 235))
        draw_centered(draw, "立即了解更多", 616, SMALL, (255, 255, 255, 255))

    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def main():
    if not SOURCE.exists():
        raise SystemExit(f"Missing source image: {SOURCE}")
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    base = cover_crop(Image.open(SOURCE).convert("RGB"), WIDTH, HEIGHT).filter(ImageFilter.UnsharpMask(radius=1, percent=105))
    for index in range(TOTAL_FRAMES):
        frame_at(base, index).save(FRAMES / f"frame_{index:04d}.jpg", quality=92)

    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(FPS),
        "-i",
        str(FRAMES / "frame_%04d.jpg"),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(VIDEO),
    ]
    subprocess.run(cmd, check=True)
    print(VIDEO)


if __name__ == "__main__":
    main()
