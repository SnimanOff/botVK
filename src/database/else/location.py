import json
from pathlib import Path
from sqlalchemy import select, delete
from database.core import get_session
from database.models import Locations, Edges


async def add_location(path: str, replace_edges: bool = True) -> bool:
    """
    Если path = файл (*.json) -> загрузит 1 локацию.
    Если path = папка -> пробежится по всем *.json и:
      1) добавит/обновит ВСЕ локации
      2) добавит/синхронизирует ВСЕ рёбра

    replace_edges=True  -> для каждой локации перезапишет исходящие рёбра ровно как в json
    replace_edges=False -> только добавит недостающие рёбра (лишние не трогает)
    """

    p = Path(path)

    files = sorted(p.glob("*.json")) if p.is_dir() else [p]
    if not files:
        raise FileNotFoundError(f"Не найдено json-файлов по пути: {p}")

    # читаем все json
    raw = [json.loads(f.read_text(encoding="utf-8")) for f in files]

    async with get_session() as session:
        # 1) UPSERT всех локаций, собираем мапу id_location -> locations.id (PK)
        ext_to_pk: dict[int, int] = {}

        for data in raw:
            location_data = data["location"]
            ext_id = int(location_data["id"])  # внешний id из json -> Locations.id_location

            res = await session.execute(
                select(Locations).where(Locations.id_location == ext_id)
            )
            location = res.scalar_one_or_none()

            if location is None:
                location = Locations(
                    id_location=ext_id,
                    name=location_data["name"],
                    description=location_data["description"],
                )
                session.add(location)
                await session.flush()  # получаем location.id (PK)
            else:
                location.name = location_data["name"]
                location.description = location_data["description"]

            ext_to_pk[ext_id] = location.id

        # 2) Синхронизация рёбер
        for data in raw:
            location_data = data["location"]
            edges_data = data.get("edges", [])

            from_ext_id = int(location_data["id"])
            from_pk = ext_to_pk[from_ext_id]

            desired_to_pks: set[int] = set()

            for e in edges_data:
                to_ext_id = int(e["to_id"])

                # если целевая локация не была в загруженных файлах — попробуем найти в БД
                to_pk = ext_to_pk.get(to_ext_id)
                if to_pk is None:
                    res = await session.execute(
                        select(Locations.id).where(Locations.id_location == to_ext_id)
                    )
                    to_pk = res.scalar_one_or_none()

                if to_pk is None:
                    raise ValueError(
                        f"В edges указан to_id={to_ext_id}, но такой локации (id_location) нет в БД. "
                        f"Добавь её json или создай в БД."
                    )

                desired_to_pks.add(int(to_pk))

            if replace_edges:
                # перезаписываем исходящие рёбра из from_pk
                await session.execute(delete(Edges).where(Edges.from_id == from_pk))
                for to_pk in desired_to_pks:
                    session.add(Edges(from_id=from_pk, to_id=to_pk))
            else:
                # добавляем только недостающие
                res = await session.execute(
                    select(Edges.to_id).where(Edges.from_id == from_pk)
                )
                existing = set(res.scalars().all())
                for to_pk in desired_to_pks - existing:
                    session.add(Edges(from_id=from_pk, to_id=to_pk))

        await session.commit()
        return True