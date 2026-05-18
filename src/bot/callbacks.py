from vkbottle import GroupEventType, GroupTypes
from vkbottle.bot import BotLabeler
from loguru import logger
from database.service.user import UserService

from bot.handlers.move import handle_move
from bot.handlers.features.shop import (
    shop_open,
    shop_category,
    shop_buy,
    shop_confirm,
    back_to_location,
)
from bot.handlers.features.dungeon import (
    enter_dungeon,
    dungeon_move,
    combat_action,
    start_combat,
    snackbar,
    delete,
    treasure_open,
    shrine_use,
)

labeler = BotLabeler()


@labeler.raw_event(GroupEventType.MESSAGE_EVENT, dataclass=GroupTypes.MessageEvent)
async def router(event: GroupTypes.MessageEvent):
    payload = event.object.payload
    cmd = payload.get("cmd")
    user_id = event.object.user_id
    player = await UserService.GoC_user(user_id)

    logger.info(">>> ROUTER CALLED: cmd={}, payload={}", cmd, payload)
    logger.debug("Callback: cmd={}, user={}", cmd, user_id)
    
    if cmd == "move":
        await handle_move(event, player, payload)
        
    elif cmd == "feature":
        feature_id = payload.get("id")
        if feature_id == "shop":
            await shop_open(event, player)
        elif feature_id == "back_to_location":
            await back_to_location(event, player)
        elif feature_id == "enter_dungeon":
            await enter_dungeon(event, player)
        else:
            logger.warning("Неизвестная фича: {}", feature_id)
            
    elif cmd == "shop_category":
        await shop_category(event, player, payload)
        
    elif cmd == "shop_buy":
        await shop_buy(event, player, payload)
        
    elif cmd == "shop_confirm":
        await shop_confirm(event, player, payload)
        
    elif cmd == "dungeon_move":
        await dungeon_move(event, player, payload)
        
    elif cmd == "start_combat":
        dungeon, ok = await UserService.get_active_dungeon(player.vk_id)
        if not ok:
            await snackbar(event, "Нет активного данжа")
            return
        await start_combat(event, player, dungeon)
        
    elif cmd == "combat_action":
        await combat_action(event, player, payload)
    
    elif cmd == "treasure_open":
        from bot.handlers.features.dungeon import treasure_open
        await treasure_open(event, player, payload)
        
    elif cmd == "shrine_use":
        from bot.handlers.features.dungeon import shrine_use
        await shrine_use(event, player, payload)

    elif feature_id == "exit_dungeon":
        dungeon, ok = await UserService.get_active_dungeon(player.vk_id)
        if ok:
            await UserService.exit_dungeon(player)
        await back_to_location(event, player)
    else:
        logger.warning("Неизвестная команда: {}", cmd)