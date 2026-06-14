import io
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BG_COLOR = (22, 27, 44)
CARD_BG = (30, 36, 58)
ACCENT = (201, 168, 76)
RED_ACCENT = (239, 68, 68)
TEXT_WHITE = (235, 235, 240)
TEXT_DIM = (150, 155, 175)
STAT_BG = (38, 44, 68)

FONT_DIR = "/usr/share/fonts/TTF"
SERIF_DIR = "/usr/share/fonts/liberation"


def _font(name, size):
    paths = {
        "bold": f"{FONT_DIR}/Roboto-Bold.ttf",
        "medium": f"{FONT_DIR}/Roboto-Medium.ttf",
        "regular": f"{FONT_DIR}/Roboto-Regular.ttf",
        "light": f"{FONT_DIR}/Roboto-Light.ttf",
        "black": f"{FONT_DIR}/Roboto-Black.ttf",
        "condensed": f"{FONT_DIR}/RobotoCondensed-Bold.ttf",
        "serif": f"{SERIF_DIR}/LiberationSerif-Regular.ttf",
    }
    return ImageFont.truetype(paths.get(name, paths["regular"]), size)


def generate_session_summary(
    name: str,
    duration_str: str,
    duration_secs: float,
    total_today_str: str,
    sessions_today: int,
    streak: int,
) -> io.BytesIO:
    WIDTH = 500
    HEIGHT = 280

    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((0, 0, WIDTH, HEIGHT), radius=16, fill=BG_COLOR)

    draw.rectangle((0, 0, 5, HEIGHT), fill=RED_ACCENT)

    header_font = _font("condensed", 14)
    draw.text((25, 18), "SESSION COMPLETE", font=header_font, fill=RED_ACCENT)

    now = datetime.now(timezone.utc)
    time_str = now.strftime("%I:%M %p UTC")
    time_font = _font("light", 12)
    tw = draw.textlength(time_str, font=time_font)
    draw.text((WIDTH - 25 - tw, 20), time_str, font=time_font, fill=TEXT_DIM)

    draw.rectangle((25, 45, WIDTH - 25, 46), fill=STAT_BG)

    dur_label_font = _font("light", 12)
    draw.text((25, 60), "SESSION DURATION", font=dur_label_font, fill=TEXT_DIM)

    dur_font = _font("black", 36)
    draw.text((25, 80), duration_str, font=dur_font, fill=ACCENT)

    box_y = 140
    box_h = 55
    box_w = (WIDTH - 50 - 20) // 3

    for i, (label, value) in enumerate([
        ("TODAY", total_today_str),
        ("SESSIONS", str(sessions_today)),
        ("STREAK", f"{streak}d" if streak > 0 else "—"),
    ]):
        bx = 25 + i * (box_w + 10)
        draw.rounded_rectangle((bx, box_y, bx + box_w, box_y + box_h), radius=8, fill=STAT_BG)
        lf = _font("light", 10)
        lw = draw.textlength(label, font=lf)
        draw.text((bx + box_w / 2 - lw / 2, box_y + 6), label, font=lf, fill=TEXT_DIM)
        vf = _font("bold", 18)
        vw = draw.textlength(value, font=vf)
        draw.text((bx + box_w / 2 - vw / 2, box_y + 25), value, font=vf, fill=TEXT_WHITE)

    remark = _get_remark(duration_secs)
    remark_font = _font("serif", 12)
    draw.text((25, box_y + box_h + 18), f"— {remark}", font=remark_font, fill=TEXT_DIM)

    footer_font = _font("light", 10)
    ft = "Professor Moore"
    fw = draw.textlength(ft, font=footer_font)
    draw.text((WIDTH - 25 - fw, HEIGHT - 25), ft, font=footer_font, fill=TEXT_DIM)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _get_remark(duration_secs: float) -> str:
    mins = duration_secs / 60
    if mins < 5:
        return "A brief visit. Every step counts, however small."
    elif mins < 15:
        return "A short but honest effort. Consistency builds greatness."
    elif mins < 30:
        return "A solid session. You're building momentum."
    elif mins < 60:
        return "Impressive focus. Prof. Moore approves."
    elif mins < 120:
        return "Outstanding discipline. The results will follow."
    else:
        return "Extraordinary dedication. You are among the committed few."
