from sqlalchemy import select
from database.core import get_session
from database.models import Players, Items, Locations, Edges
from loguru import logger
from sqlalchemy.orm.attributes import flag_modified
from settings import settings
from effects import EFFECTS

class UserService:
    
    @staticmethod
    async def GoC_user(vk_id: int) -> Players:
        """
        get or create user 
        
        Ищет профиль пользователя в базе данных по vk_id
        При ненаходе создаёт профиль 
        
        Возвращает модель игрока
        """
        async with get_session() as session:
            result = await session.execute(
                select(Players)
                .where(Players.vk_id == vk_id)
            )
            player = result.scalar_one_or_none()
            
            if player:
                logger.debug("Игрок vk_id={} уже существует, id={}", player.vk_id, player.id)
                return player
            
            player = Players(
                vk_id = vk_id,
            )
            
            session.add(player)
            await session.commit()
            await session.refresh(player)
            
            logger.debug("Создан игрок id={}, vk_id={}", player.id, vk_id)
            return player
        
    @staticmethod
    async def get_item(code: str) -> tuple[Items | None, bool]:
        """
        get item 

        Получение предмета из SQL бд

        Возвращает модель предмета и результат операции
        """
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
        """
        give item

        Выдача предмета по модели и коду предмета

        Возвращает или изменённое или неизменённый профиль и результат операции
        """
        async with get_session() as session:
            item = await UserService.get_item(item_code)

            if not item:
                logger.error("Предмет с кодом {} не найден", item_code)
                return player, False
            
            if item.type == "weapon":
                player.inventory["weapon"] = item.code
            elif item.type == "armor":
                player.inventory["armor"] = item.code
            elif item.type == "ring":
                player.inventory["ring"] = item.code
            else:
                player.inventory["bag"].append(item.code)

            flag_modified(player, "inventory")
            
            session.add(player)
            await session.commit()
            await session.refresh(player)
            
            logger.debug("Предмет {} успешно выдан игроку vk_id={}", item_code, player.vk_id)

            return player, True
        
    @staticmethod
    async def GP_item(player: Players, slot: str) -> tuple[str, bool]:
        """
        get player item 
        
        Возвращает предмет в передаваемом слоте и результат операции
        """
        code = player.inventory.get(slot)
        
        if not code: 
            logger.debug("Слот {}, пуст у игрока {}", slot, player.vk_id)
            return code, False
        
        logger.debug("Найден предмет {} в слоте {}", code, slot)
        return code, True
    
    @staticmethod
    async def get_paths(location_id: int) -> list[list | None, bool]:
        """
        get paths 
        
        Возвращает список локаций куда можно попасть и результат операции
        """
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
        """
        player move 
        
        Метод получая модель игрока и ход, проверяет возможность хода
        После чего если ход возможен перемещает игрока
        
        Возвращает модель игрока и результат операции
        """
        location = player.location_id
        async with get_session() as session:
            paths, ok = await UserService.get_paths(location)
            if not ok:
                return player, False
            
            available_ids = [loc.id_location for loc in paths]
            
            if move not in available_ids:
                return player, False
            
            player.location_id = move
            await session.commit()
            await session.refresh(player)
            return player, True
        
    @staticmethod
    async def Go_items(player: Players, item_type: str) -> tuple[list[str], bool]:
        """
        get other items
        
        Получает все предметы не принадлежащие игроку
        
        возвращает список (list) предметов и результат операции
        """
        async with get_session() as session:
            player_codes = set()
            
            if item_type == "weapon":
                if player.inventory.get("weapon"):
                    player_codes.add(player.inventory["weapon"])
            elif item_type == "armor":
                if player.inventory.get("armor"):
                    player.codes.add(player.inventory["armor"])
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
    async def enter_dungeon(player: Players) -> tuple[Players, bool]:
        """
        enter dungeon 
        
        Запускает пользователя в данж при выполнении условий
        
        Возвращает модель игрока и результат операции
        """
        in_dungeon = player.dungeon
        player_location = player.location_id
        enter_location = settings.DUNGEON_LOCATION
        
        if in_dungeon:
            logger.warning("Игрок {} попытался войти в данж, хотя уже в нём", player.vk_id)
            return player, False

        if player_location != enter_location:
            logger.warning("Игрок {} попытался войти в данж, хотя не находится на нужной клетке", player.vk_id)
            return player, False

        async with get_session() as session:
            player.dungeon = True
            await session.commit()
            await session.refresh(player)
            return player, True
        
    @staticmethod
    async def exit_dungeon(player: Players) -> tuple[Players, bool]:
        """
        exit dungeon 
        
        Выпускает пользователя в данж при выполнении условий
        
        Возвращает модель игрока и результат операции
        """
        in_dungeon = player.dungeon
        exit_location = settings.DUNGEON_LOCATION
        
        if not in_dungeon:
            logger.warning("Игрок {} попытался выйти из данжа, хотя там не находится", player.vk_id)
            return player, False
        
        async with get_session() as session:
            player.dungeon = False
            player.location_id = exit_location
            await session.commit()
            await session.refresh(player)
            return player, True
    
    @staticmethod
    async def remove_item(player: Players, slot: str) -> tuple[Players, bool]:
        """
        remove item
        
        Удаляет предмет из указанного слота или сумки по индексу
        
        Возвращает модель игрока и результат операции
        """
        inventory = player.inventory
        async with get_session() as session:
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
            
            await session.commit()
            await session.refresh(player)
            logger.debug("Предмет удалён из слота {} у игрока {}", slot, player.vk_id)
            return player, True

    @staticmethod
    async def remove_from_bag(player: Players, index: int) -> tuple[Players, bool]:
        """
        remove from bag
        
        Удаляет предмет из сумки по индексу
        
        Возвращает модель игрока и результат операции
        """
        async with get_session() as session:
            bag = player.inventory.get("bag", [])
            
            if index < 0 or index >= len(bag):
                logger.debug("Индекс {} вне диапазона сумки у игрока {}", index, player.vk_id)
                return player, False
            
            removed = bag.pop(index)
            player.inventory["bag"] = bag
            
            await session.commit()
            await session.refresh(player)
            logger.debug("Предмет {} удалён из сумки у игрока {}", removed, player.vk_id)
            return player, True
        
    @staticmethod
    async def use_item(player: Players, index: int) -> tuple[Players, bool]:
        """
        use item 
        
        Использует предмет из сумки по индексу, после чего удаляет его 
        
        Эффекты работают через database/effects
        
        Возвращает модель игрока и результат выполнения
        """
        bag = player.inventory.get("bag", [])
        
        if index < 0 or index >= len(bag):
            logger.debug("Индекс {} вне диапазона у игрока {}", index, player.vk_id)
            return player, False
        
        code = bag[index]
        item, ok = await UserService.get_item(code)
        
        if not ok:
            logger.error("Предмет {} не найден в БД", code)
            return player, False
        
        effect_name = item.stats.get("effect")
        value = item.stats.get("value")
        
        effect_func = EFFECTS.get(effect_name)
        if not effect_func:
            logger.debug("Эффект {} не найден для предмета {}", effect_name, code)
            return player, False
        
        player, ok = await effect_func(player, value)
        if not ok:
            return player, False
        
        bag.pop(index)
        player.inventory["bag"] = bag
        
        async with get_session() as session:
            merged = await session.merge(player)
            await session.commit()
            await session.refresh(merged)
            logger.debug("Предмет {} использован игроком {}", code, player.vk_id)
            return merged, True
    
    @staticmethod
    async def add_balance(player: Players, amount: int) -> tuple[Players, bool]:
        """
        add balance
        
        Увеличивает баланс игрока
        
        Возвращает модель игрока и результат выполнения
        """
        if amount <= 0:
            logger.debug("Сумма {} не положительна", amount)
            return player, False

        async with get_session() as session:
            player.balance += amount
            merged = await session.merge(player)
            await session.commit()
            await session.refresh(merged)
            logger.debug("Игрок {} получил {} монет, баланс: {}", player.vk_id, amount, merged.balance)
            return merged, True

    @staticmethod
    async def buy_item(player: Players, item_code: str) -> tuple[Players, bool]:
        item, ok = await UserService.get_item(item_code)
        
        if not ok:
            logger.error("Предмет {} не найден", item_code)
            return player, False
        
        if not item.slot:
            bag = player.inventory.get("bag", [])
            if len(bag) > 20:
                logger.debug("Сумка полна у игрока {}", player.vk_id)
                return player, False
        
        old_item_code = player.inventory.get(item.slot) if item.slot else None
        
        sell_price = 0
        if old_item_code:
            old_item, found = await UserService.get_item(old_item_code)
            if found:
                sell_price = old_item.price // 2
        
        final_price = item.price - sell_price
        
        if player.balance < final_price:
            logger.debug("У игрока {} недостаточно: {} < {}", player.vk_id, player.balance, final_price)
            return player, False
        
        async with get_session() as session:
            player.balance -= final_price
            
            if item.slot:
                player.inventory[item.slot] = item.code
            else:
                player.inventory["bag"].append(item.code)
            
            merged = await session.merge(player)
            await session.commit()
            await session.refresh(merged)
            
            logger.info(
                "Игрок {} купил {} за {} (продал {} за {})",
                player.vk_id, item.name, final_price, old_item_code, sell_price
            )
            return merged, True