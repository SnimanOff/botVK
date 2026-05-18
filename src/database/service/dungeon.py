import random
import json
from typing import Optional
from sqlalchemy import select, and_
from database.core import get_session
from database.models import Dungeons, Players, Battles, Monsters, Items
from sqlalchemy.orm.attributes import flag_modified
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
        logger.debug("Расчёт связей между комнатами (линейный)")
        result = {}
        
        for x_str, floor_data in floors.items():
            x = int(x_str)
            result[x_str] = {"rooms": {}}
            
            for y_str, room in floor_data.items():
                y = int(y_str)
                exits = []
                
                # Только вперёд (x+1), назад нельзя
                next_x = x + 1
                next_floor = floors.get(str(next_x), {})
                for dy in [-1, 0, 1]:
                    next_y = y + dy
                    if str(next_y) in next_floor:
                        exits.append(f"{next_x},{next_y}")
                        logger.debug("Выход вперёд: ({},{})->({},{})", x, y, next_x, next_y)
                
                room_copy = dict(room)
                room_copy["exits"] = exits
                room_copy["coords"] = f"{x},{y}"
                result[x_str]["rooms"][y_str] = room_copy
                
                logger.debug("Комната ({},{}): {} выходов вперёд", x, y, len(exits))
        
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
    def get_room_at_sync(dungeon: Dungeons, x: int, y: int) -> Optional[dict]:
        """Синхронная версия для использования в хендлерах (данные уже в памяти)"""
        floor = dungeon.map_data.get("floors", {}).get(str(x))
        if not floor:
            return None
        return floor.get("rooms", {}).get(str(y))

    @classmethod
    def _calculate_exits(cls, floors: dict) -> dict:
        logger.debug("Расчёт связей (линейный, только вперёд)")
        result = {}
        
        for x_str, floor_data in floors.items():
            x = int(x_str)
            result[x_str] = {"rooms": {}}
            
            for y_str, room in floor_data.items():
                y = int(y_str)
                exits = []
                
                # Только вперёд (x+1), назад нельзя
                next_x = x + 1
                next_floor = floors.get(str(next_x), {})
                for dy in [-1, 0, 1]:
                    next_y = y + dy
                    if str(next_y) in next_floor:
                        exits.append(f"{next_x},{next_y}")
                        logger.debug("Выход вперёд: ({},{})->({},{})", x, y, next_x, next_y)
                
                room_copy = dict(room)
                room_copy["exits"] = exits
                room_copy["coords"] = f"{x},{y}"
                result[x_str]["rooms"][y_str] = room_copy
                
                logger.debug("Комната ({},{}): {} выходов", x, y, len(exits))
        
        total_rooms = sum(len(f["rooms"]) for f in result.values())
        logger.debug("Связи рассчитаны, всего {} комнат", total_rooms)
        return result

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
            dungeon = await session.merge(dungeon)  # <-- ВОТ ЭТО ДОБАВИЛ
            old_pos = (dungeon.pos_x, dungeon.pos_y)
            dungeon.pos_x = new_x
            dungeon.pos_y = new_y
            
            room = await DungeonService.get_current_room(dungeon)
            if room and not room.get("cleared", False):
                room["cleared"] = True
                dungeon.rooms_cleared += 1
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


