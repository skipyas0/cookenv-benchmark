"""
Batch benchmark runner on OpenAI API. 
Runs the game in text mode in a subprocesses and sends the game output to an LLM for next steps.

Usage:
    python benchmark_batch.py --model gpt-5-mini --instances 5 --steps 20
    python benchmark_batch.py --mock --instances 2 --steps 5
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
import re
import json
import os
import select
import codecs
from typing import Optional, Dict, List, Any
from dotenv import load_dotenv
from textwrap import dedent
from openai import OpenAI

# --- Constants & Templates ---

VALID_COMMANDS = {"up", "down", "left", "right", "interact", "info"}

SYSTEM_PROMPT = dedent("""\
    # Instructions
    You are playing a **simple tile-based cooking game**. 
    The goal is to **complete the recipe** by **interacting** with **dispensers** and **appliances** and get the **final ingredient** into your inventory
    in as **few steps** (game_time) as possible. Your inventory has a **single slot**, so you can only carry one ingredient at a time!

    ## Controls
    {controls}

    ## Map
    The map is a grid-world consisting of 4 different block types:
    - floor: marked by '.', you can move freely on floor blocks, each move costs you one 'game_time'
    - wall: marked by '#'
    - dispenser: marked by a digit 1-9
    - appliance: marked by a uppercase letter A-E
    You can only move through *floor* blocks. Each block travelled costs 1 game_time.

    You have a single-slot inventory. If it is empty, interacting with a dispenser fills it with the dispensed ingredient.
    Similarly, interacting with an appliance will attempt to take an item from the appliance into your inventory.
    If your inventory is full, you will first place the contents of your inventory into the appliance.
    If an appliance contains a specific combination of ingredients, it performs an 'operation', yielding a novel ingredient after some amount of 'game_time' passes.
    By writing 'info', you can display information about the given task - a textual recipe, a mapping which maps objects in the recipe to block ids on the board, inventory and appliance states.
    Your goal is to perform the actions described in the recipe in as little 'game_time' as possible. 
""")

CONTROLS = dedent("""\
- "interact (x,y)" - Tries to interact with a block on coordinates given by 'x' and 'y'. 
If there is an interactable block on that position, the player will automatically pathfind to it.
If the block has an ongoing operation, the the game will automatically skip time until the operation ends.
- "info" - Displays info about the game and the level.
- "drop" - Empties the inventory. Caution: item in inventory is lost.
- "skip" - As an alternative to waiting using "interact (x,t)", you can skip 1 game_time with "skip".
""")

CONTROL_INFO_PATHFIND = dedent(f"""\
{CONTROLS}
Respond **ONLY** with a valid command without any additional text or reasoning.
""")

CONTROL_INFO_PATHFIND_COT = dedent(f"""\
{CONTROLS}
After your thought process, respond with a valid command wrapped in <cmd> </cmd> tags.
""")

USER_TEMPLATE = dedent("""\
    Here is the most recent game output (including the board and any status lines):\n\n
    {game_output}\n\n
    Choose the single next command without any other text.
""")

USER_TEMPLATE_COT = dedent("""\
    Here is the most recent game output (including the board and any status lines):\n\n
    {game_output}\n\n
    In a systematic manner, plan out your next step.
    Think about all possible moves from the current game state and select the best one.
    After your thinking process, provide the next command wrapped in <cmd> </cmd> tags.
""")

LEVEL_COMPLETE_TEMPLATE = dedent("""\
    Congratulations! You completed the level.
    You now advance to a new, slightly harder level.
    Keep playing!
""")

COMMAND_RE = re.compile(r"(interact)\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)|(info)|(drop)|(skip)", re.IGNORECASE)
COMMAND_RE_COT = re.compile(r"<cmd>\s*(?:(interact)\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)|(info)|(drop)|(skip))\s*</cmd>", re.IGNORECASE)

# --- Logic Implementation ---

def extract_command(text: str, reasoning: bool) -> Optional[str]:
    """Extract the first valid command from the LLM's text output."""
    pattern = COMMAND_RE_COT if reasoning else COMMAND_RE
    match = pattern.search(text)
    result = (None, None)
    if match is None:
        return None
    if match.group(1):
        cmd = match.group(1)
        x = int(match.group(2))
        y = int(match.group(3))
        result = (cmd, (x, y)) 
    elif match.group(4):
        result = ("info", None)
    elif match.group(5):
        result = ("drop", None)
    elif match.group(6):
        result = ("skip", None)
    
    str_cmd = f"{result[0]}({result[1][0]},{result[1][1]})" if result[0] == "interact" else result[0]
    return str_cmd

