import io
import math
from PIL import Image, ImageDraw, ImageFont

BG_OUTER = (22, 27, 44)
BG_INNER = (30, 36, 58)
RING_BG = (45, 52, 78)
WORK_COLOR = (201, 168, 76)
BREAK_COLOR = (90, 150, 255)
TEXT_WHITE = (235, 235, 240)
TEXT_DIM = (150, 155, 175)
COMPLETE_COLOR = (76, 175, 100)

FONT_DIR = "/usr/share/fonts/TTF"
SERIF_DIR = "/usr/share/fonts/liberation"


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    paths = {
        "bold": f"{FONT_DIR}/Roboto-Bold.ttf",
        "medium": f"{FONT_DIR}/Roboto-Medium.ttf",
        "regular": f"{FONT_DIR}/Roboto-Regular.ttf",
        "light": f"{FONT_DIR}/Roboto-Light.ttf",
        "black": f"{FONT_DIR}/Roboto-Black.ttf",
        "condensed": f"{FONT_DIR}/RobotoCondensed-Bold.ttf",
        "serif": f"{SERIF_DIR}/LiberationSerif-Bold.ttf",
    }
    return ImageFont.truetype(paths.get(name, paths["regular"]), size)


def _draw_arc_ring(draw, center, radius, thickness, progress, color, bg_color):
    cx, cy = center
    bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
    draw.arc(bbox, 0, 360, fill=bg_color, width=thickness)
    if progress > 0:
        start = -90
        end = start + 360 * progress
        draw.arc(bbox, start, end, fill=color, width=thickness)


def generate_timer_image(phase, remaining, total, cycle, members):
    WIDTH = 500
    HEIGHT = 500
    CENTER = (WIDTH // 2, 210)
    RING_RADIUS = 130
    RING_THICKNESS = 10

    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((0, 0, WIDTH, HEIGHT), radius=20, fill=BG_OUTER)

    draw.ellipse(
        (CENTER[0] - RING_RADIUS - 30, CENTER[1] - RING_RADIUS - 30,
         CENTER[0] + RING_RADIUS + 30, CENTER[1] + RING_RADIUS + 30),
        fill=BG_INNER,
    )

    progress = max(0, min(1, 1 - remaining / total)) if total > 0 else 0
    accent = WORK_COLOR if phase == "work" else BREAK_COLOR
    _draw_arc_ring(draw, CENTER, RING_RADIUS, RING_THICKNESS, progress, accent, RING_BG)

    if 0 < progress < 1:
        angle = math.radians(-90 + 360 * progress)
        dot_x = CENTER[0] + RING_RADIUS * math.cos(angle)
        dot_y = CENTER[1] + RING_RADIUS * math.sin(angle)
        draw.ellipse((dot_x - 6, dot_y - 6, dot_x + 6, dot_y + 6), fill=accent)

    mins = int(remaining) // 60
    secs = int(remaining) % 60
    time_str = f"{mins:02d}:{secs:02d}"
    time_font = _font("bold", 52)
    tw = draw.textlength(time_str, font=time_font)
    bbox = time_font.getbbox(time_str)
    th = bbox[3] - bbox[1]
    draw.text((CENTER[0] - tw / 2, CENTER[1] - th / 2 - 15), time_str, font=time_font, fill=accent)

    phase_label = "FOCUS" if phase == "work" else "BREAK"
    label_font = _font("condensed", 16)
    lw = draw.textlength(phase_label, font=label_font)
    draw.text((CENTER[0] - lw / 2, CENTER[1] + 30), phase_label, font=label_font, fill=TEXT_DIM)

    cycle_font = _font("light", 13)
    cycle_str = f"Cycle #{cycle}"
    cw = draw.textlength(cycle_str, font=cycle_font)
    draw.text((CENTER[0] - cw / 2, CENTER[1] + 52), cycle_str, font=cycle_font, fill=TEXT_DIM)

    bottom_y = CENTER[1] + RING_RADIUS + 50
    draw.rectangle((40, bottom_y, WIDTH - 40, bottom_y + 1), fill=RING_BG)
    bottom_y += 15

    count = len(members)
    header_font = _font("medium", 14)
    draw.text((40, bottom_y), f"In Session ({count})", font=header_font, fill=TEXT_DIM)
    bottom_y += 25

    name_font = _font("regular", 13)
    time_font = _font("light", 12)
    if members:
        display = members[:6]
        parts = []
        for name, elapsed in display:
            parts.append(f"{name} ({elapsed})")
        names_str = ", ".join(parts)
        if len(members) > 6:
            names_str += f" +{len(members) - 6} more"
        draw.text((40, bottom_y), names_str, font=name_font, fill=TEXT_WHITE)
    else:
        draw.text((40, bottom_y), "No one", font=name_font, fill=TEXT_DIM)

    bottom_y += 30
    footer_font = _font("light", 11)
    ft = "Professor Moore is keeping an eye."
    fw = draw.textlength(ft, font=footer_font)
    draw.text(((WIDTH - fw) / 2, bottom_y + 5), ft, font=footer_font, fill=TEXT_DIM)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def generate_timer_complete_image(phase, cycle, duration_str):
    WIDTH = 500
    HEIGHT = 320
    CENTER = (WIDTH // 2, 130)
    RING_RADIUS = 80
    RING_THICKNESS = 8

    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((0, 0, WIDTH, HEIGHT), radius=20, fill=BG_OUTER)

    draw.ellipse(
        (CENTER[0] - RING_RADIUS - 20, CENTER[1] - RING_RADIUS - 20,
         CENTER[0] + RING_RADIUS + 20, CENTER[1] + RING_RADIUS + 20),
        fill=BG_INNER,
    )

    color = COMPLETE_COLOR if phase == "work" else BREAK_COLOR
    draw.arc(
        (CENTER[0] - RING_RADIUS, CENTER[1] - RING_RADIUS,
         CENTER[0] + RING_RADIUS, CENTER[1] + RING_RADIUS),
        0, 360, fill=color, width=RING_THICKNESS,
    )

    if phase == "work":
        label = "DONE"
        sub = f"Cycle #{cycle} complete"
    else:
        label = "READY"
        sub = "Back to work"

    label_font = _font("bold", 32)
    lw = draw.textlength(label, font=label_font)
    bbox = label_font.getbbox(label)
    lh = bbox[3] - bbox[1]
    draw.text((CENTER[0] - lw / 2, CENTER[1] - lh / 2 - 5), label, font=label_font, fill=color)

    sub_font = _font("light", 14)
    sw = draw.textlength(sub, font=sub_font)
    draw.text((CENTER[0] - sw / 2, CENTER[1] + 25), sub, font=sub_font, fill=TEXT_DIM)

    bottom_y = CENTER[1] + RING_RADIUS + 35
    draw.rectangle((40, bottom_y, WIDTH - 40, bottom_y + 1), fill=RING_BG)
    bottom_y += 15

    info_font = _font("medium", 14)
    info = f"Duration: {duration_str}  ·  Status: Completed"
    iw = draw.textlength(info, font=info_font)
    draw.text(((WIDTH - iw) / 2, bottom_y), info, font=info_font, fill=TEXT_DIM)

    bottom_y += 30
    footer_font = _font("light", 11)
    ft = "Professor Moore"
    fw = draw.textlength(ft, font=footer_font)
    draw.text(((WIDTH - fw) / 2, bottom_y), ft, font=footer_font, fill=TEXT_DIM)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
