from game import play_levels
import asyncio
if __name__ == "__main__":
    asyncio.run(play_levels(start_folder="levels", use_text=True))