import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


W, H = 1280, 720
FPS = 30


def load_font(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


FONT_TITLE = load_font(54, True)
FONT_SUBTITLE = load_font(28)
FONT_LABEL = load_font(24, True)
FONT_SMALL = load_font(20)


def cover_image(image, scale=1.0, pan_x=0.0, pan_y=0.0):
    img = image.convert("RGB")
    iw, ih = img.size
    base_scale = max(W / iw, H / ih)
    target_w = int(iw * base_scale * scale)
    target_h = int(ih * base_scale * scale)
    resized = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    max_x = max(0, target_w - W)
    max_y = max(0, target_h - H)
    left = int(max_x * (0.5 + pan_x * 0.5))
    top = int(max_y * (0.5 + pan_y * 0.5))
    return resized.crop((left, top, left + W, top + H))


def rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_text_shadow(draw, xy, text, font, fill, shadow=(0, 0, 0, 150), offset=2):
    x, y = xy
    draw.text((x + offset, y + offset), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)


def fit_text(draw, text, font, max_width):
    if draw.textlength(text, font=font) <= max_width:
        return [text]
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:3]


def add_overlay(frame, title=None, subtitle=None, badge=None, stats=None, footer=None, progress=0.0):
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Soft cinematic gradients.
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad_pixels = grad.load()
    for y in range(H):
        top_alpha = max(0, int(110 * (1 - y / 260))) if y < 260 else 0
        bottom_alpha = max(0, int(155 * ((y - 420) / 300))) if y > 420 else 0
        alpha = max(top_alpha, bottom_alpha)
        if alpha:
            for x in range(W):
                grad_pixels[x, y] = (3, 10, 20, alpha)
    overlay.alpha_composite(grad)

    if badge:
        rounded_rect(draw, (46, 42, 260, 80), 10, (255, 255, 255, 220))
        draw.text((62, 51), badge.upper(), font=FONT_SMALL, fill=(13, 38, 66, 255))

    if title:
        lines = fit_text(draw, title, FONT_TITLE, W - 120)
        y = 470 if stats else 500
        for line in lines:
            draw_text_shadow(draw, (54, y), line, FONT_TITLE, (255, 255, 255, 255), offset=3)
            y += 62

    if subtitle:
        lines = fit_text(draw, subtitle, FONT_SUBTITLE, W - 120)
        y = 565 if not stats else 610
        for line in lines:
            draw_text_shadow(draw, (58, y), line, FONT_SUBTITLE, (235, 244, 255, 245), offset=2)
            y += 36

    if stats:
        x = 54
        y = 566
        for label in stats:
            text_w = int(draw.textlength(label, font=FONT_LABEL))
            rounded_rect(draw, (x, y, x + text_w + 34, y + 42), 8, (255, 255, 255, 220))
            draw.text((x + 17, y + 8), label, font=FONT_LABEL, fill=(12, 35, 56, 255))
            x += text_w + 48

    if footer:
        draw.text((54, 674), footer, font=FONT_SMALL, fill=(255, 255, 255, 210))

    bar_w = int((W - 96) * progress)
    draw.rectangle((48, 704, 48 + bar_w, 709), fill=(255, 255, 255, 210))

    composited = Image.alpha_composite(frame.convert("RGBA"), overlay).convert("RGB")
    return composited


def make_scene_frames(image_path, duration, title=None, subtitle=None, badge=None, stats=None, footer=None, direction=1):
    image = Image.open(image_path)
    frame_count = int(duration * FPS)
    frames = []
    for i in range(frame_count):
        t = i / max(1, frame_count - 1)
        ease = 0.5 - 0.5 * math.cos(math.pi * t)
        scale = 1.02 + 0.055 * ease
        pan_x = direction * (ease - 0.5) * 0.36
        pan_y = -direction * (ease - 0.5) * 0.16
        frame = cover_image(image, scale=scale, pan_x=pan_x, pan_y=pan_y)
        scene_progress = t
        frame = add_overlay(frame, title, subtitle, badge, stats, footer, scene_progress)

        # Fade in/out for smoother scene transitions.
        fade = min(1.0, i / (FPS * 0.5), (frame_count - i - 1) / (FPS * 0.5))
        if fade < 1.0:
            black = Image.new("RGB", (W, H), (0, 0, 0))
            frame = Image.blend(black, frame, max(0.0, fade))
        frames.append(cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR))
    return frames


def default_scenes(images, listing):
    address = listing.get("address", "21 Chester")
    location = listing.get("location", "Orange County, California")
    price = listing.get("price", "Private Luxury Listing")
    beds = listing.get("beds", "")
    baths = listing.get("baths", "")
    sqft = listing.get("sqft", "")
    stats = [value for value in [beds, baths, sqft] if value]

    selected = [
        images[8] if len(images) > 8 else images[0],
        images[3] if len(images) > 3 else images[0],
        images[4] if len(images) > 4 else images[0],
        images[0],
        images[6] if len(images) > 6 else images[0],
        images[7] if len(images) > 7 else images[0],
        images[5] if len(images) > 5 else images[0],
        images[1] if len(images) > 1 else images[0],
    ]
    return [
        (selected[0], 3.0, address, f"{location} | {price}", "Luxury Listing", stats, "AI-generated property video demo"),
        (selected[1], 2.6, "Resort-Style Setting", "Elevated views, privacy, pool, and outdoor entertaining spaces.", "Exterior", None, None),
        (selected[2], 2.4, "City-Light Views", "A dramatic backdrop from sunset into evening.", "View", None, None),
        (selected[3], 2.7, "Bright Grand Living", "Double-height spaces, clean finishes, and seamless indoor-outdoor flow.", "Interior", None, None),
        (selected[4], 2.4, "Chef-Inspired Kitchen", "Large island, open dining, and windows framing the view.", "Kitchen", None, None),
        (selected[5], 2.2, "Comfortable Family Room", "Relaxed gathering space with fireplace and direct outdoor access.", "Lifestyle", None, None),
        (selected[6], 2.2, "Spa-Like Primary Bath", "Marble finishes, soaking tub, glass shower, and natural light.", "Primary Suite", None, None),
        (selected[7], 2.5, "Schedule a Private Tour", "A polished listing video generated from property data and photos.", "Next Step", None, "Powered by Cell AI Data workflow"),
    ]


def write_video(output_path, scenes):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_path), fourcc, FPS, (W, H))
    if not writer.isOpened():
        raise RuntimeError("Could not open MP4 writer.")
    try:
        for idx, scene in enumerate(scenes):
            image, duration, title, subtitle, badge, stats, footer = scene
            frames = make_scene_frames(image, duration, title, subtitle, badge, stats, footer, 1 if idx % 2 == 0 else -1)
            for frame in frames:
                writer.write(frame)
    finally:
        writer.release()


def main():
    parser = argparse.ArgumentParser(description="Generate a short real estate promo video from listing photos.")
    parser.add_argument("--images", nargs="+", required=True)
    parser.add_argument("--listing-json", default="{}")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    listing = json.loads(args.listing_json)
    images = [Path(p) for p in args.images]
    missing = [str(p) for p in images if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing images: {missing}")
    scenes = default_scenes(images, listing)
    write_video(Path(args.output), scenes)
    print(json.dumps({"ok": True, "output": args.output, "images": len(images), "duration_seconds": 20}, indent=2))


if __name__ == "__main__":
    main()
