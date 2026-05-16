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
)

labeler = BotLabeler()


@labeler.raw_event(GroupEventType.MESSAGE_EVENT, dataclass=GroupTypes.MessageEvent)
async def router(event: GroupTypes.MessageEvent):
    payload = event.object.payload
    cmd = payload.get("cmd")
    user_id = event.object.user_id
    player = await UserService.GoC_user(user_id)
    
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
        
    elif cmd == "combat_action":
        await combat_action(event, player, payload)
        
    else:
        logger.warning("Неизвестная команда: {}", cmd)