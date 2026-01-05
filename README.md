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
- `assets/` — image assets for sprites, appliances and ingredients

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
  - `1 ! 10` — Dispenser 1 stops giving ingredients after 10 steps
  - `Goal: 4` — the goal item id the player should obtain to finish the level

Pygame Controls
--------

- Movement: WASD or arrow keys. Changing orientation without moving is allowed. 
- Interact: SPACE — pick up from dispenser or appliance, or place an item into an appliance.
- Pass time: Q — advance game time without moving (appliances tick).
- Toggle info overlay: E — shows the textual `desc.txt` and `mapping.txt` in a formatted overlay. Press again to return to the game.
- Drop item: R - deletes the contents of your inventory to free it.

Installing dependencies
----------------

Run 
```bash
pip install -r requirements.txt
```

Running the game with Pygbag
----------------

1. Compile the game using Pygbag:

```bash
python -m pygbag main.py
```

2. Open the game in the browser (http://localhost:8000/)

Alternative: try the [hosted experiment](skipyas0.github.io/cookenv-benchmark).

Text-mode Controls
----------------
- Interact: Write a command in the format ```interact (x,y)```, where the coordinates $(x, y)$ contain a valid object. The player automatically navigates to the object and interacts with it. If the object is busy, time is skipped automatically.
- Drop: Write the ```drop``` command to empty your inventory.
- Skip: Explicitly skip game time by writing ```skip```.

Running the game in text-mode
----------------
Run the ```game.py``` file like this.
```bash
python game.py
```

Running the benchmark
----------------
1. Put your OpenAI API key in a ```.env``` file, like this:
```
OPENAI_API_KEY=sk-proj-XXXXXXXX
```

2. Run the ```benchmark.py``` file:
```
python benchmark_batch.py --model gpt-5-mini --instances 5 --steps 20
```
You can use the ```--mock``` argument to run the benchmark in debug mode (no LLM calls).

License
-------

Use as you wish for experiments and teaching. No warranty provided.

Credits
-------

icons by [icons8](https://icons8.com/)

game assets by [kenney](https://kenney.nl)