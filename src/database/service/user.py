from sqlalchemy import select, and_
from database.core import get_session
from database.models import Players, Items, Locations, Edges, Battles, Dungeons, Monsters
from loguru import logger
from sqlalchemy.orm.attributes import flag_modified
from settings import settings
from database.effects import EFFECTS
from database.service.dungeon import DungeonService, DungeonGenerator
import random

class UserService:
    
    @staticmethod
    async def GoC_user(vk_id: int) -> Players:
        async with get_session() as session:
            result = await session.execute(
                select(Players)
                .where(Players.vk_id == vk_id)
            )
            player = result.scalar_one_or_none()
            
            if player:
                logger.debug("Игрок vk_id={} уже существует, id={}", player.vk_id, player.id)
                await session.refresh(player)
                return player
            
            player = Players(
                vk_id = vk_id,
            )
            
            session.add(player)
            await session.commit()
            await session.refresh(player)
            
            logger.info("Создан новый игрок id={}, vk_id={}", player.id, vk_id)
            return player
        
    @staticmethod
    async def get_item(code: str) -> tuple[Items | None, bool]:
        async with get_session() as session:
            result = await session.execute(
                select(Items)
                .where(Items.code == code)
            )
            
            item = result.scalar_one_or_none()
            
            if not item:
                logger.debug("Запрашиваемый предмет не найден, код искуемого: {}", code)
                return item, False
            else:
                logger.debug("Запрашиваемый предмет найден и передан: {}", code)
                return item, True
                

    @staticmethod
    async def give_item(player: Players, item_code: str) -> tuple[Players, bool]:
        async with get_session() as session:
            item, success = await UserService.get_item(item_code)

            if not success:
                logger.error("Предмет с кодом {} не найден", item_code)
                return player, False
            
            player = await session.merge(player)
            
            if item.type == "weapon":
                player.inventory["weapon"] = item.code
            elif item.type == "armor":
                player.inventory["armor"] = item.code
            elif item.type == "ring":
                player.inventory["ring"] = item.code
            else:
                player.inventory["bag"].append(item.code)

            flag_modified(player, "inventory")
            
            await session.commit()
            await session.refresh(player)
            
            logger.debug("Предмет {} успешно выдан игроку vk_id={}", item_code, player.vk_id)

            return player, True
        
    @staticmethod
    async def GP_item(player: Players, slot: str) -> tuple[str, bool]:
        code = player.inventory.get(slot)
        
        if not code: 
            logger.debug("Слот {}, пуст у игрока {}", slot, player.vk_id)
            return code, False
        
        logger.debug("Найден предмет {} в слоте {}", code, slot)
        return code, True
    
    @staticmethod
    async def get_paths(location_id: int) -> list[list | None, bool]:
        async with get_session() as session:
            result = await session.execute(
                select(Locations)
                .join(Edges, Edges.to_id == Locations.id_location)
                .where(Edges.from_id == location_id)
            )
            
            locations = result.scalars().all()
            
            if not locations:
                return [], False
            
            return list(locations), True
        
    @staticmethod
    async def player_move(player: Players, move: int) -> tuple[Players, bool]:
        async with get_session() as session:
            result = await session.execute(
                select(Players).where(Players.id == player.id)
            )
            fresh_player = result.scalar_one()
            current_location = fresh_player.location_id
            
            paths, ok = await UserService.get_paths(current_location)
            if not ok:
                return fresh_player, False
            
            available_ids = [loc.id_location for loc in paths]
            
            if move not in available_ids:
                logger.warning(
                    "Игрок {}: ход {} недоступен из локации {}. Доступны: {}",
                    fresh_player.vk_id, move, current_location, available_ids
                )
                return fresh_player, False
            
            fresh_player.location_id = move
            await session.commit()
            await session.refresh(fresh_player)
            
            logger.debug(
                "Игрок {}: {} → {}",
                fresh_player.vk_id, current_location, move
            )
            return fresh_player, True
        
    @staticmethod
    async def Go_items(player: Players, item_type: str) -> tuple[list[str], bool]:
        async with get_session() as session:
            player_codes = set()
            
            if item_type == "weapon":
                if player.inventory.get("weapon"):
                    player_codes.add(player.inventory["weapon"])
            elif item_type == "armor":
                if player.inventory.get("armor"):
                    player_codes.add(player.inventory["armor"])
            elif item_type == "ring":
                if player.inventory.get("ring"):
                    player_codes.add(player.inventory["ring"])
            else:
                player_codes.update(player.inventory.get("bag", []))
            
            result = await session.execute(
                select(Items.code)
                .where(Items.type == item_type)
            )
            all_codes = {row[0] for row in result.all()}
            
            available = list(all_codes - player_codes)
            
            if not available:
                logger.debug("Нет доступных предметов типа {} для игрока {}", item_type, player.vk_id)
                return [], False
            
            logger.debug("Найдено {} предметов типа {} для игрока {}", len(available), item_type, player.vk_id)
            return available, True
    
    @staticmethod
    async def get_location(location_id: int) -> tuple[Locations, bool]:
        async with get_session() as session:
            try:
                result = await session.execute(
                    select(Locations)
                    .where(Locations.id_location == location_id)
                )
                return result.scalar_one_or_none(), True
            
            except Exception as error:
                logger.debug("Получение локации по id={} не удалось из-за ошибки: {}", location_id, error)
                return None, False
                
    @staticmethod
    async def enter_dungeon(player: Players) -> tuple[Players, bool]:
        player_location = player.location_id
        enter_location = settings.DUNGEON_LOCATION

        existing, ok = await UserService.get_active_dungeon(player.id)
        if ok:
            logger.warning("Игрок {} уже в активном данже", player.id)
            return player, False

        if player_location != enter_location:
            logger.warning("Игрок {} не на входе в данж", player.id)
            return player, False

        dungeon, ok = await UserService.create_dungeon(player)
        if not ok:
            return player, False

        async with get_session() as session:
            player = await session.merge(player)
            player.in_dungeon = True
            await session.commit()
            await session.refresh(player)

        return player, True
        
    @staticmethod
    async def exit_dungeon(player: Players) -> tuple[Players, bool]:
        dungeon, ok = await UserService.get_active_dungeon(player.vk_id)
        if not ok:
            logger.warning("Игрок {} не в данже", player.id)
            return player, False

        async with get_session() as session:
            dungeon = await session.merge(dungeon)
            dungeon.active = False
            await session.commit()

            player = await session.merge(player)
            player.location_id = settings.HUB_LOCATION
            player.in_dungeon = False
            await session.commit()
            await session.refresh(player)
            return player, True
    
    @staticmethod
    async def remove_item(player: Players, slot: str) -> tuple[Players, bool]:
        async with get_session() as session:
            player = await session.merge(player)
            inventory = player.inventory
            
            if slot in ["weapon", "armor", "ring"]:
                if not inventory.get(slot):
                    logger.debug("Слот {} уже пуст у игрока {}", slot, player.vk_id)
                    return player, False
                
                inventory[slot] = None
                
            elif slot == "bag":
                logger.error("Для сумки данный метод не подходит, используй remove_from_bag с индексом")
                return player, False
            
            else:
                logger.error("Неизвестный слот: {}", slot)
                return player, False
            
            flag_modified(player, "inventory")
            await session.commit()
            await session.refresh(player)
            logger.debug("Предмет удалён из слота {} у игрока {}", slot, player.vk_id)
            return player, True

    @staticmethod
    async def remove_from_bag(player: Players, index: int) -> tuple[Players, bool]:
        async with get_session() as session:
            player = await session.merge(player)
            bag = player.inventory.get("bag", [])
            
            if index < 0 or index >= len(bag):
                logger.debug("Индекс {} вне диапазона сумки у игрока {}", index, player.vk_id)
                return player, False
            
            removed = bag.pop(index)
            player.inventory["bag"] = bag
            
            flag_modified(player, "inventory")
            await session.commit()
            await session.refresh(player)
            logger.debug("Предмет {} удалён из сумки у игрока {}", removed, player.vk_id)
            return player, True
    
    
    @staticmethod
    async def use_item(player: Players, index: int) -> tuple[Players, bool]:
        bag = player.inventory.get("bag", [])
        if index < 0 or index >= len(bag):
            return player, False

        code = bag[index]
        item, ok = await UserService.get_item(code)
        if not ok:
            return player, False

        stats = item.stats   # dict, например {"stat": "attack", "modifier": 10, "duration": 3}

        if "stat" in stats and "modifier" in stats:
            async with get_session() as session:
                player = await session.merge(player)
                result = await session.execute(
                    select(Battles)
                    .where(and_(Battles.vk_id == player.vk_id,
                                Battles.status == True
                                )
                           )
                    .order_by(Battles.created_at.desc())
                )
                battle = result.scalar_one_or_none()
                if not battle:
                    logger.warning("Бафф вне боя – игнорируем")
                    return player, False

                state = battle.state
                state.setdefault("player_buffs", []).append(stats)
                flag_modified(battle, "state")
                await session.commit()
                logger.debug(f"Бафф {stats} добавлен игроку {player.vk_id}")

            bag.pop(index)
            player.inventory["bag"] = bag
            
            async with get_session() as session:
                merged = await session.merge(player)
                flag_modified(merged, "inventory")
                await session.commit()
                await session.refresh(merged)
                return merged, True
        else:
            effect_func = None
            value = None

            if "effect" in stats and "value" in stats:
                effect_func = EFFECTS.get(stats.get("effect"))
                value = stats.get("value")
            elif "heal" in stats:
                effect_func = EFFECTS.get("heal")
                value = stats.get("heal")
            else:
                for k in stats.keys():
                    if k in EFFECTS:
                        effect_func = EFFECTS.get(k)
                        value = stats.get(k)
                        break

            if not effect_func:
                return player, False

            player, ok = await effect_func(player, value)
            if not ok:
                return player, False

            bag.pop(index)
            player.inventory["bag"] = bag

            async with get_session() as session:
                merged = await session.merge(player)
                flag_modified(merged, "inventory")
                await session.commit()
                await session.refresh(merged)
                return merged, True
    
    @staticmethod
    async def add_balance(player: Players, amount: int) -> tuple[Players, bool]:
        if amount <= 0:
            logger.debug("Сумма {} не положительна", amount)
            return player, False

        async with get_session() as session:
            player = await session.merge(player)
            player.balance += amount
            await session.commit()
            await session.refresh(player)
            logger.debug("Игрок {} получил {} монет, баланс: {}", player.vk_id, amount, player.balance)
            return player, True

    @staticmethod
    async def buy_item(player: Players, item_code: str) -> tuple[Players, bool]:
        item, ok = await UserService.get_item(item_code)
        
        if not ok:
            logger.error("Предмет {} не найден", item_code)
            return player, False
        
        if not item.slot:
            bag = player.inventory.get("bag", [])
            if len(bag) >= 20:
                logger.debug("Сумка полна у игрока {}", player.vk_id)
                return player, False
        
        old_item_code = player.inventory.get(item.slot) if item.slot else None
        
        sell_price = 0
        if old_item_code:
            old_item, found = await UserService.get_item(old_item_code)
            if found:
                sell_price = old_item.price // 2
        
        final_price = max(0, item.price - sell_price)
        
        if player.balance < final_price:
            logger.debug("У игрока {} недостаточно: {} < {}", player.vk_id, player.balance, final_price)
            return player, False
        
        async with get_session() as session:
            player = await session.merge(player)
            player.balance -= final_price
            
            if item.slot:
                player.inventory[item.slot] = item.code
            else:
                player.inventory["bag"].append(item.code)
            
            flag_modified(player, "inventory")
            await session.commit()
            await session.refresh(player)
            
            logger.info(
                "Игрок {} купил {} за {} (продал {} за {})",
                player.vk_id, item.name, final_price, old_item_code, sell_price
            )
            return player, True
    
    @staticmethod
    async def get_total_stats(player: Players) -> dict:
        stats = {
            "health": player.health,
            "max_health": player.max_health,
            "attack": player.attack,
            "protection": player.protection,
        }
        
        for slot in ["weapon", "armor", "ring"]:
            item_code = player.inventory.get(slot)
            if item_code:
                item, ok = await UserService.get_item(item_code)
                if ok and item:
                    for stat, value in (item.stats or {}).items():
                        if stat in stats:
                            stats[stat] += value
        
        return stats

    @staticmethod
    async def get_equipment_price(player: Players) -> int:
        total = 0
        for slot in ["weapon", "armor", "ring"]:
            item_code = player.inventory.get(slot)
            if item_code:
                item, ok = await UserService.get_item(item_code)
                if ok and item:
                    total += item.price
        
        for bag_item in player.inventory.get("bag", []):
            item, ok = await UserService.get_item(bag_item)
            if ok and item:
                total += item.price
        
        return total
    
    @staticmethod
    def _generate_map() -> dict:
        rooms = {}
        for x in range(1, 8):
            rooms[f"{x},1"] = {
                "type": "combat",
                "name": f"Комната {x}",
                "description": "Тусклый факел освещает каменные стены. Воздух пахнет сыростью и страхом.",
                "cleared": False,
            }
        rooms["1,1"].update({
            "type": "start",
            "name": "Вход",
            "description": "Тяжёлые ворота захлопнулись за спиной. Перед тобой тёмный коридор.",
        })

        rooms["7,1"].update({
            "type": "exit",
            "name": "Выход",
            "description": "Лучи света пробиваются сквозь трещины. Свобода близко.",
        })

        rooms["6,1"].update({
            "type": "boss",
            "name": "Логово босса",
            "description": "Воздух густеет от зловония...",
        })
        
        candidates = [x for x in range(2, 7)]
        for x in random.sample(candidates, min(3, len(candidates))):
            kind = random.choice(["treasure", "shrine"])
            if kind == "treasure":
                rooms[f"{x},1"].update({
                    "type": "treasure",
                    "name": f"Комната {x}",
                    "description": "В углу поблескивает что-то золотое. Сундук стоит на каменном постаменте.",
                })
            else:
                rooms[f"{x},1"].update({
                    "type": "shrine",
                    "name": f"Комната {x}",
                    "description": "Древний алтарь пульсирует едва заметным голубым светом.",
                })
        return {"rooms": rooms}

    @staticmethod
    async def get_active_dungeon(vk_id: int) -> tuple[Dungeons | None, bool]:
        async with get_session() as session:
            result = await session.execute(
                select(Dungeons)
                .where(Dungeons.vk_id == vk_id, Dungeons.active == True)
            )
            d = result.scalar_one_or_none()
            return d, d is not None

    @staticmethod
    async def create_dungeon(player: Players) -> tuple[Dungeons | None, bool]:
        async with get_session() as session:
            old = await session.execute(select(Dungeons).where(Dungeons.vk_id == player.vk_id))
            old_dungeon = old.scalar_one_or_none()
            if old_dungeon:
                await session.delete(old_dungeon)
                await session.flush()

            map_data = UserService._generate_map()
            rooms = map_data["rooms"]
            
            for key, room in rooms.items():
                if room["type"] == "combat":
                    monster, ok = await UserService.get_random_monster()
                    if ok:
                        room["monster_code"] = monster.code
                        room["monster_name"] = monster.name
                elif room["type"] == "boss":
                    monster, ok = await UserService.get_random_boss()
                    if ok and monster:
                        room["monster_code"] = monster.code
                        room["monster_name"] = monster.name

            dungeon = Dungeons(
                vk_id=player.vk_id,
                map_data=map_data,
                pos_x=1,
                pos_y=1,
                active=True,
                rooms_cleared=0,
            )
            session.add(dungeon)
            await session.commit()
            await session.refresh(dungeon)
            return dungeon, True

    @staticmethod
    async def enter_dungeon_room(dungeon: Dungeons, player: Players) -> dict:
        key = f"{dungeon.pos_x},{dungeon.pos_y}"
        room = dungeon.map_data.get("rooms", {}).get(key)
        if not room:
            return {"message": "Вы в пустоте.", "type": "empty"}

        msg = f"{room["name"]}\n{room["description"]}"
        if room["type"] in ("combat", "boss") and not room.get("cleared"):
            async with get_session() as session:
                result = await session.execute(select(Monsters))
                monsters = result.scalars().all()
                
                if monsters:
                    monster = random.choice(monsters)
                    monster_name = monster.name
                else:
                    monster_name = "Неизвестный враг"
            
            msg += f"\n\n⚔️ {monster_name} готов к бою!"
            return {"message": msg, "type": room["type"], "battle_id": 0, "monster_name": monster_name}

        return {"message": msg, "type": room["type"]}

    @staticmethod
    async def get_available_exits(dungeon: Dungeons) -> tuple[list[dict], bool]:
        rooms = dungeon.map_data.get("rooms", {})
        cx = dungeon.pos_x
        exits = []
        for dx in (-1, 1):
            nx = cx + dx
            key = f"{nx},1"
            if key in rooms:
                r = rooms[key]
                exits.append({
                    "x": nx, "y": 1,
                    "type": r["type"],
                    "name": r["name"],
                    "cleared": r.get("cleared", False),
                })
        return exits, True

    @staticmethod
    async def get_random_monster() -> tuple[Monsters | None, bool]:
        async with get_session() as session:
            result = await session.execute(select(Monsters))
            monsters = result.scalars().all()
            if not monsters:
                return None, False
            return random.choice(monsters), True

    @staticmethod
    async def get_random_boss() -> tuple[Monsters | None, bool]:
        async with get_session() as session:
            result = await session.execute(
                select(Monsters).where(Monsters.rarity.in_(["rare", "epic", "legendary"]))
            )
            bosses = result.scalars().all()
            if bosses:
                return random.choice(bosses), True

            result = await session.execute(select(Monsters))
            all_monsters = result.scalars().all()
            if not all_monsters:
                return None, False
            return random.choice(all_monsters), True

    @staticmethod
    async def move_in_dungeon(dungeon: Dungeons, new_x: int, new_y: int) -> tuple[Dungeons, bool, str]:
        if new_y != 1:
            return dungeon, False, "Только прямо."
        if not (1 <= new_x <= 7):
            return dungeon, False, "Конец коридора."
        if abs(new_x - dungeon.pos_x) != 1:
            return dungeon, False, "Только соседняя комната."
        key = f"{new_x},1"
        if key not in dungeon.map_data.get("rooms", {}):
            return dungeon, False, "Туда нет пути."
        dungeon.pos_x = new_x
        dungeon.pos_y = 1
        async with get_session() as session:
            merged = await session.merge(dungeon)
            await session.commit()
            await session.refresh(merged)
            return merged, True, ""

    @staticmethod
    async def move_to(dungeon: Dungeons, new_x: int, new_y: int) -> tuple[Dungeons, bool, str]:
        can_move, reason = await DungeonService.can_move_to(dungeon, new_x, new_y)
        if not can_move:
            return dungeon, False, reason
        
        async with get_session() as session:
            old_pos = (dungeon.pos_x, dungeon.pos_y)
            dungeon.pos_x = new_x
            dungeon.pos_y = new_y
            
            room = await DungeonService.get_current_room(dungeon)
            if room and not room.get("cleared", False):
                room["cleared"] = True
                dungeon.rooms_cleared += 1
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(dungeon, "map_data")
            
            merged = await session.merge(dungeon)
            await session.commit()
            await session.refresh(merged)
            
            logger.debug(
                "Игрок {} переместился ({},{}) -> ({},{})",
                dungeon.vk_id, old_pos[0], old_pos[1], new_x, new_y
            )
            return merged, True, ""

    @staticmethod
    async def complete_dungeon(dungeon: Dungeons, success: bool = True) -> Dungeons:
        async with get_session() as session:
            dungeon = await session.merge(dungeon)
            dungeon.active = False
            
            if dungeon.player:
                dungeon.player.in_dungeon = False
                logger.debug(
                    "DungeonService: player.in_dungeon -> False"
                )
            
            await session.commit()
            await session.refresh(dungeon)
            
            logger.info(
                "Данж id={} завершён, vk_id={}, rooms_cleared={}",
                dungeon.id, dungeon.vk_id, dungeon.rooms_cleared
            )
            return dungeon

    @staticmethod
    async def get_dungeon_room(dungeon: Dungeons) -> tuple[dict | None, bool]:
        key = f"{dungeon.pos_x},{dungeon.pos_y}"
        room = dungeon.map_data.get("rooms", {}).get(key)
        if not room:
            return None, False
        return {
            "name": room["name"],
            "description": room["description"],
            "type": room["type"],
            "x": dungeon.pos_x,
            "y": dungeon.pos_y,
            "cleared": room.get("cleared", False),
        }, True
        
    @staticmethod
    async def get_active_battle(vk_id: int) -> tuple[Battles | None, bool]:
        async with get_session() as session:
            result = await session.execute(
                select(Battles)
                .where(Battles.vk_id == vk_id, Battles.status == True)
                .order_by(Battles.created_at.desc())
            )
            battle = result.scalar_one_or_none()
            return battle, battle is not None
        
    @staticmethod
    async def mark_room_cleared(dungeon: Dungeons):
        key = f"{dungeon.pos_x},{dungeon.pos_y}"
        rooms = dungeon.map_data.get("rooms", {})
        if key in rooms:
            rooms[key]["cleared"] = True
            async with get_session() as session:
                merged = await session.merge(dungeon)
                flag_modified(merged, "map_data")
                await session.commit()

    @staticmethod
    async def heal_player(player: Players) -> tuple[Players, bool]:
        async with get_session() as session:
            player.health = player.max_health
            merged = await session.merge(player)
            await session.commit()
            await session.refresh(merged)
            return merged, True

    @staticmethod
    async def add_dungeon_buff(dungeon: Dungeons, buff: dict):
        dungeon.map_data.setdefault("buffs", []).append(buff)
        async with get_session() as session:
            merged = await session.merge(dungeon)
            flag_modified(merged, "map_data")
            await session.commit()
    
    @staticmethod
    async def get_effective_stats(player: Players) -> dict:
        attack = player.attack
        protection = player.protection
        weapon_code = player.inventory.get("weapon")

        if weapon_code:
            weapon, ok = await UserService.get_item(weapon_code)
            if ok and weapon.stats:
                damage_bonus = weapon.stats.get("damage", 0)
                attack += damage_bonus
                logger.debug(
                    "Бонус атаки от оружия {}: +{}",
                    weapon_code, damage_bonus
                )
        
        armor_code = player.inventory.get("armor")
        if armor_code:
            armor, ok = await UserService.get_item(armor_code)
            if ok and armor.stats:
                defense_percent = armor.stats.get("defense_percent", 0)
                protection = int(protection * (1 + defense_percent / 100))
                logger.debug(
                    "Бонус защиты от брони {}: +{}% (итого: {})",
                    armor_code, defense_percent, protection
                )
        
        ring_code = player.inventory.get("ring")
        if ring_code:
            ring, ok = await UserService.get_item(ring_code)
            if ok and ring.stats:
                if "attack" in ring.stats:
                    attack_bonus = ring.stats.get("attack", 0)
                    attack += attack_bonus
                if "protection" in ring.stats:
                    prot_bonus = ring.stats.get("protection", 0)
                    protection += prot_bonus
                logger.debug(
                    "Бонусы от кольца {}: атака +{}, защита +{}",
                    ring_code, 
                    ring.stats.get("attack", 0),
                    ring.stats.get("protection", 0)
                )
        
        return {
            "attack": max(1, attack),
            "protection": max(1, protection)
        }
    
    @staticmethod
    async def get_total_stats(player: Players) -> dict:
        stats = await UserService.get_effective_stats(player)
        return {
            "health": player.health,
            "max_health": player.max_health,
            "attack": stats["attack"],
            "protection": stats["protection"],
            "balance": player.balance
        }