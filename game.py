"""Simple grid-world for a cooking planning benchmark.

Defines a minimal Block abstract base class and a Game container that
holds a 2D grid of Blocks and can draw it to the console.
"""

from __future__ import annotations

from typing import List, Sequence

try:
	import pygame

	_PYGAME_AVAILABLE = True
except Exception:
	pygame = None  # type: ignore
	_PYGAME_AVAILABLE = False

from blocks import Block, Wall, Floor, Dispenser, Appliance, _load_appliance_colors  # type: ignore
from player import Player  # type: ignore
from states import Level
from pathlib import Path
from datetime import datetime
import asyncio
import sys
import time
import json
if sys.platform == "emscripten":
	import js

async def send_score(username, level, game_time, info_presses, time_spent):
	"""Send a score to the configured Google Apps Script endpoint.

	This function awaits the JS fetch Promise so it doesn't start a
	synchronous/blocking network operation that could hang the event loop.
	It is defensive and catches exceptions so network errors don't stop play.
	"""
	time_stamp = datetime.utcnow().isoformat()
	sheets_link = "https://script.google.com/macros/s/AKfycby9VqXkvxME3J2WlFa6nVfR8Sj4NgtRujfYBgUJjxlBCUI-GOYalnK5TgB8en2If4_k/exec"
	payload = {
		"username": username,
		"level": str(level),
		"gametime": game_time,
		"infopresses": info_presses,
		"timespent": time_spent,
		"time": time_stamp,
	}
	#print(payload)
	
	payload.update({"token": "abc123xyz"})
	js_code = f"""
	fetch("{sheets_link}", {{
		method: "POST",
		mode: "no-cors",  // ✅ avoids preflight rejections
		headers: {{ "Content-Type": "application/json" }},
		body: {json.dumps(json.dumps(payload))}
	}})
	.then(r => console.log("send_score OK", r))
	.catch(e => console.error("send_score failed", e));
	"""
	js.eval(js_code)
	js.console.log("send_score() invoked")


def list_levels_dir(levels_dir: str = "levels") -> list[str]:
	"""Return a sorted list of level folder paths inside `levels_dir`.

	Sorting is natural lexicographic so level1, level2, ... order is preserved.
	"""
	p = Path(levels_dir)
	if not p.exists() or not p.is_dir():
		return []
	entries = [str(x) for x in p.iterdir() if x.is_dir()]
	# sort by name
	entries.sort()
	return entries


