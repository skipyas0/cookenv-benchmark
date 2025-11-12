import json
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Tuple, List
try:
	import pygame

	_PYGAME_AVAILABLE = True
except Exception:
	pygame = None  # type: ignore
	_PYGAME_AVAILABLE = False
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
		return None
		print(f"Warning: _load_asset, asset not found: {path}")
	
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