class BattleService:
    """Сервис для управления боевой системой"""
    
    @staticmethod
    async def create_battle(player: Players, dungeon: Dungeons) -> tuple[Battles, bool]:
        """Создает новый бой с случайным противником"""
        logger.info("Создание боя для игрока vk_id={}", player.vk_id)
        
        # Получаем случайного противника
        async with get_session() as session:
            result = await session.execute(select(Monsters))
            monsters = result.scalars().all()
            
            if not monsters:
                logger.error("Противников в БД не найдено")
                return None, False
            
            monster = random.choice(monsters)
            
            # Рассчитываем характеристики врага на основе игрока
            enemy_health = max(20, int(player.max_health * 0.8))
            enemy_attack = max(5, int(player.attack * 0.7))
            enemy_protection = max(3, int(player.protection * 0.6))
            
            # Получаем зелья игрока для клавиатуры
            potions = await BattleService.get_player_potions(player)
            
            battle_state = {
                "enemy_name": monster_name,
                "enemy_health": enemy_health,
                "enemy_max_health": enemy_health,
                "enemy_attack": enemy_attack,
                "enemy_protection": enemy_protection,
                "enemy_stance": "normal",
                "player_health": player.health,
                "player_max_health": player.max_health,
                "player_stance": "normal",
                "turn": "player",
                "round": 1,
                "last_action": None,
                "combat_log": [],
                "player_potions": [{"index": p["index"], "name": p["name"]} for p in potions[:5]],
            }
            
            battle = Battles(
                vk_id=player.vk_id,
                state=battle_state,
                status=True,
            )
            
            session.add(battle)
            await session.commit()
            await session.refresh(battle)
            
            logger.info(
                "Бой создан: id={}, враг={}, игрок_hp={}, враг_hp={}",
                battle.id, monster.name, player.health, enemy_health
            )
            
            return battle, True
    
    @staticmethod
    async def get_active_battle(vk_id: int) -> tuple[Battles, bool]:
        """Получает активный бой игрока"""
        async with get_session() as session:
            result = await session.execute(
                select(Battles)
                .where(and_(Battles.vk_id == vk_id, Battles.status == True))
                .order_by(Battles.created_at.desc())
            )
            battle = result.scalar_one_or_none()
            return battle, battle is not None
    
    @staticmethod
    async def calculate_damage(attacker_attack: int, defender_protection: int, 
                              attacker_stance: str = "normal", 
                              defender_stance: str = "normal") -> int:
        """
        Расчет урона с учетом броней и стойки
        - Удар: урон = атака * 1.0
        - Защита у защищающегося: броня * 2
        """
        base_damage = max(1, attacker_attack - (defender_protection * 2 if defender_stance == "defend" else defender_protection))
        
        # Добавляем случайное отклонение ±15%
        variation = random.uniform(0.85, 1.15)
        final_damage = int(base_damage * variation)
        
        logger.debug(
            "Расчет урона: атака={}, защита={}, стойка_защиты={}, урон={}",
            attacker_attack, defender_protection, defender_stance, final_damage
        )
        
        return max(1, final_damage)
    
    @staticmethod
    async def player_action(battle: Battles, player: Players, action: str, potion_index: int = None) -> tuple[Battles, bool, str]:
        """
        Обработка действия игрока
        action: "attack" | "defend" | "potion"
        """
        if battle.state["turn"] != "player":
            return battle, False, "Не ваш ход"
        
        state = battle.state
        message = ""
        
        async with get_session() as session:
            if action == "attack":
                # Удар игрока
                damage = await BattleService.calculate_damage(
                    attacker_attack=player.attack,
                    defender_protection=state["enemy_protection"],
                    attacker_stance="normal",
                    defender_stance=state["enemy_stance"]
                )
                
                state["enemy_health"] -= damage
                state["last_action"] = f"Вы нанесли удар! Урон: {damage}"
                message = f"⚔️ Вы ударили {state['enemy_name']} на {damage} урона!"
                
                logger.info("Игрок vk_id={} атаковал, урон={}", player.vk_id, damage)
                
            elif action == "defend":
                # Защита игрока
                state["player_stance"] = "defend"
                state["last_action"] = "Вы заняли оборонительную стойку"
                message = "🛡️ Вы заняли оборонительную стойку! Броня удвоена."
                
                logger.info("Игрок vk_id={} защищается", player.vk_id)
                
            elif action == "potion":
                # Использование зелья
                if potion_index is None:
                    return battle, False, "Индекс зелья не указан"
                
                bag = player.inventory.get("bag", [])
                if potion_index < 0 or potion_index >= len(bag):
                    return battle, False, "Неверный индекс зелья"
                
                item_code = bag[potion_index]
                result = await session.execute(select(Items).where(Items.code == item_code))
                item = result.scalar_one_or_none()
                
                if not item:
                    return battle, False, "Зелье не найдено"
                
                # Применяем эффект зелья (восстановление здоровья)
                if "effect" in item.stats and item.stats["effect"] == "heal":
                    heal_amount = item.stats.get("value", 20)
                    state["player_health"] = min(state["player_max_health"], state["player_health"] + heal_amount)
                    message = f"💊 Вы выпили {item.name} и восстановили {heal_amount} HP!"
                    state["last_action"] = f"Выпил {item.name} (+{heal_amount} HP)"
                    
                    # Удаляем зелье из сумки
                    bag.pop(potion_index)
                    player.inventory["bag"] = bag
                    merged_player = await session.merge(player)
                    await session.commit()
                    
                    logger.info("Игрок vk_id={} использовал {}", player.vk_id, item.code)
                else:
                    return battle, False, "Это зелье не лечит"
            
            # Проверяем победу
            if state["enemy_health"] <= 0:
                state["status"] = "won"
                state["turn"] = "end"
                message += "\n\n🎉 Вы победили врага!"
                logger.info("Игрок vk_id={} победил {}", player.vk_id, state["enemy_name"])
                
                player.health = state["player_health"]
                
                merged_battle = await session.merge(battle)
                flag_modified(merged_battle, "state")
                await session.commit()
                await session.refresh(merged_battle)
                
                return merged_battle, True, message
            
            # Передаём ход врагу
            state["turn"] = "enemy"
            state["player_stance"] = "normal"  # Сброс стойки после каждого хода
            
            merged_battle = await session.merge(battle)
            flag_modified(merged_battle, "state")
            await session.commit()
            await session.refresh(merged_battle)
            
            return merged_battle, True, message
    
    @staticmethod
    async def enemy_action(battle: Battles, player: Players) -> tuple[Battles, str]:
        """Автоматическое действие противника"""
        state = battle.state
        
        # Враг выбирает действие: 70% атака, 30% защита
        action = "attack" if random.random() < 0.7 else "defend"
        message = ""
        
        async with get_session() as session:
            player = await session.merge(player)
            
            if action == "attack":
                damage = await BattleService.calculate_damage(
                    attacker_attack=state["enemy_attack"],
                    defender_protection=player.protection,
                    attacker_stance="normal",
                    defender_stance=state["player_stance"]
                )
                
                state["player_health"] -= damage
                message = f"⚔️ {state['enemy_name']} атакует вас! Урон: {damage}"
                state["last_action"] = f"{state['enemy_name']} атакует! Урон: {damage}"
                
                logger.info("Враг {} атаковал, урон={}", state["enemy_name"], damage)
                
            else:  # defend
                state["enemy_stance"] = "defend"
                message = f"🛡️ {state['enemy_name']} занимает оборонительную стойку!"
                state["last_action"] = f"{state['enemy_name']} защищается"
                
                logger.info("Враг {} защищается", state["enemy_name"])
            
            player.health = max(0, state["player_health"])
            
            # Проверяем поражение
            if state["player_health"] <= 0:
                state["status"] = "lost"
                state["turn"] = "end"
                message += f"\n\n💀 Вы повержены {state['enemy_name']}!"
                logger.info("Игрок vk_id={} погиб в бою", battle.vk_id)
            else:
                # Передаём ход игроку
                state["turn"] = "player"
                state["enemy_stance"] = "normal"  # Сброс стойки
            
            merged_battle = await session.merge(battle)
            flag_modified(merged_battle, "state")
            await session.commit()
            await session.refresh(merged_battle)
            
            return merged_battle, message
    
    @staticmethod
    async def end_battle(battle: Battles) -> Battles:
        """Завершить бой"""
        async with get_session() as session:
            battle.status = False
            merged = await session.merge(battle)
            await session.commit()
            await session.refresh(merged)
            
            logger.info("Бой id={} завершён", battle.id)
            return merged
    
    @staticmethod
    async def get_player_potions(player: Players) -> list[dict]:
        """Получить список зелий в инвентаре игрока"""
        potions = []
        bag = player.inventory.get("bag", [])
        
        async with get_session() as session:
            for idx, item_code in enumerate(bag):
                result = await session.execute(select(Items).where(Items.code == item_code))
                item = result.scalar_one_or_none()
                
                if item and item.type == "potion":
                    potions.append({
                        "index": idx,
                        "code": item_code,
                        "name": item.name,
                        "effect": item.stats.get("effect"),
                        "value": item.stats.get("value"),
                    })
        
        return potions