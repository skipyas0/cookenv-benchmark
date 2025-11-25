from blocks import Block, Floor  # type: ignore
from typing import List
from dataclasses import dataclass
from collections import deque
from enum import Enum

@dataclass
class Position:
        x: int
        y: int

@dataclass
class queueStruct:
        pos : Position
        distance : int


class State(Enum):
        NOT_FOUND = 0
        CLOSED = 1
        OPEN = 2
        NOT_INTERACTABLE = 4 #?


"""Finds shortest path to any block next to the specified block."""
def pathfind_neighbor_any(grid :  List[List[Block]],playerStart : Position, toFind : Position) -> tuple[int, Position]:
        if playerStart == toFind \
            or len(grid) <= 0 or len(grid[0]) <= 0\
            or toFind.x < 0 or toFind.y < 0 or toFind.x >= len(grid[0]) or toFind.y >= len(grid):
              return -1, Position(-1,-1);
        
        q_nextPosition : deque['queueStruct'] = deque()
        q_nextPosition.appendleft(queueStruct(playerStart,0))

        #init grid
        m_grid : List[List[State]] = []

        for y, row in enumerate(grid):
            lst : List[State] = []
            for x, block in enumerate(row):
                if isinstance(block, Floor):
                       lst.append(State.NOT_FOUND)
                else:
                        lst.append(State.NOT_INTERACTABLE)
            m_grid.append(lst)
                       

        while q_nextPosition:
            nextBlock = q_nextPosition.pop()
            pos=nextBlock.pos


            for neighb_pos in [Position(pos.x-1,pos.y),Position(pos.x+1,pos.y),Position(pos.x,pos.y-1),Position(pos.x,pos.y+1)]:
                if neighb_pos == toFind: #end
                      return nextBlock.distance, pos

                if m_grid[neighb_pos.y][neighb_pos.x] == State.NOT_FOUND\
                    and neighb_pos.x > 0 and neighb_pos.y > 0\
                    and neighb_pos.x < len(grid[0]) and neighb_pos.y < len(grid):

                    q_nextPosition.appendleft(queueStruct(neighb_pos,nextBlock.distance+1))
                    m_grid[neighb_pos.y][neighb_pos.x] = State.OPEN

            m_grid[pos.y][pos.x] = State.CLOSED


        return -1, Position(-1,-1)
