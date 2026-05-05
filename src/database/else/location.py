import json
from pathlib import Path
from sqlalchemy import select, delete
from database.core import get_session
from database.models import Locations, Edges


async def add_location(path: str) -> bool:
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    loc_data = data["location"]
    edges_data = data.get("edges", [])

    loc_external_id = loc_data["id"]  # это будет записано в Locations.id_location

    async with get_session() as session:
        # 1) найти локацию по внешнему id (id_location)
        res = await session.execute(
            select(Locations).where(Locations.id_location == loc_external_id)
        )
        loc = res.scalar_one_or_none()

        # 2) создать или обновить локацию (НЕ удаляем её => игроки не ломаются)
        if loc is None:
            loc = Locations(
                id_location=loc_external_id,
                name=loc_data["name"],
                description=loc_data["description"],
            )
            session.add(loc)
            await session.flush()  # чтобы появился loc.id (PK)
        else:
            loc.name = loc_data["name"]
            loc.description = loc_data["description"]

        # 3) перезаписать исходящие рёбра этой локации
        await session.execute(delete(Edges).where(Edges.from_id == loc.id))

        # 4) добавить рёбра, переводя to_id (id_location) -> Locations.id (PK)
        for e in edges_data:
            to_external_id = e["to_id"]

            res = await session.execute(
                select(Locations.id).where(Locations.id_location == to_external_id)
            )
            to_pk = res.scalar_one_or_none()
            if to_pk is None:
                raise ValueError(
                    f"В edges указан to_id={to_external_id}, но такой локации (id_location) нет в БД. "
                    f"Сначала загрузи файл этой локации."
                )

            session.add(Edges(from_id=loc.id, to_id=to_pk))

        await session.commit()
        return True