def run_game_subprocess(python_exe: str = sys.executable):
    """Start a subprocess that runs the text-mode game in BINARY mode."""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    cmd = [python_exe, "-u", "-m", "game"]
    p = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=False, # Important: Binary mode to avoid buffering issues
        bufsize=0,  # Unbuffered
        env=env
    )
    return p

def read_until_prompt(proc, timeout: float = 10.0) -> Optional[str]:
    """
    Read from proc.stdout (binary) until the game prints the input prompt (> ).
    """
    out_bytes = bytearray()
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    start = time.time()
    
    # We maintain a string buffer to check for the prompt
    str_buf = ""

    while True:
        # Check process life
        if proc.poll() is not None:
             # Drain remaining
             rest = proc.stdout.read()
             if rest:
                 str_buf += decoder.decode(rest, final=True)
             return str_buf if str_buf else None

        if time.time() - start > timeout:
            print("Timeout waiting for prompt.")
            print(f"DEBUG: Last captured: {repr(str_buf[-50:])}")
            return str_buf

        # Select on the file descriptor directly
        ready, _, _ = select.select([proc.stdout], [], [], 0.5)
        
        if ready:
            # Read raw bytes from the file descriptor
            chunk = os.read(proc.stdout.fileno(), 4096)
            if not chunk:
                # EOF
                return str_buf if str_buf else None
            
            # Decode incrementally
            text_chunk = decoder.decode(chunk, final=False)
            str_buf += text_chunk
            
            # Check for prompt
            if " > " in str_buf[-20:]: # Check tail
                return str_buf
        else:
            continue

