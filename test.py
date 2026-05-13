# C:\Users\sidor\Desktop\botVK\test_generator.py
import random
import json
from loguru import logger


class DungeonGenerator:
    VERTICAL_CHANCE = {1: 1.0, 2: 0.6, 3: 0.3}
    ROOM_TYPES = {
        "combat": {"name": "Боевая комната", "chance": 0.70},
        "treasure": {"name": "Сокровищница", "chance": 0.20},
        "shrine": {"name": "Святилище", "chance": 0.10},
    }
    START_ROOM = {"type": "start", "name": "Вход в подземелье", "description": "..."}
    BOSS_ROOM = {"type": "boss", "name": "Логово босса", "description": "..."}
    EXIT_ROOM = {"type": "exit", "name": "Выход", "description": "..."}

    @classmethod
    def _roll_room_type(cls) -> str:
        roll = random.random()
        cumulative = 0.0
        for rtype, data in cls.ROOM_TYPES.items():
            cumulative += data["chance"]
            if roll <= cumulative:
                return rtype
        return "combat"

    @classmethod
    def _generate_floor(cls, x: int) -> dict:
        rooms = {}
        if x == 1:
            rooms["1"] = cls.START_ROOM.copy()
            return rooms
        if x == 6:
            rooms["1"] = cls.BOSS_ROOM.copy()
            return rooms
        if x == 7:
            rooms["1"] = cls.EXIT_ROOM.copy()
            return rooms
        
        for y in [1, 2, 3]:
            chance = cls.VERTICAL_CHANCE[y]
            if y == 3 and "2" not in rooms:
                continue
            if random.random() <= chance:
                room_type = cls._roll_room_type()
                rooms[str(y)] = {
                    "type": room_type,
                    "name": cls.ROOM_TYPES[room_type]["name"],
                    "description": f"Комната {x},{y}",
                    "cleared": False,
                }
        
        if "1" not in rooms:
            room_type = cls._roll_room_type()
            rooms["1"] = {
                "type": room_type,
                "name": cls.ROOM_TYPES[room_type]["name"],
                "description": f"Комната {x},1",
                "cleared": False,
            }
        return rooms

    @classmethod
    def _calculate_exits(cls, floors: dict) -> dict:
        result = {}
        for x_str, floor_data in floors.items():
            x = int(x_str)
            result[x_str] = {"rooms": {}}
            for y_str, room in floor_data.items():
                y = int(y_str)
                exits = []
                for dx in [-1, 1]:
                    nx = x + dx
                    nf = floors.get(str(nx), {})
                    for dy in [-1, 0, 1]:
                        ny = y + dy
                        if str(ny) in nf:
                            exits.append(f"{nx},{ny}")
                room_copy = dict(room)
                room_copy["exits"] = exits
                room_copy["coords"] = f"{x},{y}"
                result[x_str]["rooms"][y_str] = room_copy
        return result

    @classmethod
    def generate(cls) -> dict:
        floors = {}
        for x in range(1, 8):
            floors[str(x)] = cls._generate_floor(x)
        return {
            "version": 1,
            "seed": random.randint(1000, 999999),
            "floors": cls._calculate_exits(floors),
        }


async def main():
    for i in range(1, 11):
        map_data = DungeonGenerator.generate()
        filename = f"dungeon_{i:02d}_seed{map_data['seed']}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(map_data, f, ensure_ascii=False, indent=2)
        print(f"{filename} сохранён")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())