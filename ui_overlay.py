# ui_overlay.py
import sys
import os
import base64
import pygame
from textwrap import dedent
import re

game_text = dedent("""\
    <h1>You are playing a simple tile-based cooking game.</h1>
    <p>The goal is to <b style='color: #7D9598'>complete the recipe</b> and get the <b style='color: #7D9598'>goal ingredient</b> into your inventory in as <b style='color: #7D9598'>few steps</b> (game_time) as possible.
    <h2><b style='color: #ff6b6b'>Controls</b></h2>
	Moving <b style='color: #ff6b6b'>(WSAD/Arrows)</b>, Interact <b style='color: #ff6b6b'>(Space)</b>, Pass time <b style='color: #ff6b6b'>(Q)</b>, Information <b style='color: #ff6b6b'>(E)</b>, Discard item <b style='color: #ff6b6b'>(R)</b></b>
    <h2>Map</h2>
    <p>
    The map is a grid-world consisting of 4 different block types:
    <ul>
    <li>floor: light, you can move freely on floor blocks, each move costs you one 'game_time'</li>
    <li>wall: dark, you can't move through wall blocks</li>
    <li>dispenser: marked by an item image, like <img src="{icon_url}" style="width: 24px; vertical-align: middle; margin-right: 10px;">
    <li>appliance: marked by an appliance image, like <img src="{app_url}" style="width: 24px; vertical-align: middle; margin-right: 10px;"></li>
    </ul>
    </p>
    <h2>Tips & Hints</h2>
    <ul>
    <li>Use <b style='color: #ff6b6b'>E</b> to display info and switch between level and game info (this screen)</li>
    <li>Read the <b style='color: #7D9598'>recipe</b> on the level info screen</li>
    <li>Walk to a <b style='color: #7D9598'>dispenser</b> and use <b style='color: #ff6b6b'>Space</b> to grab an ingredient</li>
    <li>Your inventory holds only <b style='color: #7D9598'>one</b> item. You can see which in the menu at the bottom of the screen
    <li>Walk to an <b style='color: #7D9598'>appliance</b> and use <b style='color: #ff6b6b'>Space</b> to place item in inventory or take the item in the appliance</li>
    <li>If the <b style='color: #7D9598'>appliance</b> has the necessary ingredients (in any order), it performs an <b style='color: #7D9598'>operation</b>, which produces a new item after some time</li>
    <li>If you need to wait for an operation without moving, use <b style='color: #ff6b6b'>Q</b></li>
    <li>If your inventory is full but you need to grab another item, interact with an <b style='color: #7D9598'>appliance</b> multiple times to cycle through items or use <b style='color: #ff6b6b'>R</b> to empty your inventory.</li>
    </ul>
    """)

COLOR_BG = "#3C3C3C"
COLOR_ACCENT = "#7D9598" 
COLOR_TEXT = "#E0E0E0"
class BrowserUI:
    def __init__(self):
        self.is_web = sys.platform == "emscripten"
        self.window = None
        self.document = None
        self.overlay = None
        self.game_info = game_text.format(icon_url=get_image_data_url("assets/apple.png"), app_url=get_image_data_url("assets/pan.png"))
        self.level_info = "<h1>placeholder</h1>"
        if self.is_web:
            import platform
            self.window = platform.window
            self.document = self.window.document
            
            self.overlay = self.document.getElementById("info-overlay")
            if self.overlay is None:
                self.overlay = self.document.createElement("div")
                self.overlay.id = "info-overlay"
                self.document.body.appendChild(self.overlay)
                
                # --- MINIMALIST STYLING ---
                s = self.overlay.style
                s.position = "absolute"
                # Center the div
                s.top = "50%"
                s.left = "50%"
                s.transform = "translate(-50%, -50%)"
                
                # Dimensions
                s.width = "70%"
                s.maxHeight = "80%"
                
                # Colors & Borders
                s.backgroundColor = "#3C3C3C"       # Dark Gray Background
                s.border = "2px solid #7D9598"      # Muted Teal Border
                s.borderRadius = "8px"              # Slight rounding
                s.boxShadow = "0 4px 15px rgba(0,0,0,0.5)"
                
                # Text Styling
                s.color = "#E0E0E0"                 # Light gray text for readability
                s.fontFamily = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
                s.fontSize = "16px"
                s.lineHeight = "1.6"
                s.padding = "25px"
                
                # Behavior
                s.display = "none"
                s.zIndex = "1000"
                s.overflowY = "auto" # Scroll if content is too long

    def show_html(self, html_content):
        if self.is_web and self.overlay is not None:
            self.overlay.innerHTML = html_content
            self.overlay.style.display = "block"
        else:
            print("--- HTML CONTENT ---")
            print(html_content)

    def hide(self):
        if self.is_web and self.overlay is not None:
            self.overlay.style.display = "none"

    def show_game_info(self):
        html_wrapper = dedent(f"""
        <div style="font-family: 'Segoe UI', sans-serif; color: {COLOR_TEXT};">
        
        <div style="border-bottom: 2px solid {COLOR_ACCENT}; margin-bottom: 15px; padding-bottom: 5px;">
            <h2 style="margin: 0; font-size: 22px; color: {COLOR_ACCENT};">Game Info</h2>
            <small style="font-size: 12px; color: #999;">Press 'E' to Close</small>
        </div>

        <div style="margin-bottom: 20px; line-height: 1.6; font-size: 16px;">
            {self.game_info}
        </div>
        </div>
        """)
        self.show_html(html_wrapper)

    def show_level_info(self):
        self.show_html(self.level_info)

    def update_game_info(self, game_info):
        self.game_info = game_info

    def update_level_info(self, level):
        self.level_info = generate_level_html(level)