class GameSession:
    """Manages a single game process and its conversation history."""
    def __init__(self, index: int, args):
        self.index = index
        self.id = f"game_{index}"
        self.proc = run_game_subprocess()
        self.history: List[Dict[str, str]] = []
        self.steps = 0
        self.finished = False
        self.args = args
        
        system_prompt = SYSTEM_PROMPT.format(
            controls=CONTROL_INFO_PATHFIND_COT if args.cot else CONTROL_INFO_PATHFIND
        )
        self.history.append({
            "role": "user" if any(x in args.model for x in ["gemma", "qwen"]) else "system",
            "content": system_prompt,
        })
        self.user_template = USER_TEMPLATE_COT if args.cot else USER_TEMPLATE

    def advance_to_prompt(self) -> str:
        """Reads game output up to the user prompt."""
        captured = read_until_prompt(self.proc, timeout=10.0)
        print(captured)
        if not captured:
            if self.proc.poll() is not None:
                self.finished = True
            return ""

        if "Level complete." in captured:
            self.history.append({"role": "user", "content": LEVEL_COMPLETE_TEMPLATE})
            return captured
        
        msg_content = self.user_template.format(game_output=captured)
        self.history.append({"role": "user", "content": msg_content})
        return captured

    def get_last_request_body(self) -> Dict[str, Any]:
        return {
            "model": self.args.model,
            "messages": self.history,
        }

    def apply_command(self, raw_output: str):
        cmd = extract_command(raw_output, self.args.cot)
        self.history.append({"role": "assistant", "content": raw_output})
        
        if cmd is None:
            cmd = "info" 
            print(f"[{self.id}] Fallback to info")
        
        print(f"[{self.id}] LLM ({self.steps}) -> {cmd}")
        
        try:
            # We must encode to bytes for binary stdin
            self.proc.stdin.write((cmd + "\n").encode('utf-8'))
            self.proc.stdin.flush()
        except Exception as e:
            print(f"[{self.id}] Failed to write to stdin: {e}")
            self.finished = True
            return

        if cmd == "quit":
            self.finished = True
        
        self.steps += 1
        if self.steps >= self.args.max_steps:
            self.finished = True

    def close(self):
        if self.proc.poll() is None:
            self.proc.kill()
        with open(f"transcript_{self.id}.json", "w+") as f:
            json.dump(self.history, f, indent=4)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="gpt-5-mini", help="Model name to use")
    parser.add_argument("--max-steps", type=int, default=400, help="Maximum steps per game")
    parser.add_argument("--instances", type=int, default=1, help="Number of concurrent instances")
    parser.add_argument("--cot", action="store_true", default=False, help="Enable Chain of Thought")
    parser.add_argument("--mock", action="store_true", help="Run in mock mode")
    args = parser.parse_args()

    load_dotenv()
    client = None
    if not args.mock:
        client = OpenAI()

    print(f"Starting {args.instances} game instances (Mock: {args.mock})...")
    sessions = [GameSession(i, args) for i in range(args.instances)]
    active_sessions = {s.id: s for s in sessions}

    batch_counter = 0

    try:
        while active_sessions:
            print(f"\n--- Batch Step {batch_counter} ---")
            batch_inputs = []
            
            # 1. Collect Requests
            finished_ids = []
            for sess_id, session in active_sessions.items():
                print(f"Reading output from {sess_id}...")
                session.advance_to_prompt() # Output handled internally
                
                if session.finished:
                    print(f"{sess_id} finished locally.")
                    finished_ids.append(sess_id)
                    continue
                
                if not args.mock:
                    request_body = session.get_last_request_body()
                    batch_line = {
                        "custom_id": sess_id,
                        "method": "POST",
                        "url": "/v1/chat/completions",
                        "body": request_body
                    }
                    batch_inputs.append(batch_line)
                else:
                    batch_inputs.append(sess_id)

            for fid in finished_ids:
                active_sessions[fid].close()
                del active_sessions[fid]
            
            if not batch_inputs:
                print("No active games left.")
                break

            # 2. Process Batch
            results_map = {}

            if args.mock:
                print("MOCK MODE: Simulating batch processing...")
                time.sleep(1) 
                for sess_id in batch_inputs:
                    results_map[sess_id] = {
                        "custom_id": sess_id,
                        "response": {
                            "body": {
                                "choices": [{
                                    "message": {
                                        "content": "Reasoning: Skipping time.\n<cmd>skip</cmd>"
                                    }
                                }]
                            }
                        }
                    }
            else:
                # Real API Logic
                jsonl_filename = f"batch_input_{batch_counter}.jsonl"
                with open(jsonl_filename, "w") as f:
                    for line in batch_inputs:
                        f.write(json.dumps(line) + "\n")
                
                print(f"Uploading batch file {jsonl_filename}...")
                batch_input_file = client.files.create(
                    file=open(jsonl_filename, "rb"),
                    purpose="batch"
                )

                print("Creating batch job...")
                batch_job = client.batches.create(
                    input_file_id=batch_input_file.id,
                    endpoint="/v1/chat/completions",
                    completion_window="24h",
                    metadata={"description": f"game_step_{batch_counter}"}
                )
                print(f"Batch {batch_job.id} submitted. Waiting...")

                while True:
                    batch_status = client.batches.retrieve(batch_job.id)
                    status = batch_status.status
                    print(batch_status)
                    if status == "completed":
                        break
                    elif status in ["failed", "expired", "cancelled"]:
                        print(f"Batch failed: {status}")
                        return
                    else:
                        sys.stdout.write(".")
                        sys.stdout.flush()
                        time.sleep(30)
                
                print("\nDownloading results...")
                if batch_status.output_file_id:
                    file_response = client.files.content(batch_status.output_file_id)
                    for line in file_response.text.strip().split('\n'):
                        res = json.loads(line)
                        results_map[res['custom_id']] = res
                    print(file_response.text)
                elif batch_status.error_file_id:
                    print(f"\nBatch contained errors. Downloading error log {batch_status.error_file_id}...")
                    error_response = client.files.content(batch_status.error_file_id)
                    error_content = error_response.text
                    
                    print("--- BATCH ERRORS ---")
                    for line in error_content.strip().split('\n'):
                        try:
                            err_entry = json.loads(line)
                            cid = err_entry.get('custom_id', 'unknown_id')
                            
                            # Extract error details safely
                            # Errors usually appear in response.body.error or directly if validation failed
                            error_info = err_entry.get('response', {}).get('body', {})
                            if not error_info: 
                                error_info = err_entry.get('error', err_entry)
                                
                            print(f"Game ID: {cid} | Error: {json.dumps(error_info, indent=2)}")
                        except json.JSONDecodeError:
                            print(f"Raw Error Line: {line}")
                    
                    print("--------------------")
                    # Stop execution since the batch failed
                    raise RuntimeError("Batch processing failed. See errors above.")
                os.remove(jsonl_filename)
            # 3. Apply results
            for sess_id, result in results_map.items():
                if sess_id in active_sessions:
                    try:
                        choice = result['response']['body']['choices'][0]
                        content = choice['message']['content']
                        active_sessions[sess_id].apply_command(content)
                    except Exception as e:
                        print(f"Error processing result for {sess_id}: {e}")
            
            batch_counter += 1

    except KeyboardInterrupt:
        print("\nBenchmark interrupted.")
    finally:
        print("Cleaning up processes...")
        for s in sessions:
            s.close()

if __name__ == "__main__":
    main()