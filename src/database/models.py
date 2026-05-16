from sqlalchemy import String, Integer, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.ext.mutable import MutableDict
from database.core import Base
from pathlib import Path
from typing import Optional
import json

DEFAULT_EQUIPMENT = {
    "weapon": None,
    "armor": None,
    "ring": None,
    "bag": []
}

# Модель локаций
class Locations(Base):
    __tablename__ = "locations"
    
    id_location: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500))
    features: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)
    
    outgoing_edges: Mapped[list["Edges"]] = relationship(
        foreign_keys="Edges.from_id",
        back_populates="from_location"
    )
    incoming_edges: Mapped[list["Edges"]] = relationship(
        foreign_keys="Edges.to_id",
        back_populates="to_location"
    )

# Модель путей между локациями
class Edges(Base):
    __tablename__ = "edges"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_id: Mapped[int] = mapped_column(ForeignKey("locations.id_location"), index=True)
    to_id: Mapped[int] = mapped_column(ForeignKey("locations.id_location"), index=True)

    from_location: Mapped["Locations"] = relationship(
        foreign_keys=[from_id],
        back_populates="outgoing_edges"
    )
    to_location: Mapped["Locations"] = relationship(
        foreign_keys=[to_id],
        back_populates="incoming_edges"
    )

# Модель игроков
class Players(Base):
    __tablename__ = "players"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vk_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    location_id: Mapped[int] = mapped_column(Integer, default=1, nullable=False, index=True)
    
    
    health: Mapped[int] = mapped_column(Integer, default=100)
    max_health: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    protection: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    attack: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    balance: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    
    inventory: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=lambda: DEFAULT_EQUIPMENT.copy())
    
    dungeon_run: Mapped[Optional["Dungeons"]] = relationship(
        "Dungeons", back_populates="player", uselist=False
    )
    
# Модель всех предметов
class Items(Base):
    __tablename__ = "items"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    slot: Mapped[Optional[str]] = mapped_column(String(20))
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    price: Mapped[int] = mapped_column(Integer, default=0)

# Молдель боя
class Battles(Base):
    __tablename__ = "battles"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vk_id: Mapped[int] = mapped_column(Integer, index=True)
    state: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), nullable=False)
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

# Модель противников 
class Monsters(Base):
    __tablename__ = "monsters"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500))
    rarity: Mapped[str] = mapped_column(String(20), default="common")

# Модель данжей
class Dungeons(Base):
    __tablename__ = "dungeons"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vk_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.vk_id"), unique=True, index=True)
    
    map_data: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), nullable=False)
    pos_x: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    pos_y: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rooms_cleared: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    player: Mapped[Optional["Players"]] = relationship("Players", back_populates="dungeon_run")
    
    @validates('pos_x')
    def validate_pos_x(self, key, value):
        if not 1 <= value <= 7:
            raise ValueError(f"pos_x must be 1-7, got {value}")
        return value
    
    @validates('pos_y')
    def validate_pos_y(self, key, value):
        if not 1 <= value <= 3:
            raise ValueError(f"pos_y must be 1-3, got {value}")
        return value
    
    def __repr__(self):
        return f"<Dungeons(vk_id={self.vk_id}, pos=({self.pos_x},{self.pos_y}), active={self.active})>"