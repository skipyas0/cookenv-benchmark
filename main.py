from game import play_levels
import asyncio

# !!! use_text=False here for pygbag, run game.py for text version 
if __name__ == "__main__":
    asyncio.run(play_levels(start_folder="levels", use_text=False))