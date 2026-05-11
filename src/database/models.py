from sqlalchemy import String, Integer, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database.core import Base
from pathlib import Path
from typing import Optional
import json

DEFAULT_EQUIPMENT = json.loads(Path("default_equipment.json").read_text())

# Модель локаций
class Locations(Base):
    __tablename__ = "locations"
    
    id_location: Mapped[int] = mapped_column(Integer, primary_key=True)  # PK = твой ID из JSON
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500))
    
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
    balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dungeon: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False) # находится ли в данже
    
    inventory: Mapped[dict] = mapped_column(JSON, default=lambda:DEFAULT_EQUIPMENT.copy())
    
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