async def prompt_username_pygame(tile_size: int = 128) -> str:
	"""Show a simple pygame text-input overlay and return the entered username.

	This function is async so it yields to the event loop (needed for pygbag).
	"""
	if not _PYGAME_AVAILABLE:
		return "player"
	try:
		font = pygame.font.SysFont(None, max(18, tile_size // 4))
	except Exception:
		font = None

	username = ""
	active = True
	clock = pygame.time.Clock()
	# draw loop
	while active:
		for ev in pygame.event.get():
			if ev.type == pygame.QUIT:
				active = False
				break
			if ev.type == pygame.KEYDOWN:
				if ev.key == pygame.K_RETURN:
					active = False
					break
				elif ev.key == pygame.K_BACKSPACE:
					username = username[:-1]
				else:
					try:
						ch = ev.unicode
						if ch and ch.isprintable():
							username += ch
					except Exception:
						pass

		# render overlay
		try:
			w, h = pygame.display.get_surface().get_size()
			over = pygame.Surface((w, h), pygame.SRCALPHA)
			over.fill((0, 0, 0, 180))
			pygame.display.get_surface().blit(over, (0, 0))
			if font is not None:
				prompt = "Enter username: " + username
				surf = font.render(prompt, True, (240, 240, 240))
				pygame.display.get_surface().blit(
					surf, ((w - surf.get_width()) // 2, h // 2)
				)
			pygame.display.flip()
		except Exception:
			pass

		await asyncio.sleep(0.02)
		clock.tick(30)

	return username or "player"


async def play_levels(start_folder: str | None = None, use_text: bool = True) -> None:
	"""Play all levels starting from the lowest available.

	If start_folder is provided and present in the levels list it will be used
	as the first level; otherwise we start from the first sorted level.
	"""
	levels = list_levels_dir()
	if not levels:
		print("No levels found in 'levels/'")
		return

	# find starting index
	idx = 0
	if start_folder:
		try:
			idx = levels.index(start_folder)
		except ValueError:
			idx = 0

	# ask for username
	username = "text_player"
	if not use_text:
		try:
			username = await prompt_username_pygame()
		except Exception:
			username = "unknown_player"

	# ensure levels dir exists
	Path("levels").mkdir(parents=True, exist_ok=True)
	score_file = Path("levels") / f"scores-{datetime.now().isoformat()}.txt"
	while idx < len(levels):
		lvl_path = levels[idx]
		print(f"Loading level: {lvl_path}")
		lvl = Level.load_from_folder(lvl_path)
		game = Game.from_level(lvl)

		t0 = time.time()
		if use_text:
			completed, game_time, choice, info_presses = game.run_text()
		else:
			completed, game_time, choice, info_presses = await game.run_pygame()
		time_spent = time.time() - t0

		if sys.platform == "emscripten":
			await send_score(
				username, lvl.path, game_time if completed else -1, info_presses, time_spent
			)
			await asyncio.sleep(0)
		else:
			with open(score_file, "a+") as f:
				f.write(f"{username}, {lvl.path}, {game_time if completed else -1}, {info_presses}, {time_spent}")
				 
		# interpret choice
		if choice == "repeat":
			print(f"Repeating level {lvl_path}")
			continue
		if choice == "continue":
			idx += 1
			if idx >= len(levels):
				print("No more levels. Exiting.")
				print()
				break
			print(f"Continuing to next level: {levels[idx]}")
			continue
		# exit or unknown -> break
		print("Exiting level play")
		break


class Game:
	"""Container for a grid of Block instances.

	The grid is a list of rows (y-major): grid[y][x].
	"""

	def __init__(
		self,
		grid: List[List[Block]],
		operations: list | None = None,
		goal: int | None = None,
	) -> None:
		assert grid and all(isinstance(r, list) for r in grid), "grid must be a 2D list"
		# ensure rectangular
		widths = {len(r) for r in grid}
		if len(widths) != 1:
			raise ValueError("All rows in grid must have the same length")
		self.grid = grid
		# distribute operations to appliances when provided
		self.operations = operations or []
		if self.operations:
			self.distribute_operations()
		# optional goal item id; game ends when player.inventory == goal
		self.goal = goal

		# optional player start position (set by from_level)
		self.start_pos: tuple[int, int] | None = None
		self.start_orientation: str | None = None
		# optional Level object (set by from_level)
		self.level: Level | None = None

	@classmethod
	def from_level(
		cls, level: Level | str, mapping: dict[str, object] | None = None
	) -> "Game":
		"""Construct a Game from a Level object or a path to a level folder.

		Accepts either a `Level` instance (preferred) or a string path to a
		level folder (for backward compatibility). When given a path, it will
		load a Level via `Level.load_from_folder`.
		"""
		# accept a path or a Level instance
		if isinstance(level, str):
			level_obj = Level.load_from_folder(level)
		else:
			level_obj = level

		lines = level_obj.maze_lines
		ops = level_obj.operations
		goal = level_obj.goal

		game = cls.from_text_map(lines, goal, mapping=mapping, operations=ops)
		if level_obj.start_pos is not None:
			game.start_pos = level_obj.start_pos
			game.start_orientation = level_obj.start_orientation
		# attach the original Level object if available
		if hasattr(level_obj, "path"):
			game.level = level_obj
		return game

	def distribute_operations(self) -> None:
		"""Assign operations to appliances based on the operation.appliance id."""
		# operations is a list of Operation-like objects; import locally to avoid cycles
		for y, row in enumerate(self.grid):
			for x, block in enumerate(row):
				if isinstance(block, Appliance):
					# find ops for this appliance id
					for op in self.operations:
						try:
							if getattr(op, "appliance", None) == block.id:
								block.add_operation(op)
						except Exception:
							pass

	@classmethod
	def from_text_map(
		cls,
		lines: Sequence[str],
		goal: int,
		mapping: dict[str, object] | None = None,
		operations: list | None = None,
	) -> "Game":
		"""Construct a Game from an iterable of strings.

		Each character is mapped to a Block subclass via `mapping`.
		By default, '#' -> Wall, '.' -> Floor, ' ' -> Floor.
		"""

		if mapping is None:
			# mapping values can be either a Block subclass or a callable that
			# accepts a single character and returns a Block instance.
			mapping = {"#": Wall, ".": Floor, " ": Floor}

		grid: List[List[Block]] = []
		for line in lines:
			row: List[Block] = []
			for ch in line.rstrip("\n"):
				spec = mapping.get(ch)
				if spec is None:
					# fallback: digits -> Dispenser, letters -> Appliance
					if ch.isdigit():

						def make_dispenser(_ch: str) -> Dispenser:  # type: ignore[override]
							return Dispenser(_ch)

						spec = make_dispenser
					elif ch.isalpha():

						def make_appliance(_ch: str) -> Appliance:  # type: ignore[override]
							return Appliance(_ch)

						spec = make_appliance
					else:
						raise ValueError(f"Unrecognized map character: {ch!r}")

				if isinstance(spec, type) and issubclass(spec, Block):
					# Block subclass
					row.append(spec())
				elif callable(spec):
					row.append(spec(ch))
				else:
					raise ValueError(f"Invalid mapping for character {ch!r}")
			grid.append(row)

		return cls(grid, operations=operations, goal=goal)

	def draw(self, player: "Player" | None = None) -> str:
		"""Render the entire grid to a multiline string using each
		block's `char` attribute. If `player` is provided, the player's
		`char` will overlay the corresponding tile.
		"""
		lines: List[str] = []
		for y, row in enumerate(self.grid):
			chars: List[str] = []
			for x, block in enumerate(row):
				if player is not None and player.x == x and player.y == y:
					chars.append(player.char)
				else:
					chars.append(block.char)
			lines.append("".join(chars))
		return "\n".join(lines)

	async def run_pygame(
		self,
		tile_size: int = 128,
		caption: str = "CookEnv",
		scale_to_display: bool = True,
		margin: float = 0.95,
		min_tile_size: int = 24,
	) -> None:
		"""Open a pygame window and render the grid. Blocks' draw methods
		are used to render each tile.
		"""
		if not _PYGAME_AVAILABLE:
			raise RuntimeError("pygame is not available in this environment")

		pygame.init()

		rows = len(self.grid)
		cols = len(self.grid[0])

		info_press_counter = 0

		# attempt to scale tile size so the whole grid + HUD fits on the display
		if scale_to_display:
			try:
				info = pygame.display.Info()
				disp_w, disp_h = info.current_w, info.current_h
			except Exception:
				disp_w, disp_h = 800, 600
			# compute candidate tile sizes based on width and height constraints
			candidate_w = max(1, int(disp_w * margin) // cols)
			# account for HUD by reserving roughly one tile row
			candidate_h = max(1, int(disp_h * margin) // (rows + 1))
			new_tile = min(tile_size, candidate_w, candidate_h)
			if new_tile < min_tile_size:
				# if the computed tile is too small, respect the minimum but warn
				print(
					f"Warning: computed tile_size {new_tile} < min_tile_size {min_tile_size}; using min_tile_size"
				)
				new_tile = min_tile_size
			# use the computed tile size
			tile_size = new_tile

		width = cols * tile_size
		# reserve HUD height equal to one tile for a simple bottom HUD
		hud_height = max(32, tile_size // 3)
		height = rows * tile_size + hud_height
		screen = pygame.display.set_mode((width, height))
		pygame.display.set_caption(caption)

		# Create a player in the first available walkable tile (top-left search)
		player = None
		# if a start_pos was provided use it
		if getattr(self, "start_pos", None) is not None:
			x, y = self.start_pos
			if (
				0 <= y < len(self.grid)
				and 0 <= x < len(self.grid[0])
				and self.grid[y][x].walkable
			):
				player = Player(x, y)
				# set starting orientation if provided
				if getattr(self, "start_orientation", None) is not None:
					player.orientation = self.start_orientation
		# otherwise fall back to first walkable tile
		if player is None:
			for y, row in enumerate(self.grid):
				for x, block in enumerate(row):
					if block.walkable:
						player = Player(x, y)
						break
				if player is not None:
					break

		if player is None:
			raise RuntimeError("No walkable tile found to place the player")

		running = True
		clock = pygame.time.Clock()
		show_info = False
		# end-of-level state
		level_completed = False
		end_choice = None  # 'repeat', 'continue', 'exit'
		while running:
			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					running = False
				elif event.type == pygame.KEYDOWN:
					# toggle info screen with 'E'
					if event.key == pygame.K_e:
						show_info = not show_info
						if show_info:
							info_press_counter += 1
						continue
					# when info screen is shown, ignore other key inputs
					if show_info:
						continue

					# map keys to orientation and movement deltas, then delegate to Player
					dx = dy = 0
					new_orientation = player.orientation
					if event.key in (pygame.K_w, pygame.K_UP):
						new_orientation = "up"
						dy = -1
					elif event.key in (pygame.K_s, pygame.K_DOWN):
						new_orientation = "down"
						dy = 1
					elif event.key in (pygame.K_a, pygame.K_LEFT):
						new_orientation = "left"
						dx = -1
					elif event.key in (pygame.K_d, pygame.K_RIGHT):
						new_orientation = "right"
						dx = 1

					# update orientation (even if movement blocked)
					player.set_orientation(new_orientation)

					# attempt move via player's try_move
					if dx != 0 or dy != 0:
						moved = player.try_move(dx, dy, self.grid)
						if moved:
							# advance appliances by one game step and try to start ops
							for ry, rrow in enumerate(self.grid):
								for rx, blk in enumerate(rrow):
									if isinstance(blk, Appliance):
										blk.tick()
										# after ticking, attempt to start any eligible op
										blk.try_start_operations()

					elif event.key == pygame.K_SPACE:
						# interact with the tile in front
						player.interact(self.grid)
						# check goal achievement
						if self.goal is not None and player.inventory == self.goal:
							print(
								f"Goal achieved: player has item {self.goal} at time {player.game_time}"
							)
							level_completed = True
							running = False
					elif event.key == pygame.K_q:
						# pass time without moving
						player.pass_time()
						# tick appliances same as on move
						for ry, rrow in enumerate(self.grid):
							for rx, blk in enumerate(rrow):
								if isinstance(blk, Appliance):
									blk.tick()
									blk.try_start_operations()

			# draw background (optional)
			# fill background for tiles area
			screen.fill((100, 100, 100))

			# draw tiles
			for y, row in enumerate(self.grid):
				for x, block in enumerate(row):
					block.draw(screen, x, y, tile_size)

			# draw HUD background at bottom
			hud_rect = pygame.Rect(0, len(self.grid) * tile_size, width, hud_height)
			pygame.draw.rect(screen, (30, 30, 30), hud_rect)
			pygame.draw.line(
				screen,
				(80, 80, 80),
				(0, len(self.grid) * tile_size),
				(width, len(self.grid) * tile_size),
			)

			# draw HUD content: inventory and game_time
			try:
				font = pygame.font.SysFont(None, max(12, hud_height - 8))
			except Exception:
				font = None

			inv_text = "Inventory: empty"
			if player.inventory is not None:
				inv_text = f"Inventory: {player.inventory}"
			gt_text = f"Time: {player.game_time}"

			if font is not None:
				surf_inv = font.render(inv_text, True, (220, 220, 220))
				surf_time = font.render(gt_text, True, (220, 220, 220))
				# position inventory on left, time on right
				screen.blit(
					surf_inv,
					(
						8,
						len(self.grid) * tile_size
						+ (hud_height - surf_inv.get_height()) // 2,
					),
				)
				screen.blit(
					surf_time,
					(
						width - surf_time.get_width() - 8,
						len(self.grid) * tile_size
						+ (hud_height - surf_time.get_height()) // 2,
					),
				)
			else:
				# minimal fallback: draw no text
				pass

			# if info screen is toggled, draw it over the entire area and skip drawing the player
			if show_info and getattr(self, "level", None) is not None:
				# dark translucent overlay
				over = pygame.Surface((width, height), pygame.SRCALPHA)
				over.fill((10, 10, 10, 220))
				screen.blit(over, (0, 0))
				# draw the description and mapping text with improved layout
				try:
					info_font = pygame.font.SysFont(None, max(16, tile_size // 3))
					head_font = pygame.font.SysFont(
						None, max(18, tile_size // 2), bold=True
					)
				except Exception:
					info_font = None
					head_font = None
				if info_font is not None and head_font is not None:
					lvl = self.level
					# layout
					x_pad = 24
					y_pad = 24
					col_gap = 24
					desc_w = int(width * 0.62) - 2 * x_pad
					# left: Description
					screen.blit(
						head_font.render("Description", True, (245, 245, 245)),
						(x_pad, y_pad),
					)
					y_cursor = y_pad + head_font.get_height() + 8
					for para in (lvl.desc or "").split("\n\n"):
						para = para.strip()
						if not para:
							continue
						if "#" in para:
							para = para.split("#")[1]

						words = para.split()
						line = ""
						for w in words:
							test = (line + " " + w).strip()
							surf = info_font.render(test, True, (230, 230, 230))
							if surf.get_width() > desc_w:
								# render current
								if line == "":
									screen.blit(
										info_font.render(w, True, (230, 230, 230)),
										(x_pad + 8, y_cursor),
									)
									y_cursor += info_font.get_height() + 6
									line = ""
								else:
									screen.blit(
										info_font.render(line, True, (230, 230, 230)),
										(x_pad + 8, y_cursor),
									)
									y_cursor += info_font.get_height() + 6
									line = w
							else:
								line = test
						if line:
							text_to_render = line
							screen.blit(
								info_font.render(text_to_render, True, (230, 230, 230)),
								(x_pad + 8, y_cursor),
							)
							y_cursor += info_font.get_height() + 8
						# paragraph gap
						y_cursor += 6

					# right column: mappings
					right_x = x_pad + desc_w + col_gap
					try:
						colors = _load_appliance_colors()
					except Exception:
						colors = {}

					# Items
					screen.blit(
						head_font.render("Items", True, (245, 245, 245)),
						(right_x, y_pad),
					)
					y_m = y_pad + head_font.get_height() + 8
					for k, v in (lvl.mapping or {}).items():
						if k.isdigit():
							line = f"• {k}: {v}"
							screen.blit(
								info_font.render(line, True, (220, 220, 220)),
								(right_x + 6, y_m),
							)
							y_m += info_font.get_height() + 6
					# Appliances
					y_m += 8
					screen.blit(
						head_font.render("Appliances", True, (245, 245, 245)),
						(right_x, y_m),
					)
					y_m += head_font.get_height() + 8
					for k, v in (lvl.mapping or {}).items():
						if k.isalpha():
							color = colors.get(k)
							if color is None:
								text_color = (220, 220, 220)
							else:
								text_color = tuple(
									max(0, min(255, int(c))) for c in color
								)
							line = f"• {k}: {v}"
							screen.blit(
								info_font.render(line, True, text_color),
								(right_x + 6, y_m),
							)
							y_m += info_font.get_height() + 6
				else:
					# no fonts available: skip content
					pass
			else:
				# draw player via Player.draw (tiles area only)
				player.draw(screen, tile_size)
			pygame.display.flip()
			clock.tick(30)
			await asyncio.sleep(0)
		# if level completed, show a small in-window dialog to choose repeat/continue/exit
		if level_completed:
			# simple blocking loop to let player choose R/C/E
			choosing = True
			# use an async-friendly loop so the browser event loop isn't blocked
			while choosing:
				for event in pygame.event.get():
					if event.type == pygame.QUIT:
						choosing = False
						end_choice = "exit"
						break
					if event.type == pygame.KEYDOWN:
						if event.key in (pygame.K_r,):
							end_choice = "repeat"
							choosing = False
							break
						if event.key in (pygame.K_c,):
							end_choice = "continue"
							choosing = False
							break
						if event.key in (pygame.K_e, pygame.K_ESCAPE):
							end_choice = "exit"
							choosing = False
							break
				# render a simple dialog
				surf = pygame.Surface((width, height), pygame.SRCALPHA)
				surf.fill((0, 0, 0, 180))
				screen.blit(surf, (0, 0))
				try:
					font = pygame.font.SysFont(None, max(16, tile_size // 3))
				except Exception:
					font = None
				if font is not None:
					lines = [
						f"Level complete! Time: {player.game_time}",
						"(R) Repeat level  (C) Continue to next  (E) Exit",
					]
					for i, L in enumerate(lines):
						surf_t = font.render(L, True, (240, 240, 240))
						screen.blit(
							surf_t,
							(
								(width - surf_t.get_width()) // 2,
								(height // 2) + i * (surf_t.get_height() + 8),
							),
						)
				pygame.display.flip()
				# yield to the asyncio event loop instead of blocking (fixes pygbag/wasm hang)
				await asyncio.sleep(0.05)
			# only call pygame.quit() on native platforms; pygbag manages lifecycle in the browser
			if sys.platform != "emscripten":
				pygame.quit()
			return True, player.game_time, end_choice, info_press_counter
		else:
			if sys.platform != "emscripten":
				pygame.quit()
			return False, player.game_time, None, info_press_counter

	def run_text(self) -> None:
		"""Run a simple text-mode loop.

		Commands:
		- up, down, left, right : attempt to move in that direction (orientation sets first)
		- interact : interact with the tile in front (pick/place)
		- info : print level description and mapping
		- quit : exit

		Movement steps advance game time and tick appliances; other commands do not advance time.
		"""
		# spawn player similar to run_pygame
		player = None

		info_press_counter = 0

		if getattr(self, "start_pos", None) is not None:
			x, y = self.start_pos
			if (
				0 <= y < len(self.grid)
				and 0 <= x < len(self.grid[0])
				and self.grid[y][x].walkable
			):
				player = Player(x, y)
				if getattr(self, "start_orientation", None) is not None:
					player.orientation = self.start_orientation
		if player is None:
			for y, row in enumerate(self.grid):
				for x, block in enumerate(row):
					if block.walkable:
						player = Player(x, y)
						break
				if player is not None:
					break
		if player is None:
			raise RuntimeError("No walkable tile found to place the player")

		def print_board():
			print(self.draw(player))
			print(f"Time: {player.game_time}")
			print(
				f"Inventory: {player.inventory if player.inventory is not None else 'empty'}"
			)
			# appliances status
			print("Appliances:")
			for yy, row in enumerate(self.grid):
				for xx, blk in enumerate(row):
					if isinstance(blk, Appliance):
						status = "idle"
						if blk.active_operation is not None:
							op = blk.active_operation
							status = f"running {op.ingredients} -> {op.product}, remaining={blk.remaining_time}"
						print(
							f"  {blk.id} at ({xx},{yy}): {status}; contents={blk.contents}"
						)

		def print_info():
			lvl = getattr(self, "level", None)
			if lvl is None:
				print("No level info available")
				return
			print("\n--- Description ---")
			for raw in (lvl.desc or "").splitlines():
				print(raw)
			print("\n--- Mapping ---")
			# separate items and appliances
			items = []
			agg = []
			for k, v in (lvl.mapping or {}).items():
				if k.isdigit():
					items.append((k, v))
				else:
					agg.append((k, v))
			if items:
				print("Items:")
				for k, v in items:
					print(f"  - {k}: {v}")
			if agg:
				print("Appliances:")
				for k, v in agg:
					print(f"  - {k}: {v}")

		print("Text-mode controls: up/down/left/right, interact, info, skip, quit")
		print_board()
		while True:
			cmd = input("> ").strip().lower()
			if not cmd:
				continue
			if cmd in ("quit", "exit"):
				print("Exiting")
				return False, player.game_time, "exit", info_press_counter
			if cmd == "info":
				info_press_counter += 1
				print_info()
				continue
			if cmd == "skip":
				# pass time without moving
				player.pass_time()
				# tick appliances same as on move
				for ry, rrow in enumerate(self.grid):
					for rx, blk in enumerate(rrow):
						if isinstance(blk, Appliance):
							blk.tick()
							blk.try_start_operations()
				print_board()
				continue
			if cmd == "interact":
				changed = player.interact(self.grid)
				if changed:
					print("Interaction succeeded")
					if self.goal is not None and player.inventory == self.goal:
						print(
							f"Goal achieved: player has item {self.goal} at time {player.game_time}"
						)
						choice = None
						while choice not in ("r", "c", "e"):
							choice = (
								input(
									"Level complete. (r) repeat, (c) continue, (e) exit: "
								)
								.strip()
								.lower()
							)
							if choice not in ("r", "c", "e"):
								print("Please choose r, c or e")
						if choice == "r":
							return True, player.game_time, "repeat", info_press_counter
						if choice == "c":
							return (
								True,
								player.game_time,
								"continue",
								info_press_counter,
							)
						return True, player.game_time, "exit", info_press_counter
				else:
					print("Nothing happened")
				continue
			# movement commands
			if cmd in ("up", "down", "left", "right"):
				dx = dy = 0
				if cmd == "up":
					new_orient = "up"
					dy = -1
				elif cmd == "down":
					new_orient = "down"
					dy = 1
				elif cmd == "left":
					new_orient = "left"
					dx = -1
				else:
					new_orient = "right"
					dx = 1
				# set orientation (no time pass)
				player.set_orientation(new_orient)
				moved = player.try_move(dx, dy, self.grid)
				if moved:
					# tick appliances and attempt to start ops
					for ry, rrow in enumerate(self.grid):
						for rx, blk in enumerate(rrow):
							if isinstance(blk, Appliance):
								blk.tick()
								blk.try_start_operations()
					print_board()
					if self.goal is not None and player.inventory == self.goal:
						print(
							f"Goal achieved: player has item {self.goal} at time {player.game_time}"
						)
						choice = None
						while choice not in ("r", "c", "e"):
							choice = (
								input(
									"Level complete. (r) repeat, (c) continue, (e) exit: "
								)
								.strip()
								.lower()
							)
							if choice not in ("r", "c", "e"):
								print("Please choose r, c or e")
						if choice == "r":
							return True, player.game_time, "repeat"
						if choice == "c":
							return True, player.game_time, "continue"
						return True, player.game_time, "exit"
				else:
					print("Move blocked or out of bounds")
				print_board()
				continue
			# unknown command
			print("Unknown command. Use up/down/left/right, interact, info, quit")


if __name__ == "__main__":
	asyncio.run(play_levels(start_folder="levels", use_text=True))