def get_image_data_url(filepath):
    """
    Reads a local file (accessible to Python) and converts it 
    to a Base64 Data URL string for use in HTML <img> tags.
    """
    if not os.path.exists(filepath):
        print(f"Warning: Image not found at {filepath}")
        return ""
        
    # Determine file extension for the MIME type
    ext = filepath.split('.')[-1].lower()
    mime_type = "image/png" if ext == "png" else "image/jpeg"
    
    with open(filepath, "rb") as f:
        # Read the binary data
        data = f.read()
        # Encode to base64 string
        b64_data = base64.b64encode(data).decode('utf-8')
        
    return f"data:{mime_type};base64,{b64_data}"




# --- 2. The HTML Generator Function ---
def generate_level_html(lvl):
    """
    Converts level data into a styled HTML string with inline icons.
    """
    
    # Configuration for styling (Minimalist Palette)

    
    # Helper to create an <img> tag from a name (e.g., "Toaster" -> assets/Toaster.png)
    def make_icon_tag(name, size=20):
        # Assumes images are in 'assets/' and match the name in mapping
        # You might need to lowercase it or add .png depending on your file structure
        path = f"assets/{name.replace(' ', '_').lower()}.png" 
        src = get_image_data_url(path)
        if src:
            return f'<img src="{src}" style="width:{size}px; height:{size}px; vertical-align:middle; margin: 0 4px;">'
        return "" # Return empty if image not found

    # --- A. Prepare the Regex Logic (The "Processor") ---
    mapping = lvl.mapping or {}
    phrase_map = {v.lower(): v for v in mapping.values()}
    
    # Sort phrases by length (descending) for the single-pass greedy match
    sorted_phrases = sorted(phrase_map.keys(), key=len, reverse=True)
    
    # Compile regex once if we have phrases
    pattern = None
    if sorted_phrases:
        pattern_str = r'\b(' + '|'.join(map(re.escape, sorted_phrases)) + r')\b'
        pattern = re.compile(pattern_str, re.IGNORECASE)

    def inject_icons(text_segment):
        """Helper to apply the regex replacement to any text string."""
        if not text_segment or not pattern:
            return text_segment
            
        def replace_match(match):
            text_found = match.group(0)
            canonical_name = phrase_map[text_found.lower()]
            icon = make_icon_tag(canonical_name, size=18) # Icon size matches text
            return f'<span style="color:{COLOR_ACCENT}; font-weight:bold;">{text_found}</span>{icon}'
            
        return pattern.sub(replace_match, text_segment)

    # --- B. Split and Process Description ---
    raw_desc = (lvl.desc or "").strip()
    if "#" in raw_desc:
        raw_desc = raw_desc.split("#")[1].strip()

    # Split first line (Heading) vs Rest (Body)
    if "\n" in raw_desc:
        desc_head, desc_body = raw_desc.split("\n", 1)
    else:
        desc_head, desc_body = raw_desc, ""

    # 1. Clean HTML safety
    desc_head = desc_head.strip().replace("<", "&lt;").replace(">", "&gt;")
    desc_body = desc_body.strip().replace("<", "&lt;").replace(">", "&gt;")

    # 2. Inject Icons into BOTH parts <--- UPDATED HERE
    desc_head = inject_icons(desc_head)
    desc_body = inject_icons(desc_body)

    # 3. Format body newlines
    desc_body = desc_body.replace("\n", "<br>")

    # --- C. Build Columns (Items & Appliances) ---
    items_html = ""
    appliances_html = ""

    for k, v in mapping.items():
        icon = make_icon_tag(v, size=24)
        entry_html = (
            f'<div style="margin-bottom: 8px; display: flex; align-items: center;">'
            f'<span style="color:{COLOR_ACCENT}; font-weight:bold; min-width: 30px;">{k}</span>'
            f'{icon}'
            f'<span>{v}</span>'
            f'</div>'
        )
        if k.isdigit():
            items_html += entry_html
        elif k.isalpha():
            appliances_html += entry_html

    # --- C. Assemble Final HTML ---
    final_html = f"""
    <div style="font-family: 'Segoe UI', sans-serif; color: {COLOR_TEXT};">
        
        <div style="border-bottom: 2px solid {COLOR_ACCENT}; margin-bottom: 15px; padding-bottom: 5px;">
            <h2 style="margin: 0; font-size: 22px; color: {COLOR_ACCENT};">Level Info</h2>
            <small style="font-size: 12px; color: #999;">Press 'E' to Close</small>
        </div>

        <div style="margin-bottom: 20px;">
            <h3 style="margin: 0 0 10px 0; color: #FFF; font-size: 18px;">
                {desc_head}
            </h3>
            
            <div style="line-height: 1.6; font-size: 16px; color: #CCC;">
                {desc_body}
            </div>
        </div>

        <div style="display: flex; gap: 20px; background: rgba(0,0,0,0.2); padding: 15px; border-radius: 8px;">
            
            <div style="flex: 1;">
                <h3 style="margin-top: 0; color: {COLOR_ACCENT}; border-bottom: 1px solid #555;">Items</h3>
                {items_html if items_html else "<i>None</i>"}
            </div>

            <div style="flex: 1;">
                <h3 style="margin-top: 0; color: {COLOR_ACCENT}; border-bottom: 1px solid #555;">Appliances</h3>
                {appliances_html if appliances_html else "<i>None</i>"}
            </div>
            
        </div>
    </div>
    """
    
    return final_html

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
        font = pygame.font.SysFont(None, max(10, tile_size // 5))
        head_font = pygame.font.SysFont(None, max(14, tile_size // 3), bold=True)
    except Exception:
        return

    x_pad = 24
    y_pad = 24
    text_w = width - 2 * x_pad

    # Title
    screen.blit(head_font.render("Game Info (Press E to EXIT)", True, (245, 245, 245)), (x_pad, y_pad))
    y_cursor = y_pad + head_font.get_height() + 12

    

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
        info_font = pygame.font.SysFont(None, max(12, tile_size // 4))
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
    right_x1 = x_pad + desc_w + col_gap
    try:
        colors = _load_appliance_colors()
    except Exception:
        colors = {}

    # Items
    y_m = y_pad
    screen.blit(head_font.render("Items", True, (245, 245, 245)), (right_x1, y_m))
    y_m += head_font.get_height() + 8
    for k, v in (lvl.mapping or {}).items():
        if k.isdigit():
            line = f"• {k}: {v}"
            screen.blit(
                info_font.render(line, True, (220, 220, 220)), (right_x1 + 6, y_m)
            )
            y_m += info_font.get_height() + 6

    # Appliances
    y_m = y_pad
    right_x2 = x_pad + 1.25*desc_w + col_gap
    screen.blit(head_font.render("Appliances", True, (245, 245, 245)), (right_x2, y_m))
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
            screen.blit(info_font.render(line, True, text_color), (right_x2 + 6, y_m))
            y_m += info_font.get_height() + 6
