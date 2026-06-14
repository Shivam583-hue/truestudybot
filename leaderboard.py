import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BG_COLOR = (22, 27, 44)
HEADER_BG = (30, 36, 58)
ROW_EVEN = (28, 34, 54)
ROW_ODD = (34, 40, 62)
GOLD = (201, 168, 76)
SILVER = (180, 180, 195)
BRONZE = (176, 141, 87)
TEXT_WHITE = (235, 235, 240)
TEXT_DIM = (150, 155, 175)
PODIUM_BG = (38, 44, 68)
RANK_COLORS = [GOLD, SILVER, BRONZE]

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
        "serif-regular": f"{SERIF_DIR}/LiberationSerif-Regular.ttf",
    }
    return ImageFont.truetype(paths.get(name, paths["regular"]), size)


async def fetch_avatar(url: str, size: int = 64) -> Image.Image | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(str(url)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    img = Image.open(io.BytesIO(data)).convert("RGBA")
                    img = img.resize((size, size), Image.LANCZOS)
                    return img
    except Exception:
        return None


def make_circle_avatar(avatar: Image.Image, size: int = 64) -> Image.Image:
    big = size * 2
    avatar = avatar.resize((big, big), Image.LANCZOS)
    mask = Image.new("L", (big, big), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, big - 1, big - 1), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(1))
    avatar.putalpha(mask)
    return avatar.resize((size, size), Image.LANCZOS)


