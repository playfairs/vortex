import os
import emoji
from io import BytesIO
from aiohttp import ClientSession
from PIL import Image, ImageDraw, ImageFont
from typing import Union


async def _convert_number(number: int) -> str:
    if number >= 1000000000:
        return f"{number / 1000000000:.1f}B"
    elif number >= 1000000:
        return f"{number / 1000000:.1f}M"
    elif number >= 1000:
        return f"{number / 1000:.1f}K"
    else:
        return str(number)


async def _image(url: str):
    async with ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise ValueError(f"Invalid image url: {url}")
            data = await response.read()
            return Image.open(BytesIO(data))


def _get_mixed_text_length(
    text_string: str,
    main_font: ImageFont.FreeTypeFont,
    emoji_font: ImageFont.FreeTypeFont,
    draw: ImageDraw.ImageDraw,
) -> int:
    total_width = 0
    for char in text_string:
        font_to_use = emoji_font if emoji.is_emoji(char) else main_font
        total_width += draw.textlength(char, font=font_to_use)
    return total_width


def _draw_mixed_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text_string: str,
    main_font: ImageFont.FreeTypeFont,
    emoji_font: ImageFont.FreeTypeFont,
    fill: str,
    stroke_width: int = 0,
    stroke_fill: Union[str, None] = None,
):
    current_x = xy[0]
    y = xy[1]
    # print(f"Drawing text: '{text_string}'") # Optional: print the whole string
    for char in text_string:
        is_char_emoji = emoji.is_emoji(char)
        font_to_use = emoji_font if is_char_emoji else main_font
        # ---- DEBUGGING PRINT ----
        # print(f"Char: '{char}', Is Emoji: {is_char_emoji}, Font: {'Emoji Font' if is_char_emoji else 'Main Font'}")
        # ---- END DEBUGGING PRINT ----
        try:
            draw.text(
                (current_x, y),
                char,
                font=font_to_use,
                fill=fill,
                stroke_width=stroke_width,
                stroke_fill=stroke_fill,
            )
            current_x += draw.textlength(char, font=font_to_use)
        except Exception as e:
            print(f"Error drawing character '{char}': {e}")


async def create_rank_card(
    avatar,
    level,
    rank,
    username,
    current_xp,
    max_xp,
    bar_color="teal",
    text_color="white",
    background_color="#1A1A1E",
    resize=100,
):
    path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    if isinstance(avatar, str):
        if avatar.startswith("http"):
            avatar = await _image(avatar)
    elif isinstance(avatar, Image.Image):
        pass
    else:
        raise TypeError(f"avatar must be a url, not {type(avatar)}")

    card_width, card_height = 1000, 333
    card_corner_radius = 30

    background = Image.new("RGBA", (card_width, card_height), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(background)
    bg_draw.rounded_rectangle(
        (0, 0, card_width, card_height),
        radius=card_corner_radius,
        fill=background_color,
    )

    inner_panel_width, inner_panel_height = 950, 333 - 50
    inner_panel_offset_x, inner_panel_offset_y = 25, 25
    inner_corner_radius = 20
    inner_panel_color = "#2f3136"

    inner_panel = Image.new(
        "RGBA", (inner_panel_width, inner_panel_height), (0, 0, 0, 0)
    )
    inner_draw = ImageDraw.Draw(inner_panel)
    inner_draw.rounded_rectangle(
        (0, 0, inner_panel_width, inner_panel_height),
        radius=inner_corner_radius,
        fill=inner_panel_color,
    )
    background.paste(
        inner_panel, (inner_panel_offset_x, inner_panel_offset_y), inner_panel
    )

    avatar_resized = avatar.resize((260, 260))

    circular_mask = Image.new("L", avatar_resized.size, 0)
    mask_draw = ImageDraw.Draw(circular_mask)
    mask_draw.ellipse((0, 0, avatar_resized.size[0], avatar_resized.size[1]), fill=255)

    avatar_rgba = avatar_resized.convert("RGBA")
    avatar_rgba.putalpha(circular_mask)

    background.paste(avatar_rgba, (53, 36), avatar_rgba)

    draw = ImageDraw.Draw(background)
    main_font = ImageFont.truetype(path + "/assets/levelfont.otf", 50)
    emoji_font = ImageFont.truetype(path + "/assets/Twemoji.ttf", 50)

    level_text = "LEVEL: " + await _convert_number(level)
    _draw_mixed_text(
        draw,
        (330, 40),
        level_text,
        main_font,
        emoji_font,
        fill=text_color,
        stroke_width=1,
        stroke_fill=(0, 0, 0),
    )

    if rank is not None:
        rank_text = "RANK: #" + str(rank)
        w_rank = _get_mixed_text_length(rank_text, main_font, emoji_font, draw)
        _draw_mixed_text(
            draw,
            (950 - w_rank, 40),
            rank_text,
            main_font,
            emoji_font,
            fill=text_color,
            stroke_width=1,
            stroke_fill=(0, 0, 0),
        )

    truncated_username = username[:15]
    _draw_mixed_text(
        draw,
        (330, 130),
        truncated_username,
        main_font,
        emoji_font,
        fill=text_color,
        stroke_width=1,
        stroke_fill=(0, 0, 0),
    )

    exp_text = (
        f"XP: {await _convert_number(current_xp)}/{await _convert_number(max_xp)}"
    )
    w_exp = _get_mixed_text_length(exp_text, main_font, emoji_font, draw)
    _draw_mixed_text(
        draw,
        (950 - w_exp, 130),
        exp_text,
        main_font,
        emoji_font,
        fill=text_color,
        stroke_width=1,
        stroke_fill=(0, 0, 0),
    )

    bar_width_total = 619
    bar_height = 50
    bar_corner_radius_xp = bar_height // 2

    bar_exp_ratio = current_xp / max_xp if max_xp > 0 else 0
    bar_exp_fill_width = bar_exp_ratio * bar_width_total

    if current_xp > 0 and bar_exp_fill_width < bar_corner_radius_xp * 2:
        bar_exp_fill_width = bar_corner_radius_xp * 2
    elif current_xp == 0:
        bar_exp_fill_width = 0

    bar_exp_fill_width = min(bar_exp_fill_width, bar_width_total)

    xp_bar_img = Image.new("RGBA", (bar_width_total, bar_height), (0, 0, 0, 0))
    draw_xp_bar = ImageDraw.Draw(xp_bar_img)

    draw_xp_bar.rounded_rectangle(
        (0, 0, bar_width_total, bar_height),
        radius=bar_corner_radius_xp,
        fill=(255, 255, 255, 50),
    )

    if current_xp > 0 and bar_exp_fill_width > 0:
        draw_xp_bar.rounded_rectangle(
            (0, 0, bar_exp_fill_width, bar_height),
            radius=bar_corner_radius_xp,
            fill=bar_color,
        )

    background.paste(xp_bar_img, (330, 235), xp_bar_img)

    if resize != 100:
        new_size = (
            int(background.size[0] * (resize / 100)),
            int(background.size[1] * (resize / 100)),
        )
        background = background.resize(new_size, Image.Resampling.LANCZOS)

    image_bytes = BytesIO()
    background.save(image_bytes, "PNG")
    image_bytes.seek(0)
    return image_bytes
