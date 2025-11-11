"""Player representation for the cookenv game.

Contains the Player class which tracks tile coordinates, orientation and
`game_time` counter.
"""

from __future__ import annotations

from typing import List

try:
	import pygame
	_PYGAME_AVAILABLE = True
except Exception:
	pygame = None  # type: ignore
	_PYGAME_AVAILABLE = False

from blocks import Block  # type: ignore

# simple asset cache for player sprites
_PLAYER_ASSETS: dict[str, "pygame.Surface"] = {}


def _load_player_asset(name: str):
	if not _PYGAME_AVAILABLE:
		raise RuntimeError("pygame required to load assets")
	if name in _PLAYER_ASSETS:
		return _PLAYER_ASSETS[name]
	from pathlib import Path

	assets_dir = Path(__file__).parent / "assets"
	path = assets_dir / name
	if not path.exists():
		raise FileNotFoundError(path)
	surf = pygame.image.load(str(path)).convert_alpha()
	_PLAYER_ASSETS[name] = surf
	return surf


class Player:
	"""Simple player with integer tile coordinates and a game_time counter.

	Responsibility moved here:
	- changing orientation (set_orientation)
	- attempting movement (try_move)
	- drawing itself (draw)
	"""

	def __init__(self, x: int, y: int) -> None:
		self.x = x
		self.y = y
		self.game_time = 0
		# orientation is one of: 'up', 'down', 'left', 'right'
		self.orientation = "down"

	@property
	def char(self) -> str:
		return {"up": "^", "down": "v", "left": "<", "right": ">"}[self.orientation]

	def set_orientation(self, orientation: str) -> None:
		"""Set player's orientation. Does not change game_time."""
		if orientation not in ("up", "down", "left", "right"):
			raise ValueError("invalid orientation")
		self.orientation = orientation

	def try_move(self, dx: int, dy: int, grid: List[List[Block]]) -> bool:
		"""Attempt to move by (dx,dy) on the provided grid.

		If the target tile is walkable and inside bounds, update position,
		increment game_time, print it, and return True. Otherwise return False.
		"""
		new_x = self.x + dx
		new_y = self.y + dy
		if 0 <= new_y < len(grid) and 0 <= new_x < len(grid[0]):
			target = grid[new_y][new_x]
			if target.walkable:
				self.x = new_x
				self.y = new_y
				self.game_time += 1
				#print(f"game_time: {self.game_time}")
				return True
		return False

	def pass_time(self) -> None:
		"""Advance game time by 1 without moving."""
		self.game_time += 1
		print(f"game_time: {self.game_time}")

	def draw(self, surface, tile_size: int) -> None:
		"""Draw the player as a red circle with a directional arrow inside.

		Requires pygame to be available.
		"""
		if not _PYGAME_AVAILABLE:
			raise RuntimeError("pygame is required for drawing the player")

		# try to draw sprite asset for player
		try:
			name = {
				"up": "player_back.png",
				"down": "player_front.png",
				"left": "player_left.png",
				"right": "player_right.png",
			}[self.orientation]
			img = _load_player_asset(name)
			img_s = pygame.transform.smoothscale(img, (tile_size, tile_size))
			surface.blit(img_s, (self.x * tile_size, self.y * tile_size))
			return
		except Exception:
			pass

		# fallback: draw circle + arrow as before
		px = self.x * tile_size + tile_size // 2
		py = self.y * tile_size + tile_size // 2

		# draw directional arrow inside player circle
		arrow_size = max(4, tile_size // 4)
		if self.orientation == "up":
			pts = [
				(px, py - arrow_size),
				(px - arrow_size, py + arrow_size),
				(px + arrow_size, py + arrow_size),
			]
		elif self.orientation == "down":
			pts = [
				(px, py + arrow_size),
				(px - arrow_size, py - arrow_size),
				(px + arrow_size, py - arrow_size),
			]
		elif self.orientation == "left":
			pts = [
				(px - arrow_size, py),
				(px + arrow_size, py - arrow_size),
				(px + arrow_size, py + arrow_size),
			]
		else:  # right
			pts = [
				(px + arrow_size, py),
				(px - arrow_size, py - arrow_size),
				(px - arrow_size, py + arrow_size),
			]
		pygame.draw.polygon(surface, (20, 20, 20), pts)

		# inventory overlay intentionally omitted; HUD displays inventory now

	# inventory: can hold a single integer item or None
	inventory: int | None = None

	def interact(self, grid: List[List[Block]]) -> bool:
		"""Interact with the tile the player is facing using the Space key.

		- If facing a Dispenser and inventory is empty, take one item (dispenser.dispense()).
		- If facing an Appliance and inventory has an item, place it into appliance.contents.

		Returns True if an interaction modified state, False otherwise.
		"""
		dx = dy = 0
		if self.orientation == "up":
			dy = -1
		elif self.orientation == "down":
			dy = 1
		elif self.orientation == "left":
			dx = -1
		else:
			dx = 1

		tx = self.x + dx
		ty = self.y + dy
		if not (0 <= ty < len(grid) and 0 <= tx < len(grid[0])):
			return False

		target = grid[ty][tx]
		# pick up from dispenser
		if hasattr(target, "dispense") and self.inventory is None:
			try:
				item = target.dispense()  # type: ignore[attr-defined]
				if(item == -1):
					print(f"Dispenser at ({tx},{ty}) is not available anymore")
					return False;
				self.inventory = item
				print(f"picked up item {item} from dispenser at ({tx},{ty})")
				return True
			except Exception:
				return False

		# pick up from appliance if it has contents and player inventory is empty
		if hasattr(target, "contents") and self.inventory is None and getattr(target, "contents", None):
			try:
				# take the first item
				item = target.contents.pop(0)  # type: ignore[attr-defined]
				self.inventory = item
				print(f"picked up item {item} from appliance at ({tx},{ty})")
				return True
			except Exception:
				return False

		# place into appliance
		if isinstance(target, type) and False:
			# defensive: should not happen
			return False

		if hasattr(target, "contents") and self.inventory is not None:
			try:
				# limit appliance inventory size to 4
				if len(target.contents) >= 4:  # type: ignore[attr-defined]
					print(f"appliance at ({tx},{ty}) is full")
					return False
				if target.active_operation is not None:
					print(f"appliance at ({tx},{ty}) is busy")
					return False

				target.contents.append(self.inventory)  # type: ignore[attr-defined]
				print(f"placed item {self.inventory} into appliance at ({tx},{ty})")
				# after placing, attempt to start an operation if possible
				try:
					target.try_start_operations()  # type: ignore[attr-defined]
				except Exception:
					pass
				self.inventory = None
				return True
			except Exception:
				return False

		return False
