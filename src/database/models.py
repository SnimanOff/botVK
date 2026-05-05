from sqlalchemy import String, Integer, BigInteger, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
from typing import Optional, Dict, Any

# Модель локаций
class Locations(Base):
    __tablename__ = "locations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_location: Mapped[int] = mapped_column(Integer, unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500))
    
    # Связь путей с локациями
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
    from_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    to_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)

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