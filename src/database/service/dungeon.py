import random
import json
from typing import Optional
from sqlalchemy import select
from database.core import get_session
from database.models import Dungeons, Players
from loguru import logger


class DungeonGenerator:
    VERTICAL_CHANCE = {
        1: 1.0,
        2: 0.6,
        3: 0.3,
    }
    
    ROOM_TYPES = {
        "combat": {"name": "Боевая комната", "chance": 0.70},
        "treasure": {"name": "Сокровищница", "chance": 0.20},
        "shrine": {"name": "Святилище", "chance": 0.10},
    }
    
    START_ROOM = {
        "type": "start",
        "name": "Вход в подземелье",
        "description": "Тёмный проход ведёт вглубь...",
    }
    BOSS_ROOM = {
        "type": "boss",
        "name": "Логово босса",
        "description": "Воздух густеет от зловония...",
    }
    EXIT_ROOM = {
        "type": "exit",
        "name": "Выход",
        "description": "Свет в конце туннеля!",
    }
    
    @classmethod
    def _roll_room_type(cls) -> str:
        roll = random.random()
        cumulative = 0.0
        logger.debug("Бросок типа комнаты, roll={:.4f}", roll)
        
        for rtype, data in cls.ROOM_TYPES.items():
            cumulative += data["chance"]
            logger.debug("проверка {}: cumulative={:.2f}", rtype, cumulative)
            if roll <= cumulative:
                logger.debug("выбран тип: {}", rtype)
                return rtype
        return "combat"
    
    @classmethod
    def _generate_floor(cls, x: int) -> dict:
        logger.debug("Генерация этажа x={}", x)
        rooms = {}
        
        if x == 1:
            rooms["1"] = cls.START_ROOM.copy()
            logger.debug("Этаж {}: стартовая комната", x)
            return rooms
        
        if x == 6:
            rooms["1"] = cls.BOSS_ROOM.copy()
            logger.debug("Этаж {}: босс", x)
            return rooms
        
        if x == 7:
            rooms["1"] = cls.EXIT_ROOM.copy()
            logger.debug("Этаж {}: выход", x)
            return rooms
        
        for y in [1, 2, 3]:
            chance = cls.VERTICAL_CHANCE[y]
            roll = random.random()
            logger.debug("y={}: chance={:.2f}, roll={:.4f}", y, chance, roll)
            
            if y == 3 and "2" not in rooms:
                logger.debug("Пропуск y=3: нет y=2")
                continue
            
            if roll <= chance:
                room_type = cls._roll_room_type()
                rooms[str(y)] = {
                    "type": room_type,
                    "name": cls.ROOM_TYPES[room_type]["name"],
                    "description": f"Комната {x},{y}",
                    "cleared": False,
                }
                logger.debug("Создана комната: {} ({})", room_type, rooms[str(y)]["name"])
            else:
                logger.debug("Комната не создана (roll > chance)")
        
        if "1" not in rooms:
            room_type = cls._roll_room_type()
            rooms["1"] = {
                "type": room_type,
                "name": cls.ROOM_TYPES[room_type]["name"],
                "description": f"Комната {x},1",
                "cleared": False,
            }
            logger.debug("Гарантия: создана комната y=1, тип={}", room_type)
        
        logger.debug("Этаж {} итого: {} комнат", x, len(rooms))
        return rooms
    
    @classmethod
    def _calculate_exits(cls, floors: dict) -> dict:
        logger.debug("Расчёт связей между комнатами")
        result = {}
        
        for x_str, floor_data in floors.items():
            x = int(x_str)
            result[x_str] = {"rooms": {}}
            logger.debug("Обработка этажа x={}", x)
            
            for y_str, room in floor_data.items():
                y = int(y_str)
                exits = []
                
                next_x = x + 1
                next_floor = floors.get(str(next_x), {})
                for dy in [-1, 0, 1]:
                    next_y = y + dy
                    if str(next_y) in next_floor:
                        exits.append(f"{next_x},{next_y}")
                        logger.debug("Выход вперёд: ({},{})->({},{})", x, y, next_x, next_y)
                
                prev_x = x - 1
                prev_floor = floors.get(str(prev_x), {})
                for dy in [-1, 0, 1]:
                    prev_y = y + dy
                    if str(prev_y) in prev_floor:
                        exits.append(f"{prev_x},{prev_y}")
                        logger.debug("Выход назад: ({},{})->({},{})", x, y, prev_x, prev_y)
                
                room_copy = dict(room)
                room_copy["exits"] = exits
                room_copy["coords"] = f"{x},{y}"
                result[x_str]["rooms"][y_str] = room_copy
                
                logger.debug("Комната ({},{}): {} выходов", x, y, len(exits))
        
        total_rooms = sum(len(f["rooms"]) for f in result.values())
        logger.debug("Связи рассчитаны, всего {} комнат", total_rooms)
        return result
    
    @classmethod
    def generate(cls) -> dict:
        logger.info("Начало генерации данжа")
        floors = {}
        
        for x in range(1, 8):
            floor_rooms = cls._generate_floor(x)
            floors[str(x)] = floor_rooms
        
        map_data = {
            "version": 1,
            "seed": random.randint(1000, 999999),
            "floors": cls._calculate_exits(floors),
        }
        
        total_rooms = sum(len(f) for f in floors.values())
        logger.info(
            "Данж сгенерирован, seed={}, всего {} комнат",
            map_data["seed"], total_rooms
        )
        logger.debug("Полная карта: {}", json.dumps(map_data, ensure_ascii=False))
        
        return map_data


