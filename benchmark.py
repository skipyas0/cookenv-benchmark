"""Simple benchmark runner that tests an LLM on the text-mode game.

It launches the game's `run_text` in a subprocess, reads the game's stdout until the
interactive prompt, calls the OpenAI API (configurable model) to get the next move,
parses the response and feeds it back to the game process.

Usage:
    python benchmark.py --model gpt-4o-openrouter --level levels/level1 --steps 200

Environment:
    Create a .env file with OPENAI_API_KEY and optionally OPENAI_API_BASE (for OpenRouter)

"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import re
from typing import Optional
import json
from dotenv import load_dotenv
from textwrap import dedent

from openai import OpenAI

# accepted commands the game understands in text mode
VALID_COMMANDS = {"up", "down", "left", "right", "interact", "info"}

SYSTEM_PROMPT = dedent("""\
    You are playing a simple tile-based cooking game. 

    The map is a grid-world consisting of 4 different block types:
    - floor: marked by '.', you can move freely on floor blocks, each move costs you one 'game_time'
    - wall: marked by '#', you can't move through wall blocks
    - dispenser: marked by a digit 1-9, impassable, when standing besides it you can *interact* with it to acquire an ingredient if your inventory is empty
    - appliance: marked by a uppercase letter A-E, impassable, when standing besides it you can *interact* with it to either 1. place the contents of your inventory inside or 2. take the contents of the appliance if your inventory is empty
    Furthermore, if an appliance contains a specific combination of ingredients, it performs an 'operation', yielding a novel ingredient after some amount of 'game_time' passes.
    By writing 'info', you can display information about the given task - a textual recipe, a mapping which maps objects in the recipe to block ids on the board, inventory and appliance states.
    Your goal is to perform the actions described in the recipe in as little 'game_time' as possible.
    Each move on the board costs 1 'game_time'. If your move is blocked by an impassable object, the player just changes orientation without incrementing 'game_time'.
    Interacting and summoning info does not cost 'game_time'. If you need to pass 'game_time' without moving, (e.g. when waiting for an appliance to finish an operation), use the 'skip' command.

    The game prints the board and then prompts with ' > ' when it wants your next action.
    You must respond with exactly one of the following commands (lowercase): up, down, left, right, interact, info, skip, quit.
    Do not output any other text or commentary — only the single command followed by a newline.
""")


USER_TEMPLATE = dedent("""\
    Here is the most recent game output (including the board and any status lines):\n\n
    {game_output}\n\n
    Choose the single next command.
""")

LEVEL_COMPLETE_TEMPLATE = dedent("""\
    Congratulations! You completed the level.
    You now advance to a new, slightly harder level.
    Keep playing!
""")


COMMAND_RE = re.compile(
    r"\b(up|down|left|right|interact|info)\b", re.IGNORECASE
)


def extract_command(text: str) -> Optional[str]:
    """Extract the first valid command from the LLM's text output."""
    m = COMMAND_RE.search(text)
    if not m:
        return None
    cmd = m.group(1).lower()
    if cmd in VALID_COMMANDS:
        return cmd
    return None


def call_llm(
    client: OpenAI,
    model: str,
    turns: list[dict[str, str]],
    temperature: float = 0.0,
) -> Optional[str]:
    """Call the configured model and return the parsed single command (or None).

    This uses the ChatCompletion API via the openai client. If you're using
    an OpenRouter-compatible base, set OPENAI_API_BASE to your router URL.
    """
    time.sleep(3)
    resp = client.chat.completions.create(
        model=model, messages=turns, temperature=temperature
    )
    content = ""
    try:
        content = resp.choices[0].message.content
    except Exception as e:
        print(e)
        try:
            content = str(resp)
        except Exception:
            content = ""
            print("exception: empty content")
    cmd = extract_command(content)
    return cmd


def run_game_subprocess(python_exe: str = sys.executable):
    """Start a subprocess that runs the text-mode game for the provided level.

    The child process will be started with unbuffered output (-u) so we can
    read the prompt as it appears.
    """
    cmd = [python_exe, "-u", "-m", "game"]
    # The cookenv.game __main__ calls play_levels("levels", use_text=False) by default in this repo.
    # We prefer to pass the level we want; to keep things simple we set the CWD such that
    # relative level paths will be resolved by the level loader. Alternatively, you can
    # edit this call to pass an environment variable or different entrypoint.
    p = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    return p


def read_until_prompt(proc, timeout: float = 10.0) -> Optional[str]:
    """Read from proc.stdout until the game prints the input prompt (> ).

    Returns the captured output (including the prompt) or None on EOF/timeout.
    """
    out = []
    buf = ""
    start = time.time()
    while True:
        ch = proc.stdout.read(1)
        if ch == "":
            # EOF
            return "".join(out) if out else None
        buf += ch
        out.append(ch)
        if buf.endswith(" > "):
            return "".join(out)
        if time.time() - start > timeout:
            return "".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model", type=str, default="openai/gpt-oss-120b", help="Model name to use"
    )
    parser.add_argument(
        "--max-steps", type=int, default=1000, help="Maximum steps/actions to take"
    )
    args = parser.parse_args()

    # setup_openai_from_env()   
    #key = os.environ.get("API_KEY")
    proc = run_game_subprocess()
    load_dotenv()
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1"
    )
    turns = [{"role": "user" if any(x in args.model for x in ["gemma"]) else "system", "content": SYSTEM_PROMPT}]

    steps = 0
    try:
        while steps < args.max_steps:
            captured = read_until_prompt(proc, timeout=20.0)
            if captured is None:
                print("Game process ended or produced no output.")
                break
            # show latest output
            print("--- game output ---")
            print(captured)
            print("--- end of game output ---")
            if "Level complete." in captured:
                cmd = "c" # select continue for the LLM
                message = {
                    "role": "user", "content": LEVEL_COMPLETE_TEMPLATE
                }

                print(message)
                turns.append(message)

            else:
                message = {
                    "role": "user", "content": USER_TEMPLATE.format(game_output=captured)
                }

                print(message)
                turns.append(message)

                with open("benchmark.log", "w+") as f:
                    json.dump(turns, f)

                # Ask LLM for the next command
                #cmd = input("debug input:")
                cmd = call_llm(client, args.model, turns)
                if cmd is None:
                    print("LLM did not return a valid command. Sending 'info' as fallback.")
                    cmd = "info"
                    turns.append({"role": "assistant", "content": f"{cmd}"})
                print(f"LLM -> {cmd}")

            # send to game stdin
            try:
                proc.stdin.write(cmd + "\n")
                proc.stdin.flush()
            except Exception:
                print("Failed to write to game stdin")
                break
            if cmd == "quit":
                print("Requested quit; ending benchmark")
                break
            steps += 1
        # attempt graceful shutdown
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.kill()
    with open("transcript.json", "w+") as f:
        json.dump(turns, f, indent=4)

if __name__ == "__main__":
    main()
