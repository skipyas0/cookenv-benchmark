"""Operation definitions for appliances."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List
from pathlib import Path
from typing import Dict, Optional
import re


@dataclass
class Operation:
    """Defines an appliance operation.

    Attributes:
        ingredients: list[int] -- list of item ids required (multiset)
        appliance: str -- appliance id character this operation belongs to
        product: int -- resulting item id
        time: int -- number of game steps the appliance is blocked for
    """

    ingredients: List[int]
    appliance: str
    product: int
    time: int

@dataclass
class DispenserTimeLimit:
    dispenser: int
    expTime: int


@dataclass
class Level:
    """Container for level files and parsed content.

    Loads the following files from a level folder:
    - desc.txt       : textual description
    - mapping.txt    : mapping of item/appliance ids to human names
    - maze.txt       : textual map (with start marker ^ v < >)
    - recipe.txt     : operations and goal
    """

    path: Path
    desc: str
    mapping: Dict[str, str]
    maze_lines: List[str]
    operations: List[Operation]
    goal: Optional[int]
    start_pos: tuple[int, int] | None = None
    start_orientation: str | None = None

    @classmethod
    def load_from_folder(cls, folder: str | Path) -> "Level":
        p = Path(folder)
        if not p.exists() or not p.is_dir():
            raise FileNotFoundError(f"Level folder not found: {p}")

        desc_file = p / "desc.txt"
        map_file = p / "mapping.txt"
        maze_file = p / "maze.txt"
        recipe_file = p / "recipe.txt"

        if not maze_file.exists() or not recipe_file.exists():
            raise FileNotFoundError("Level must contain maze.txt and recipe.txt")

        # read description
        desc = ""
        if desc_file.exists():
            try:
                desc = desc_file.read_text(encoding="utf-8")
            except Exception:
                desc = ""

        # read mapping (simple key = value lines)
        mapping: Dict[str, str] = {}
        if map_file.exists():
            try:
                for raw in map_file.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        mapping[k.strip()] = v.strip()
            except Exception:
                mapping = {}

        # read maze and detect start marker
        maze_lines: List[str] = []
        start_pos = None
        start_orientation = None
        markers = {"^": "up", "v": "down", "<": "left", ">": "right"}
        with maze_file.open("r", encoding="utf-8") as fh:
            for y, raw in enumerate(fh.readlines()):
                row = raw.rstrip("\n")
                for idx, ch in enumerate(row):
                    if ch in markers and start_pos is None:
                        start_pos = (idx, y)
                        start_orientation = markers[ch]
                        row = row[:idx] + "." + row[idx+1:]
                        break
                maze_lines.append(row)

        # parse recipe file into operations and goal
        ops: List[Operation|DispenserTimeLimit] = []
        goal: Optional[int] = None
        with recipe_file.open("r", encoding="utf-8") as fh:
            for raw in fh.readlines():
                line = raw.strip()
                if not line:
                    continue
                if line.lower().startswith("goal:"):
                    try:
                        goal = int(line.split(":", 1)[1].strip())
                    except Exception:
                        goal = None
                    continue
                if "->" in line:
                    left, right = line.split("->", 1)
                    ingredients = [int(s.strip()) for s in left.split(",") if s.strip()]
                    right = right.strip()
                    m = re.match(r"^([A-Za-z])\s*=\s*(\d+)\s*\((\d+)\)$", right)
                    if not m:
                        parts = right.split("=")
                        if len(parts) >= 2:
                            app = parts[0].strip()
                            prod_part = parts[1].strip()
                            try:
                                prod = int(prod_part.split("(")[0].strip())
                                time = int(prod_part.split("(")[1].rstrip(")").strip())
                            except Exception:
                                raise RuntimeError(f"Incorrect recipte file format {recipe_file}. Line {line}")
                        else:
                            continue
                    else:
                        app = m.group(1)
                        prod = int(m.group(2))
                        time = int(m.group(3))
                    ops.append(Operation(ingredients, app, prod, time))
                if "!" in line:
                    disp, time = line.split("!", 1)
                    disp= disp.strip()
                    time=time.strip()
                    if not disp.isdigit() or not time.isdigit():
                        raise RuntimeError(f"Incorrect recipte file format {recipe_file}. Line {line}")
                    ops.append(DispenserTimeLimit(int(disp),int(time)))
                    
                    

        return cls(path=p, desc=desc, mapping=mapping, maze_lines=maze_lines, operations=ops, goal=goal, start_pos=start_pos, start_orientation=start_orientation)