class DungeonService:
    @staticmethod
    async def get_dungeon(vk_id: int) -> Optional[Dungeons]:
        logger.debug("Поиск активного данжа для vk_id={}", vk_id)
        async with get_session() as session:
            result = await session.execute(
                select(Dungeons)
                .where(Dungeons.vk_id == vk_id, Dungeons.active == True)
            )
            dungeon = result.scalar_one_or_none()
            
            if dungeon:
                logger.debug("Найден данж id={}", dungeon.id)
            else:
                logger.debug("Активный данж не найден")
            
            return dungeon
    
    @staticmethod
    async def has_active_dungeon(vk_id: int) -> bool:
        has = await DungeonService.get_dungeon(vk_id) is not None
        logger.debug("has_active_dungeon(vk_id={}) = {}", vk_id, has)
        return has
    
    @staticmethod
    async def create_dungeon(player: Players) -> Dungeons:
        logger.info("Создание данжа для vk_id={}", player.vk_id)
        
        abandoned = await DungeonService.abandon_dungeon(player.vk_id)
        if abandoned:
            logger.debug("Старый данж завершён")
        
        map_data = DungeonGenerator.generate()
        logger.debug("Карта сгенерирована, seed={}", map_data["seed"])
        
        async with get_session() as session:
            dungeon = Dungeons(
                vk_id=player.vk_id,
                map_data=map_data,
                pos_x=1,
                pos_y=1,
                active=True,
                rooms_cleared=0,
            )
            session.add(dungeon)
            logger.debug("Данж добавлен в сессию")
            
            await session.commit()
            await session.refresh(dungeon)
            logger.debug("Данж сохранён, id={}", dungeon.id)
            
            player.dungeon = True
            await session.commit()
            
            logger.info(
                "Данж создан для vk_id={}, id={}, pos=(1,1)",
                player.vk_id, dungeon.id
            )
            return dungeon
    
    @staticmethod
    async def abandon_dungeon(vk_id: int) -> bool:
        async with get_session() as session:
            result = await session.execute(
                select(Dungeons)
                .where(Dungeons.vk_id == vk_id, Dungeons.active == True)
            )
            dungeon = result.scalar_one_or_none()
            
            if dungeon:
                dungeon.active = False
                await session.commit()
                logger.debug("Данж id={} деактивирован", dungeon.id)
                return True
            
            logger.debug("Нечего завершать")
            return False
    
    @staticmethod
    async def get_current_room(dungeon: Dungeons) -> Optional[dict]:
        floor = dungeon.map_data.get("floors", {}).get(str(dungeon.pos_x))
        if not floor:
            logger.warning(
                "Этаж {} не найден в данже id={}",
                dungeon.pos_x, dungeon.id
            )
            return None
        
        room = floor.get("rooms", {}).get(str(dungeon.pos_y))
        if not room:
            logger.warning(
                "Комната ({},{}) не найдена в данже id={}",
                dungeon.pos_x, dungeon.pos_y, dungeon.id
            )
            return None
        
        logger.debug(
            "Текущая комната id={}: type={}, name={}",
            dungeon.id, room.get("type"), room.get("name")
        )
        return room
    
    @staticmethod
    async def get_room_at(dungeon: Dungeons, x: int, y: int) -> Optional[dict]:
        floor = dungeon.map_data.get("floors", {}).get(str(x))
        if not floor:
            logger.debug("Этаж {} не существует", x)
            return None
        
        room = floor.get("rooms", {}).get(str(y))
        if room:
            logger.debug(
                "Найдена комната ({},{}): type={}",
                x, y, room.get("type")
            )
        else:
            logger.debug("Комната ({},{}) не существует", x, y)
        
        return room
    
    @staticmethod
    async def can_move_to(dungeon: Dungeons, new_x: int, new_y: int) -> tuple[bool, str]:
        if not (1 <= new_x <= 7 and 1 <= new_y <= 3):
            return False, "За пределами данжа"
        
        floor = dungeon.map_data.get("floors", {}).get(str(new_x))
        if not floor:
            return False, "Этот путь ведёт в пустоту"
        
        room = floor.get("rooms", {}).get(str(new_y))
        if not room:
            return False, "Там нет комнаты"
        
        current_room = await DungeonService.get_current_room(dungeon)
        if current_room:
            exits = current_room.get("exits", [])
            target_key = f"{new_x},{new_y}"
            logger.debug(
                "Текущие выходы: {}, проверяем: {}",
                exits, target_key
            )
            if target_key not in exits:
                logger.debug("Отказ — нет выхода в ({},{})", new_x, new_y)
                return False, "Нет прохода в эту комнату"
        
        if new_y == 3:
            mid_room = floor.get("rooms", {}).get("2")
            if not mid_room:
                logger.debug("Отказ — нет y=2 для доступа к y=3")
                return False, "Нет пути на третий уровень"
        
        logger.debug("Разрешено движение в ({},{})", new_x, new_y)
        return True, ""
    
    @staticmethod
    async def move_to(dungeon: Dungeons, new_x: int, new_y: int) -> tuple[Dungeons, bool, str]:
        can_move, reason = await DungeonService.can_move_to(dungeon, new_x, new_y)
        if not can_move:
            return dungeon, False, reason
        
        async with get_session() as session:
            old_pos = (dungeon.pos_x, dungeon.pos_y)
            dungeon.pos_x = new_x
            dungeon.pos_y = new_y
            dungeon.rooms_cleared += 1
            logger.debug(
                "Позиция обновлена: {} -> ({},{})",
                old_pos, new_x, new_y
            )
            
            room = await DungeonService.get_current_room(dungeon)
            if room and not room.get("cleared", False):
                room["cleared"] = True
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(dungeon, "map_data")
            
            await session.commit()
            await session.refresh(dungeon)
            
            logger.debug(
                "Игрок {} переместился ({},{}) -> ({},{})",
                dungeon.vk_id, old_pos[0], old_pos[1], new_x, new_y
            )
            return dungeon, True, ""
    
    @staticmethod
    async def get_available_exits(dungeon: Dungeons) -> list[dict]:
        room = await DungeonService.get_current_room(dungeon)
        if not room:
            logger.debug("DungeonService: нет текущей комнаты, выходов 0")
            return []
        
        exits = []
        raw_exits = room.get("exits", [])
        
        for exit_coords in raw_exits:
            x, y = map(int, exit_coords.split(","))
            target = await DungeonService.get_room_at(dungeon, x, y)
            if target:
                exits.append({
                    "x": x,
                    "y": y,
                    "coords": exit_coords,
                    "type": target.get("type"),
                    "name": target.get("name"),
                    "cleared": target.get("cleared", False),
                })
        
        return exits
    
    @staticmethod
    async def is_completed(dungeon: Dungeons) -> bool:
        completed = dungeon.pos_x == 7
        return completed
    
    @staticmethod
    async def is_boss_room(dungeon: Dungeons) -> bool:
        is_boss = dungeon.pos_x == 6
        return is_boss
    
    @staticmethod
    async def mark_room_cleared(dungeon: Dungeons) -> Dungeons:
        room = await DungeonService.get_current_room(dungeon)
        if room and not room.get("cleared"):
            room["cleared"] = True
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(dungeon, "map_data")
            
            async with get_session() as session:
                await session.commit()
                await session.refresh(dungeon)
                logger.debug("Комната помечена cleared")
        else:
            logger.debug("Комната уже cleared или не найдена")
        
        return dungeon
    
    @staticmethod
    async def complete_dungeon(dungeon: Dungeons, success: bool = True) -> Dungeons:
        async with get_session() as session:
            dungeon.active = False
            
            if dungeon.player:
                old_dungeon_flag = dungeon.player.dungeon
                dungeon.player.dungeon = False
                logger.debug(
                    "DungeonService: player.dungeon {} -> False",
                    old_dungeon_flag
                )
            
            await session.commit()
            await session.refresh(dungeon)
            
            logger.info(
                "Данж id={} завершён, vk_id={}, rooms_cleared={}",
                dungeon.id, dungeon.vk_id, dungeon.rooms_cleared
            )
            return dungeon