CookEnv — simple cooking grid-world (planning benchmark)

Overview
--------
CookEnv is a minimal, extensible grid-world implemented in Python and pygame. It models a small kitchen domain with ingredient dispensers, appliances (pans, ovens, etc.), and a single player agent. The environment is designed to serve as a simple planning benchmark: levels describe maps, operations (recipes), goals, and human-readable mappings.

Key concepts
------------
- Grid world: The world is a rectangular grid of Block objects. Each tile may be a Wall, Floor, Dispenser (numeric ingredient provider) or Appliance (lettered device that can run operations).
- Player: A single controllable agent with an orientation, single-slot inventory, and a game-time counter. Player interacts with the world using keyboard controls.
- Operations: Each Appliance can be configured with Operation objects that specify input ingredient ids, a product id, and a duration (time steps). Appliances start operations when their contents match the required ingredients and produce the product after the specified time.
- Levels: Each level is a folder containing a small set of files (see Level format).

Project layout
--------------
- `game.py` — main Game class, pygame loop, level loading helper, HUD and info overlay.
- `blocks.py` — Block base class and concrete block types: `Wall`, `Floor`, `Dispenser`, `Appliance`. Also contains asset loading helpers and appliance color parsing.
- `player.py` — Player class (movement, orientation, inventory, drawing).
- `states.py` — `Operation` dataclass and `Level` loader (parses level folders).
- `levels/` — example level folders (each level has `maze.txt`, `recipe.txt`, `mapping.txt`, and `desc.txt`).
- `assets/` — optional image assets (floor.png, wall.png, appliance_X.png, dispenser_overlay.png, player sprites) and `appliance_colors.csv` for appliance-specific colors.

Level format
------------
Each level is a folder with the following files:
- `desc.txt` — human-readable textual description of the recipe/goal (shown in the info overlay).
- `mapping.txt` — human-readable mapping of item ids and appliance letters to names, e.g. `1 = butter` and `A = pan`.
- `maze.txt` — ASCII map; characters used:
  - `#` wall
  - `.` floor
  - digits `1..9` — dispensers that produce that ingredient id
  - letters `A..Z` — appliances
  - `^`, `v`, `<`, `>` — player start location and orientation (will be replaced with `.` when loaded)
- `recipe.txt` — operation definitions and `Goal: N`. Example lines:
  - `1 -> A = 3 (3)`  (ingredient 1 into appliance A produces item 3 after 3 steps)
  - `2, 3 -> A = 4 (5)`
  - `Goal: 4` — the goal item id the player should obtain to finish the level

Controls
--------

- Movement: WASD or arrow keys. Changing orientation without moving is allowed.
- Interact: SPACE — pick up from dispenser or appliance, or place an item into an appliance.
- Pass time: Q — advance game time without moving (appliances tick).
- Toggle info overlay: E — shows the textual `desc.txt` and `mapping.txt` in a formatted overlay. Press again to return to the game.

Visuals and assets
------------------

- If `pygame` is available, the game renders a graphical window and draws tiles using assets in the `assets/` folder when available. If assets are missing, the game falls back to color fills and geometric drawings.
- `appliance_colors.csv` in `assets/` can define RGB colors per appliance (e.g. `A, 206, 140, 73`). These colors are used for operation progress fills and for coloring appliance names in the info overlay.

Extensibility and development notes
-----------------------------------

- The code is modular: add new Block subclasses in `blocks.py` and update `Game.from_text_map` mapping if you want new tile types.
- `Level` parsing is intentionally tolerant: malformed lines are skipped rather than crashing. If you need stricter validation, we can add schema checks.
- The UI overlay is text-wrapped and shows description and mapping in separate columns. For long descriptions we may want to add vertical scrolling.

Running the game
----------------

1. Install dependencies (pygame):

```bash
python3 -m pip install pygame
```

2. Run the demo level:

```bash
python3 game.py
```

(If you prefer a fixed tile size or to disable automatic scaling to the display, call `Game.run_pygame(scale_to_display=False)` from a small wrapper.)

Next improvements you might want
------------------------------

- Add vertical scrolling for the info overlay.
- Add item icons in the HUD and overlay when images are available.
- Add keyboard shortcuts for restarting the level, toggling debug overlays, or stepping time.
- Improve recipe parsing and validation and provide a `build_level.py` helper for level authors.

Contributing
------------

This is a small educational project — contributions are welcome. Please open a PR with small, focused changes and include a short description of the behavioral change and a screenshot if applicable.

License
-------

Use as you wish for experiments and teaching. No warranty provided.
