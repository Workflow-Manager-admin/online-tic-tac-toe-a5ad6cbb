from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from .db import get_db
from .models import User, Game, Move

router = APIRouter()

# --- Pydantic Schemas ---

class UserSchema(BaseModel):
    id: int
    username: str

    class Config:
        orm_mode = True

class GameCreate(BaseModel):
    player_x_id: int = Field(..., description="User ID for X")
    player_o_id: int = Field(..., description="User ID for O")

class GameState(BaseModel):
    id: int
    player_x: UserSchema
    player_o: UserSchema
    state: str
    winner: Optional[Literal["X", "O", "draw", None]]
    moves: List[int] = Field(..., description="List of move indices")
    created_at: str
    updated_at: str

    class Config:
        orm_mode = True

class MoveRequest(BaseModel):
    player_id: int = Field(..., description="User ID making the move")
    move_index: int = Field(..., ge=0, le=8, description="Board index for the move (0-8)")

class GameListItem(BaseModel):
    id: int
    state: str
    winner: Optional[Literal["X", "O", "draw", None]]
    created_at: str
    updated_at: str
    opponent: UserSchema

    class Config:
        orm_mode = True

# --- Utility/game logic ---
def get_current_turn(state: str) -> str:
    """X always starts; if even number of moves, it's X's turn, else O's."""
    moves_count = 9 - state.count("-")
    return "X" if moves_count % 2 == 0 else "O"

def check_winner(state: str) -> Optional[Literal["X", "O", "draw"]]:
    """Checks win/draw condition for current state string."""
    lines = [
        [0,1,2],[3,4,5],[6,7,8],  # Rows
        [0,3,6],[1,4,7],[2,5,8],  # Cols
        [0,4,8],[2,4,6],          # Diagonals
    ]
    for line in lines:
        a, b, c = line
        if state[a] == state[b] == state[c] and state[a] in "XO":
            return state[a]
    if "-" not in state:
        return "draw"
    return None

# --- REST Endpoints ---

# PUBLIC_INTERFACE
@router.post("/games", response_model=GameState, summary="Create new game", tags=["Game"])
async def create_game(payload: GameCreate, db: AsyncSession = Depends(get_db)):
    """Creates a new Tic Tac Toe game between two users. Returns the initial game state."""
    # Ensure both users exist
    result = await db.execute(
        select(User).where(User.id.in_([payload.player_x_id, payload.player_o_id]))
    )
    users = result.scalars().all()
    if len(users) != 2:
        raise HTTPException(status_code=404, detail="Both users must exist.")

    game = Game(player_x_id=payload.player_x_id, player_o_id=payload.player_o_id, state="---------", winner=None)
    db.add(game)
    await db.commit()
    await db.refresh(game)
    # Eager load player info for response
    await db.refresh(game, ["player_x", "player_o", "moves"])
    return _to_gamestate(game)

def _to_gamestate(game: Game) -> GameState:
    return GameState(
        id=game.id,
        player_x=UserSchema.from_orm(game.player_x),
        player_o=UserSchema.from_orm(game.player_o),
        state=game.state,
        winner=game.winner,
        moves=[move.move_index for move in sorted(game.moves, key=lambda m: m.id)],
        created_at=game.created_at.isoformat(),
        updated_at=game.updated_at.isoformat(),
    )

# PUBLIC_INTERFACE
@router.get("/games/{game_id}", response_model=GameState, summary="Get game state", tags=["Game"])
async def get_game_state(game_id: int, db: AsyncSession = Depends(get_db)):
    """Get the current state and player info for a game."""
    result = await db.execute(
        select(Game).where(Game.id == game_id)
    )
    game = result.scalars().first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    await db.refresh(game, ["player_x", "player_o", "moves"])
    return _to_gamestate(game)

# PUBLIC_INTERFACE
@router.post("/games/{game_id}/move", response_model=GameState, summary="Make move", tags=["Game"])
async def make_move(game_id: int, request: MoveRequest, db: AsyncSession = Depends(get_db)):
    """Makes a move in the selected game. Validates turn, checks win/draw, and updates board & moves."""
    result = await db.execute(select(Game).where(Game.id == game_id))
    game = result.scalars().first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.winner:
        raise HTTPException(status_code=400, detail="Game already finished")
    # Determine which player is X/O in this game
    player_type = "X" if request.player_id == game.player_x_id else "O" if request.player_id == game.player_o_id else None
    if not player_type:
        raise HTTPException(status_code=403, detail="Not a participant in this game")
    # Only correct player can move
    current_turn = get_current_turn(game.state)
    if player_type != current_turn:
        raise HTTPException(status_code=400, detail=f"It is not {player_type}'s turn")
    # Valid move index?
    if not (0 <= request.move_index <= 8):
        raise HTTPException(status_code=400, detail="move_index must be [0,8]")
    if game.state[request.move_index] != "-":
        raise HTTPException(status_code=400, detail="Square already taken")

    # Update state string
    new_state = (
        game.state[:request.move_index] + player_type + game.state[request.move_index + 1 :]
    )
    # Add move
    move = Move(game_id=game.id, player_id=request.player_id, move_index=request.move_index)
    db.add(move)
    game.state = new_state
    # Win/draw detection
    winner = check_winner(new_state)
    if winner:
        game.winner = winner
    await db.commit()
    await db.refresh(game)
    await db.refresh(game, ["player_x", "player_o", "moves"])
    return _to_gamestate(game)

# PUBLIC_INTERFACE
@router.get("/users/{user_id}/games", response_model=List[GameListItem], summary="List games by user", tags=["Game"])
async def list_games_for_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Lists all games (with opponent info) that the user participates in."""
    # Get games where the user is X or O
    result = await db.execute(
        select(Game).where(or_(Game.player_x_id == user_id, Game.player_o_id == user_id))
    )
    games = result.scalars().all()
    res: List[GameListItem] = []
    for g in games:
        # Determine opponent user
        if g.player_x_id == user_id:
            await db.refresh(g, ["player_o"])
            opponent = g.player_o
        else:
            await db.refresh(g, ["player_x"])
            opponent = g.player_x
        res.append(
            GameListItem(
                id=g.id,
                state=g.state,
                winner=g.winner,
                created_at=g.created_at.isoformat(),
                updated_at=g.updated_at.isoformat(),
                opponent=UserSchema.from_orm(opponent),
            )
        )
    return res
