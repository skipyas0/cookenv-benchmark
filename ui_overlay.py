# ui_overlay.py
import pygame
from textwrap import dedent


def _wrap_text(text, font, max_width):
    """Helper to wrap text into lines fitting into max_width."""
    words = text.split()
    lines, line = [], ""
    for w in words:
        test = (line + " " + w).strip()
        if font.size(test)[0] > max_width:
            if line:
                lines.append(line)
                line = w
            else:
                # word itself too long, force break
                lines.append(w)
                line = ""
        else:
            line = test
    if line:
        lines.append(line)
    return lines


def draw_game_info(screen, width, height, tile_size):
    """Draw the general game info overlay with wrapped text."""
    over = pygame.Surface((width, height), pygame.SRCALPHA)
    over.fill((10, 10, 10, 220))
    screen.blit(over, (0, 0))

    try:
        font = pygame.font.SysFont(None, max(12, tile_size // 4))
        head_font = pygame.font.SysFont(None, max(18, tile_size // 2), bold=True)
    except Exception:
        return

    x_pad = 24
    y_pad = 24
    text_w = width - 2 * x_pad

    # Title
    screen.blit(head_font.render("Game Info (Press E to EXIT)", True, (245, 245, 245)), (x_pad, y_pad))
    y_cursor = y_pad + head_font.get_height() + 12

    # Game instructions and tips
    game_text = dedent("""\
    You are playing a simple tile-based cooking game. 
	Controls: Moving (WSAD/Arrows), Interact (Space), Pass time (Q), Information (E), Drop item (R)
    The map is a grid-world consisting of 4 different block types:
    - floor: light, you can move freely on floor blocks, each move costs you one 'game_time'
    - wall: dark, you can't move through wall blocks
    - dispenser: marked by a digit 1-9, impassable, you can interact with it using (Space) to acquire an ingredient if your inventory is empty
    - appliance: marked by a uppercase letter A-E, impassable, you can interact with it using (Space) to either 1. place the contents of your inventory inside or 2. take the contents of the appliance if your inventory is empty
    
	If an appliance contains a specific combination of ingredients, it performs an 'operation', yielding a novel ingredient after some amount of 'game_time' passes.
    By using (E), you can display information about the given task - a textual recipe, a mapping which maps objects in the recipe to block ids on the board, inventory and appliance states.
    You can use (R) to drop your current item if needed. Your goal is to perform the actions described in the recipe in as little 'game_time' as possible.
    Each move on the board costs 1 'game_time'. If your move is blocked by an impassable object, the player just changes orientation without incrementing 'game_time'.
    Interacting and summoning info does not cost 'game_time'. If you need to pass 'game_time' without moving, (e.g. when waiting for an appliance to finish an operation), use the (Q) to skip time.
    """)

    # Wrap text
    lines = []
    for para in game_text.strip().split("\n"):
        para = para.strip()
        if not para:
            lines.append("")
            continue
        lines.extend(_wrap_text(para, font, text_w))

    # Render
    for line in lines:
        if not line:
            y_cursor += font.get_height() + 4
            continue
        clr = (255, 100, 0) if 'Controls' in line else (235, 235, 235)
        screen.blit(font.render(line, True, clr), (x_pad, y_cursor))
        y_cursor += font.get_height() + 6


def draw_level_info(screen, width, height, tile_size, level, _load_appliance_colors):
    """Draw level-specific info: description, mapping, items, appliances."""
    over = pygame.Surface((width, height), pygame.SRCALPHA)
    over.fill((10, 10, 10, 220))
    screen.blit(over, (0, 0))

    try:
        info_font = pygame.font.SysFont(None, max(16, tile_size // 3))
        head_font = pygame.font.SysFont(None, max(18, tile_size // 2), bold=True)
    except Exception:
        return

    lvl = level
    x_pad = 24
    y_pad = 24
    col_gap = 24
    desc_w = int(width * 0.62) - 2 * x_pad

    # Left: Description
    screen.blit(head_font.render("Level Info (Press E to EXIT)", True, (245, 245, 245)), (x_pad, y_pad))
    y_cursor = y_pad + head_font.get_height() + 8
    for para in (lvl.desc or "").split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if "#" in para:
            para = para.split("#")[1]

        lines = _wrap_text(para, info_font, desc_w)
        for line in lines:
            screen.blit(
                info_font.render(line, True, (230, 230, 230)), (x_pad + 8, y_cursor)
            )
            y_cursor += info_font.get_height() + 6
        y_cursor += 8  # paragraph spacing

    # Right: Mapping
    right_x = x_pad + desc_w + col_gap
    try:
        colors = _load_appliance_colors()
    except Exception:
        colors = {}

    # Items
    y_m = y_pad
    screen.blit(head_font.render("Items", True, (245, 245, 245)), (right_x, y_m))
    y_m += head_font.get_height() + 8
    for k, v in (lvl.mapping or {}).items():
        if k.isdigit():
            line = f"• {k}: {v}"
            screen.blit(
                info_font.render(line, True, (220, 220, 220)), (right_x + 6, y_m)
            )
            y_m += info_font.get_height() + 6

    # Appliances
    y_m += 8
    screen.blit(head_font.render("Appliances", True, (245, 245, 245)), (right_x, y_m))
    y_m += head_font.get_height() + 8
    for k, v in (lvl.mapping or {}).items():
        if k.isalpha():
            color = colors.get(k)
            text_color = (
                (220, 220, 220)
                if color is None
                else tuple(max(0, min(255, int(c))) for c in color)
            )
            line = f"• {k}: {v}"
            screen.blit(info_font.render(line, True, text_color), (right_x + 6, y_m))
            y_m += info_font.get_height() + 6
