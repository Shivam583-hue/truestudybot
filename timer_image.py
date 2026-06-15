import io
import math
from PIL import Image, ImageDraw, ImageFont

BG_OUTER = (22, 27, 44)
BG_INNER = (30, 36, 58)
RING_BG = (45, 52, 78)
ACCENT = (201, 168, 76)
TEXT_WHITE = (235, 235, 240)
TEXT_DIM = (150, 155, 175)

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


def _wrap_text(draw, text, font, max_width):
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
    return "\n".join(lines)


def generate_focus_image(elapsed_secs, members):
    WIDTH = 500
    CENTER = (WIDTH // 2, 210)
    RING_RADIUS = 130
    RING_THICKNESS = 10

    tmp = Image.new("RGBA", (1, 1))
    td = ImageDraw.Draw(tmp)
    name_font = _font("regular", 13)
    if members:
        parts = [f"{n} ({e})" for n, e in members[:6]]
        ns = ", ".join(parts)
        if len(members) > 6:
            ns += f" +{len(members) - 6} more"
        wrapped_lines = _wrap_text(td, ns, name_font, WIDTH - 80).count("\n") + 1
    else:
        wrapped_lines = 1
    HEIGHT = CENTER[1] + RING_RADIUS + 50 + 15 + 25 + wrapped_lines * 20 + 10 + 30

    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((0, 0, WIDTH, HEIGHT), radius=20, fill=BG_OUTER)

    draw.ellipse(
        (CENTER[0] - RING_RADIUS - 30, CENTER[1] - RING_RADIUS - 30,
         CENTER[0] + RING_RADIUS + 30, CENTER[1] + RING_RADIUS + 30),
        fill=BG_INNER,
    )

    mins_elapsed = elapsed_secs / 60
    hour_progress = (mins_elapsed % 60) / 60
    _draw_arc_ring(draw, CENTER, RING_RADIUS, RING_THICKNESS, hour_progress, ACCENT, RING_BG)

    if hour_progress > 0:
        angle = math.radians(-90 + 360 * hour_progress)
        dot_x = CENTER[0] + RING_RADIUS * math.cos(angle)
        dot_y = CENTER[1] + RING_RADIUS * math.sin(angle)
        draw.ellipse((dot_x - 6, dot_y - 6, dot_x + 6, dot_y + 6), fill=ACCENT)

    total_secs = int(elapsed_secs)
    h, rem = divmod(total_secs, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        time_str = f"{h}:{m:02d}:{s:02d}"
    else:
        time_str = f"{m:02d}:{s:02d}"
    time_font = _font("bold", 52)
    tw = draw.textlength(time_str, font=time_font)
    bbox = time_font.getbbox(time_str)
    th = bbox[3] - bbox[1]
    draw.text((CENTER[0] - tw / 2, CENTER[1] - th / 2 - 15), time_str, font=time_font, fill=ACCENT)

    label_font = _font("condensed", 16)
    label = "FOCUS SESSION"
    lw = draw.textlength(label, font=label_font)
    draw.text((CENTER[0] - lw / 2, CENTER[1] + 30), label, font=label_font, fill=TEXT_DIM)

    count_font = _font("light", 13)
    count_str = f"{len(members)} studying"
    cw = draw.textlength(count_str, font=count_font)
    draw.text((CENTER[0] - cw / 2, CENTER[1] + 52), count_str, font=count_font, fill=TEXT_DIM)

    bottom_y = CENTER[1] + RING_RADIUS + 50
    draw.rectangle((40, bottom_y, WIDTH - 40, bottom_y + 1), fill=RING_BG)
    bottom_y += 15

    count = len(members)
    header_font = _font("medium", 14)
    draw.text((40, bottom_y), f"In Session ({count})", font=header_font, fill=TEXT_DIM)
    bottom_y += 25

    name_font = _font("regular", 13)
    if members:
        display = members[:6]
        parts = []
        for name, elapsed in display:
            parts.append(f"{name} ({elapsed})")
        names_str = ", ".join(parts)
        if len(members) > 6:
            names_str += f" +{len(members) - 6} more"
        wrapped = _wrap_text(draw, names_str, name_font, WIDTH - 80)
        draw.text((40, bottom_y), wrapped, font=name_font, fill=TEXT_WHITE)
        bottom_y += (wrapped.count("\n") + 1) * 20
    else:
        draw.text((40, bottom_y), "No one", font=name_font, fill=TEXT_DIM)
        bottom_y += 20

    bottom_y += 10
    footer_font = _font("light", 11)
    ft = "Professor Moore is keeping an eye."
    fw = draw.textlength(ft, font=footer_font)
    draw.text(((WIDTH - fw) / 2, bottom_y + 5), ft, font=footer_font, fill=TEXT_DIM)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _draw_arc_ring(draw, center, radius, thickness, progress, color, bg_color):
    cx, cy = center
    bbox = (cx - radius, cy - radius, cx + radius, cy + radius)
    draw.arc(bbox, 0, 360, fill=bg_color, width=thickness)
    if progress > 0:
        start = -90
        end = start + 360 * progress
        draw.arc(bbox, start, end, fill=color, width=thickness)