def _draw_rounded_rect(draw: ImageDraw.Draw, xy, radius, fill):
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def _draw_avatar_or_initial(img, draw, entry, x, y, size):
    if entry.get("avatar"):
        av = make_circle_avatar(entry["avatar"], size)
        img.paste(av, (x, y), av)
    else:
        draw.ellipse((x, y, x + size, y + size), fill=PODIUM_BG)
        init_font = _font("bold", size // 2)
        initial = entry["name"][0].upper()
        iw = draw.textlength(initial, font=init_font)
        bbox = init_font.getbbox(initial)
        ih = bbox[3] - bbox[1]
        draw.text(
            (x + size / 2 - iw / 2, y + size / 2 - ih / 2),
            initial, font=init_font, fill=TEXT_WHITE,
        )


def _draw_row(img, draw, entry, y, width, padding, rank_color=TEXT_DIM):
    row_color = ROW_EVEN if entry["rank"] % 2 == 0 else ROW_ODD
    ROW_H = 58
    _draw_rounded_rect(draw, (padding, y, width - padding, y + ROW_H - 4), radius=8, fill=row_color)

    rank_font = _font("bold", 20)
    draw.text((padding + 18, y + 16), str(entry["rank"]), font=rank_font, fill=rank_color)

    av_x = padding + 60
    _draw_avatar_or_initial(img, draw, entry, av_x, y + 8, 38)

    name_font = _font("medium", 17)
    name = entry["name"]
    if len(name) > 22:
        name = name[:21] + ".."
    draw.text((av_x + 52, y + 16), name, font=name_font, fill=TEXT_WHITE)

    time_font = _font("bold", 17)
    tw = draw.textlength(entry["time_str"], font=time_font)
    draw.text((width - padding - 18 - tw, y + 16), entry["time_str"], font=time_font, fill=GOLD)


def generate_leaderboard_image(
    title: str,
    subtitle: str,
    entries: list[dict],
    quote: str = "We are what we repeatedly do. Excellence, then, is not an act, but a habit.",
) -> io.BytesIO:
    WIDTH = 700
    PADDING = 30
    HEADER_H = 110
    ROW_H = 58
    PODIUM_H = 200 if len(entries) >= 3 else 0
    remaining_entries = entries[3:] if len(entries) >= 3 else entries
    ROWS_H = len(remaining_entries) * ROW_H
    QUOTE_H = 70
    FOOTER_H = 40

    total_h = HEADER_H + PODIUM_H + ROWS_H + QUOTE_H + FOOTER_H + PADDING * 2
    if not entries:
        total_h = HEADER_H + 80 + QUOTE_H + FOOTER_H + PADDING * 2

    img = Image.new("RGBA", (WIDTH, total_h), BG_COLOR)
    draw = ImageDraw.Draw(img)

    _draw_rounded_rect(draw, (0, 0, WIDTH, HEADER_H), radius=0, fill=HEADER_BG)
    draw.rectangle((0, HEADER_H - 3, WIDTH, HEADER_H), fill=GOLD)

    title_font = _font("serif", 32)
    tw = draw.textlength(title, font=title_font)
    draw.text(((WIDTH - tw) / 2, 22), title, font=title_font, fill=GOLD)

    sub_font = _font("regular", 14)
    sw = draw.textlength(subtitle, font=sub_font)
    draw.text(((WIDTH - sw) / 2, 65), subtitle, font=sub_font, fill=TEXT_DIM)

    y = HEADER_H + 10

    if not entries:
        empty_font = _font("light", 18)
        et = "No study sessions recorded yet."
        ew = draw.textlength(et, font=empty_font)
        draw.text(((WIDTH - ew) / 2, y + 25), et, font=empty_font, fill=TEXT_DIM)
        y += 80
    elif len(entries) >= 3:
        podium_y = y + 10
        positions = [
            (WIDTH // 2, 80, "1ST", 0),
            (WIDTH // 2 - 180, 64, "2ND", 20),
            (WIDTH // 2 + 180, 64, "3RD", 20),
        ]

        for idx, (cx, av_size, rank_label, y_off) in enumerate(positions):
            entry = entries[idx]
            rank_color = RANK_COLORS[idx]
            ey = podium_y + y_off

            circle_r = av_size // 2 + 4
            draw.ellipse(
                (cx - circle_r, ey - circle_r + av_size // 2 + 10,
                 cx + circle_r, ey + circle_r + av_size // 2 + 10),
                fill=rank_color,
            )

            _draw_avatar_or_initial(img, draw, entry, cx - av_size // 2, ey + 10, av_size)

            rank_font = _font("condensed", 13)
            rw = draw.textlength(rank_label, font=rank_font)
            draw.text((cx - rw / 2, ey + av_size + 18), rank_label, font=rank_font, fill=rank_color)

            name_font = _font("medium", 13)
            name = entry["name"]
            if len(name) > 14:
                name = name[:13] + ".."
            nw = draw.textlength(name, font=name_font)
            draw.text((cx - nw / 2, ey + av_size + 34), name, font=name_font, fill=TEXT_WHITE)

            time_font = _font("light", 12)
            ttw = draw.textlength(entry["time_str"], font=time_font)
            draw.text((cx - ttw / 2, ey + av_size + 52), entry["time_str"], font=time_font, fill=TEXT_DIM)

        y = podium_y + PODIUM_H

        for i, entry in enumerate(entries[3:]):
            _draw_row(img, draw, entry, y + i * ROW_H, WIDTH, PADDING)

        y += ROWS_H
    else:
        for i, entry in enumerate(entries):
            rank_color = RANK_COLORS[i] if i < 3 else TEXT_DIM
            _draw_row(img, draw, entry, y + i * ROW_H, WIDTH, PADDING, rank_color)

        y += ROWS_H

    y += 10
    draw.rectangle((PADDING + 4, y, PADDING + 6, y + 35), fill=GOLD)
    quote_font = _font("serif-regular", 13)
    draw.text((PADDING + 16, y + 4), f'"{quote}"', font=quote_font, fill=TEXT_DIM)
    quote_attr = _font("light", 11)
    draw.text((PADDING + 16, y + 24), "— Prof. Moore", font=quote_attr, fill=(*GOLD, 180))

    y += QUOTE_H
    footer_font = _font("light", 11)
    ft = "Generated by Professor Moore"
    fw = draw.textlength(ft, font=footer_font)
    draw.text(((WIDTH - fw) / 2, y), ft, font=footer_font, fill=TEXT_DIM)

    mask = Image.new("L", img.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, WIDTH, total_h), radius=16, fill=255)
    img.putalpha(mask)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
