import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .db import Base

# PUBLIC_INTERFACE
class User(Base):
    """Represents a player in the Tic Tac Toe application."""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(128), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    games_as_x = relationship("Game", back_populates="player_x", foreign_keys='Game.player_x_id')
    games_as_o = relationship("Game", back_populates="player_o", foreign_keys='Game.player_o_id')
    moves = relationship("Move", back_populates="player")


# Game 'state' will hold a flattened string list of board ("---------", "XO---O---", etc.).
# 'winner' can be null, "X", "O", or "draw".
# PUBLIC_INTERFACE
class Game(Base):
    """Represents a single Tic Tac Toe match."""
    __tablename__ = "games"
    id = Column(Integer, primary_key=True, index=True)
    player_x_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    player_o_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    state = Column(String(9), nullable=False, default="---------")  # 9-char string
    winner = Column(String(10), nullable=True)  # 'X', 'O', or 'draw'
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    player_x = relationship("User", foreign_keys=[player_x_id], back_populates="games_as_x")
    player_o = relationship("User", foreign_keys=[player_o_id], back_populates="games_as_o")
    moves = relationship("Move", back_populates="game", order_by="Move.id")

# PUBLIC_INTERFACE
class Move(Base):
    """Stores an individual move in the game."""
    __tablename__ = "moves"
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    move_index = Column(Integer, nullable=False)  # 0 to 8 board position
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    game = relationship("Game", back_populates="moves")
    player = relationship("User", back_populates="moves")
