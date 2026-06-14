import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from quotes import random_quote

BG_COLOR = (22, 27, 44)
CARD_BG = (30, 36, 58)
ACCENT = (201, 168, 76)
TEXT_WHITE = (235, 235, 240)
TEXT_DIM = (150, 155, 175)
STAT_BG = (38, 44, 68)
STREAK_COLOR = (255, 140, 50)

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
        "serif": f"{SERIF_DIR}/LiberationSerif-Bold.ttf",
    }
    return ImageFont.truetype(paths.get(name, paths["regular"]), size)


def _circle_avatar(avatar, size):
    big = size * 2
    avatar = avatar.resize((big, big), Image.LANCZOS)
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, big - 1, big - 1), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1))
    avatar.putalpha(mask)
    return avatar.resize((size, size), Image.LANCZOS)


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


def _draw_stat_box(draw, x, y, w, h, label, value, value_color=ACCENT):
    draw.rounded_rectangle((x, y, x + w, y + h), radius=10, fill=STAT_BG)
    label_font = _font("light", 11)
    lw = draw.textlength(label, font=label_font)
    draw.text((x + w / 2 - lw / 2, y + 8), label, font=label_font, fill=TEXT_DIM)
    value_font = _font("bold", 20)
    vw = draw.textlength(str(value), font=value_font)
    draw.text((x + w / 2 - vw / 2, y + 28), str(value), font=value_font, fill=value_color)


def generate_profile_card(
    name: str,
    avatar: Image.Image | None,
    total_time: str,
    sessions: int,
    best_session: str,
    rank: int,
    streak: int,
    monthly_time: str,
) -> io.BytesIO:
    WIDTH = 600

    tmp_img = Image.new("RGBA", (1, 1))
    tmp_draw = ImageDraw.Draw(tmp_img)
    quote_text_raw, quote_author = random_quote()
    quote_font = _font("light", 13)
    max_quote_w = WIDTH - 15 - 30 - 14 - 15
    wrapped_quote = _wrap_text(tmp_draw, f'"{quote_text_raw}"', quote_font, max_quote_w)
    quote_lines = wrapped_quote.count("\n") + 1
    quote_box_h = 35 + quote_lines * 18 + 20

    box_y = 155
    box_h = 65
    bar_y = box_y + box_h + 20
    HEIGHT = bar_y + quote_box_h + 45

    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((0, 0, WIDTH, HEIGHT), radius=16, fill=BG_COLOR)

    draw.rounded_rectangle((15, 15, WIDTH - 15, 140), radius=12, fill=CARD_BG)

    draw.rectangle((15, 130, WIDTH - 15, 133), fill=ACCENT)

    av_size = 80
    av_x, av_y = 35, 30
    if avatar:
        av = _circle_avatar(avatar, av_size)
        draw.ellipse((av_x - 3, av_y - 3, av_x + av_size + 3, av_y + av_size + 3), fill=ACCENT)
        img.paste(av, (av_x, av_y), av)
    else:
        draw.ellipse((av_x, av_y, av_x + av_size, av_y + av_size), fill=STAT_BG)
        init_font = _font("bold", 36)
        initial = name[0].upper()
        iw = draw.textlength(initial, font=init_font)
        bbox = init_font.getbbox(initial)
        ih = bbox[3] - bbox[1]
        draw.text((av_x + av_size / 2 - iw / 2, av_y + av_size / 2 - ih / 2), initial, font=init_font, fill=TEXT_WHITE)

    name_font = _font("bold", 24)
    display_name = name if len(name) <= 20 else name[:19] + ".."
    draw.text((av_x + av_size + 20, av_y + 5), display_name, font=name_font, fill=TEXT_WHITE)

    title_font = _font("light", 13)
    rank_str = f"Rank #{rank}" if rank > 0 else "Unranked"
    draw.text((av_x + av_size + 20, av_y + 35), rank_str, font=title_font, fill=TEXT_DIM)

    if streak > 0:
        streak_font = _font("condensed", 14)
        streak_str = f"{streak} day streak"
        sx = av_x + av_size + 20
        draw.text((sx, av_y + 58), streak_str, font=streak_font, fill=STREAK_COLOR)

    total_label_font = _font("light", 12)
    draw.text((WIDTH - 180, av_y + 8), "TOTAL STUDY TIME", font=total_label_font, fill=TEXT_DIM)
    total_font = _font("black", 28)
    draw.text((WIDTH - 180, av_y + 28), total_time, font=total_font, fill=ACCENT)

    box_w = (WIDTH - 30 - 30) // 3
    gap = 15

    _draw_stat_box(draw, 15, box_y, box_w, box_h, "SESSIONS", str(sessions))
    _draw_stat_box(draw, 15 + box_w + gap, box_y, box_w, box_h, "BEST SESSION", best_session)
    _draw_stat_box(draw, 15 + (box_w + gap) * 2, box_y, box_w, box_h, "THIS MONTH", monthly_time)

    draw.rounded_rectangle((15, bar_y, WIDTH - 15, bar_y + quote_box_h), radius=12, fill=CARD_BG)

    quote_bar_x = 30
    draw.rectangle((quote_bar_x, bar_y + 15, quote_bar_x + 2, bar_y + quote_box_h - 15), fill=ACCENT)

    draw.text((quote_bar_x + 14, bar_y + 18), wrapped_quote, font=quote_font, fill=TEXT_DIM)
    attr_y = bar_y + 18 + quote_lines * 18
    attr_font = _font("light", 11)
    draw.text((quote_bar_x + 14, attr_y), f"— {quote_author}", font=attr_font, fill=(*ACCENT, 180))

    footer_y = HEIGHT - 30
    footer_font = _font("light", 10)
    ft = "Professor Moore  ·  Student Profile Card"
    fw = draw.textlength(ft, font=footer_font)
    draw.text(((WIDTH - fw) / 2, footer_y), ft, font=footer_font, fill=TEXT_DIM)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
