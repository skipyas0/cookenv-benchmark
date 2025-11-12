CookEnv — simple cooking grid-world (planning benchmark)

Acknowledgements
- main game assets are taken from https://kenney.nl 


Overview
--------
CookEnv is a minimal, extensible grid-world implemented in Python and pygame. It models a small kitchen domain with ingredient dispensers, appliances (pans, ovens, etc.), and a single player agent. The environment is designed to serve as a simple planning benchmark: levels describe maps, operations (recipes), goals, and human-readable mappings.

Key concepts
------------
- Grid world: The world is a rectangular grid of Block objects. Each tile may be a Wall, Floor, Dispenser (numeric ingredient provider) or Appliance (lettered device that can run operations).
- Player: A single controllable agent with an orientation, single-slot inventory, and a game-time counter. Player interacts with the world using keyboard controls.
- Operations: Each Appliance can be configured with Operation objects that specify input ingredient ids, a product id, and a duration (time steps). Appliances start operations when their contents match the required ingredients and produce the product after the specified time.
- Levels: Each level is a folder containing a small set of files (see Level format).

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
