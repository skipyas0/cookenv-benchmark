"""Block types for the cookenv game.

This module defines Block, Wall, Floor, Dispenser and Appliance used by
`game.py`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple, List
from collections import Counter
from states import Operation  # type: ignore

try:
	import pygame
	_PYGAME_AVAILABLE = True
except Exception:
	pygame = None  # type: ignore
	_PYGAME_AVAILABLE = False

# asset cache: original loaded surfaces (not scaled)
_ASSET_CACHE: dict[str, "pygame.Surface"] = {}

# cache for appliance colors loaded from CSV
_APPLIANCE_COLORS: dict[str, Tuple[int, int, int]] | None = None


def _load_asset(name: str):
	"""Load an asset from the assets/ directory next to this file.

	Returns a pygame.Surface or raises if not found / pygame unavailable.
	"""
	if not _PYGAME_AVAILABLE:
		raise RuntimeError("pygame required to load assets")
	if name in _ASSET_CACHE:
		return _ASSET_CACHE[name]
	from pathlib import Path

	assets_dir = Path(__file__).parent / "assets"
	path = assets_dir / name
	if not path.exists():
		raise FileNotFoundError(f"asset not found: {path}")
	surf = pygame.image.load(str(path)).convert_alpha()
	_ASSET_CACHE[name] = surf
	return surf


def _load_appliance_colors() -> dict[str, Tuple[int, int, int]]:
	"""Load appliance_colors.csv from the assets directory and return a map
	from appliance id (single letter) to (r,g,b) tuples.
	"""
	global _APPLIANCE_COLORS
	if _APPLIANCE_COLORS is not None:
		return _APPLIANCE_COLORS
	from pathlib import Path

	assets_dir = Path(__file__).parent / "assets"
	csv_path = assets_dir / "appliance_colors.csv"
	colors: dict[str, Tuple[int, int, int]] = {}
	if not csv_path.exists():
		_APPLIANCE_COLORS = colors
		return colors
	try:
		with csv_path.open("r", encoding="utf-8") as fh:
			for raw in fh.readlines():
				line = raw.strip()
				if not line or line.startswith("#"):
					continue
				parts = [p.strip() for p in line.split(",")]
				if len(parts) >= 4:
					key = parts[0]
					try:
						r = int(parts[1])
						g = int(parts[2])
						b = int(parts[3])
						colors[key] = (r, g, b)
					except Exception:
						continue
	except Exception:
		# any error: return empty mapping
		_APPLIANCE_COLORS = {}
		return _APPLIANCE_COLORS

	_APPLIANCE_COLORS = colors
	return colors


class Block(ABC):
	"""Abstract building block for the grid.

	Attributes:
		graphics: tuple -- RGB tuple used for pygame drawing
		char: str -- textual char for ascii rendering
		walkable: bool -- whether agents can walk on this block
	"""

	graphics: Tuple[int, int, int] = (128, 128, 128)
	char: str = "#"
	walkable: bool = False

	def __init__(self) -> None:
		self.graphics = self.__class__.graphics
		self.walkable = self.__class__.walkable
		self.char = self.__class__.char

	@abstractmethod
	def draw(self, surface, x: int, y: int, tile_size: int) -> None:
		if not _PYGAME_AVAILABLE:
			raise RuntimeError("pygame is required for graphical drawing")
		rect = pygame.Rect(x * tile_size, y * tile_size, tile_size, tile_size)
		surface.fill(self.graphics, rect)


class Wall(Block):
	graphics = (0, 0, 0)
	walkable = False
	char = "#"

	def draw(self, surface, x: int, y: int, tile_size: int) -> None:
		if _PYGAME_AVAILABLE:
			# try to draw an asset
			try:
				img = _load_asset("wall.png")
				img_s = pygame.transform.smoothscale(img, (tile_size, tile_size))
				surface.blit(img_s, (x * tile_size, y * tile_size))
				return
			except Exception:
				pass
		# fallback to color fill
		if not _PYGAME_AVAILABLE:
			raise RuntimeError("pygame is required for graphical drawing")
		rect = pygame.Rect(x * tile_size, y * tile_size, tile_size, tile_size)
		surface.fill(self.graphics, rect)


class Floor(Block):
	graphics = (255, 255, 255)
	walkable = True
	char = "."

	def draw(self, surface, x: int, y: int, tile_size: int) -> None:
		if _PYGAME_AVAILABLE:
			try:
				img = _load_asset("floor.png")
				img_s = pygame.transform.smoothscale(img, (tile_size, tile_size))
				surface.blit(img_s, (x * tile_size, y * tile_size))
				return
			except Exception:
				pass
		# fallback
		if not _PYGAME_AVAILABLE:
			raise RuntimeError("pygame is required for graphical drawing")
		rect = pygame.Rect(x * tile_size, y * tile_size, tile_size, tile_size)
		surface.fill(self.graphics, rect)


class Dispenser(Block):
	"""Ingredient dispenser wall that shows a numeric id."""

	walkable = False

	def __init__(self, id_char: str):
		self.id = id_char
		self.graphics = (160, 220, 160)
		self.char = id_char
		self.walkable = False

	def draw(self, surface, x: int, y: int, tile_size: int) -> None:
		# draw base (use wall asset as base)
		if _PYGAME_AVAILABLE:
			try:
				base = _load_asset("wall.png")
				base_s = pygame.transform.smoothscale(base, (tile_size, tile_size))
				surface.blit(base_s, (x * tile_size, y * tile_size))
				# overlay dispenser icon if available
				try:
					over = _load_asset("dispenser_overlay.png")
					over_s = pygame.transform.smoothscale(over, (tile_size, tile_size))
					surface.blit(over_s, (x * tile_size, y * tile_size))
				except Exception:
					pass
			except Exception:
				# fallback to color base
				rect = pygame.Rect(x * tile_size, y * tile_size, tile_size, tile_size)
				surface.fill(self.graphics, rect)
		else:
			raise RuntimeError("pygame is required for graphical drawing")

		# draw the id text on top (number)
		font = pygame.font.SysFont(None, max(12, tile_size // 2))
		r, g, b = self.graphics
		color = (156, 187, 189)
		surf = font.render(self.id, True, color)
		sw, sh = surf.get_size()
		sx = x * tile_size + (tile_size - sw) // 2
		sy = y * tile_size + (tile_size - sh) // 2
		surface.blit(surf, (sx, sy))

		


	def dispense(self) -> int:
		"""Return the integer id of the dispenser's item.

		For now dispensers provide an infinite supply of their id.
		"""
		try:
			return int(self.id)
		except Exception:
			# fallback: return 0 if id not numeric
			return 0


class Appliance(Block):
	"""Appliance wall that shows a letter id (A, B, C...)."""

	walkable = False

	def __init__(self, id_char: str):
		self.id = id_char
		self.graphics = (160, 200, 240)
		self.char = id_char
		self.walkable = False
		# appliance can hold multiple integer items
		self.contents: list[int] = []

		# operation handling
		self.operations: List[Operation] = []
		# remaining blocked time in game steps (0 == not blocked)
		self.remaining_time: int = 0
		# currently active operation (None when idle)
		self.active_operation: Operation | None = None

		try:
			colors = _load_appliance_colors()
			ap_color = colors.get(self.id)
		except Exception:
			ap_color = None
		if ap_color is not None:
			r, g, b = ap_color
			# clamp values
			r = max(0, min(255, int(r)))
			g = max(0, min(255, int(g)))
			b = max(0, min(255, int(b)))
			self.fill_color = (r, g, b)
		else:
			# fallback: darker shade of the appliance color
			r, g, b = self.graphics
			self.fill_color = (max(0, int(r * 0.6)), max(0, int(g * 0.6)), max(0, int(b * 0.6)))
		
	def draw(self, surface, x: int, y: int, tile_size: int) -> None:
		# appliance base asset
		if _PYGAME_AVAILABLE:
			try:
				imgname = f"appliance_{self.id}.png"
				img = _load_asset(imgname)
				img_s = pygame.transform.smoothscale(img, (tile_size, tile_size))
				surface.blit(img_s, (x * tile_size, y * tile_size))
				# if active operation draw progress fill over base
			except Exception:
				# fallback to color fill
				rect = pygame.Rect(x * tile_size, y * tile_size, tile_size, tile_size)
				surface.fill(self.graphics, rect)
		else:
			raise RuntimeError("pygame is required for graphical drawing")

		# draw operation progress fill if an operation is active
		if self.active_operation is not None and self.active_operation.time > 0:
			op_time = self.active_operation.time
			elapsed = op_time - self.remaining_time
			if elapsed < 0:
				elapsed = 0
			progress = elapsed / op_time
			fill_h = int(tile_size * progress)
			if fill_h > 0:
				# choose a color for the fill: prefer CSV-specified appliance color
				fill_rect = pygame.Rect(x * tile_size, y * tile_size + tile_size - fill_h, tile_size, fill_h)
				surface.fill(self.fill_color, fill_rect)

		font = pygame.font.SysFont(None, max(8, tile_size // 3))
		r, g, b = self.graphics
		color = (60, 60, 60)
		surf = font.render(self.id, True, color)
		sw, sh = surf.get_size()
		sx = x * tile_size + (tile_size - sw) // 2
		sy = y * tile_size + (tile_size - sh) // 1.8
		surface.blit(surf, (sx, sy))

		# draw appliance contents (small numbers) on the top of the tile
		if hasattr(self, "contents") and self.contents:
			# show up to 4 items, space them horizontally
			max_show = min(4, len(self.contents))
			small_font = pygame.font.SysFont(None, max(10, tile_size // 5))
			for i in range(max_show):
				text = str(self.contents[i])
				surf2 = small_font.render(text, True, self.fill_color)
				sw2, sh2 = surf2.get_size()
				# compute positions: small padding from top, distribute across width
				pad_x = (i + 1) * tile_size // (max_show + 1) - sw2 // 2
				sx2 = x * tile_size + pad_x
				sy2 = y * tile_size + 2
				surface.blit(surf2, (sx2, sy2))

	def add_operation(self, op: Operation) -> None:
		"""Register an Operation that this appliance can perform."""
		self.operations.append(op)
		print(f"add operation {op.appliance}({op.ingredients}) -> {op.product} ({op.time})")

	def is_blocked(self) -> bool:
		return self.remaining_time > 0

	def tick(self) -> None:
		"""Advance the appliance by one game step; decrement remaining_time."""
		if self.remaining_time > 0:
			self.remaining_time -= 1
			# if we've finished an active operation, finalize it
			if self.remaining_time == 0 and self.active_operation is not None:
				# place the product into contents
				self.contents = [self.active_operation.product]
				print(f"appliance {self.id} finished operation -> product {self.active_operation.product}")
				self.active_operation = None

	def try_start_operations(self) -> bool:
		"""If the appliance inventory exactly matches any operation's ingredients,
		start that operation: remove ingredients, set remaining_time, and place product.
		Returns True if an operation was started.
		"""
		if self.is_blocked():
			return False

		# compare multisets
		contents_counter = Counter(self.contents)
		for op in self.operations:
			if Counter(op.ingredients) == contents_counter:
				# start operation: remove ingredients and set active operation; product placed when finished
				self.active_operation = op
				self.remaining_time = op.time
				# remove ingredients from visible contents
				self.contents = []
				print(f"appliance {self.id} started operation -> will produce {op.product} in {op.time} steps")
				return True
		return False