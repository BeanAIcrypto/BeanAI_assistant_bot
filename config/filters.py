import logging
from typing import Any
from aiogram import types, Dispatcher
from aiogram.dispatcher.filters import BoundFilter

from db.dbworker import create_user

logger = logging.getLogger(__name__)


class GroupAutoRegisterFilter(BoundFilter):
    """
    Фильтр, предназначенный для автоматической регистрации пользователя в группе.
    """

    key = "auto_group"

    def __init__(self, auto_group: bool) -> None:
        self.auto_group = auto_group

    async def check(self, obj: Any) -> bool:
        """
        Проверяет, нужно ли автоматически регистрировать пользователя в групповом чате.

        Args:
            obj (Any): Объект, представляющий сообщение или callback-запрос.

        Returns:
            bool: True, если пользователь должен быть зарегистрирован автоматически, иначе False.
        """
        try:
            if isinstance(obj, types.Message):
                chat = obj.chat
                user_id = obj.from_user.id
                username = obj.from_user.username or "NoUserName"
            elif isinstance(obj, types.CallbackQuery):
                chat = obj.message.chat
                user_id = obj.from_user.id
                username = obj.from_user.username or "NoUserName"
            else:
                return False

            if chat.type in (types.ChatType.GROUP, types.ChatType.SUPERGROUP):

                create_user(user_id, username)

                return True

            elif chat.type == types.ChatType.PRIVATE:
                return True

            return False
        except Exception as error:
            logger.exception(
                f"[GroupAutoRegister] Ошибка при регистрации пользователя: {error}"
            )
            return False


class MentionBotFilter(BoundFilter):
    """
    Фильтр, который:
      - В (супер)группе пропускает (True), только если есть @bot_username в тексте/подписи.
      - В личке (PRIVATE) всегда True (пропускает).
      - В канале и прочих чатах можно вернуть False.
    """

    key = "mention_bot"

    def __init__(self, mention_bot: bool) -> None:
        self.mention_bot = mention_bot

    async def check(self, obj: Any) -> bool:
        try:
            if isinstance(obj, types.Message):
                chat = obj.chat
                text_or_caption = obj.text or obj.caption or ""
            elif isinstance(obj, types.CallbackQuery):
                chat = obj.message.chat
                text_or_caption = obj.message.text or obj.message.caption or ""
            else:
                return False

            if chat.type == types.ChatType.PRIVATE:
                return True

            if chat.type in (types.ChatType.GROUP, types.ChatType.SUPERGROUP):
                bot_user = await obj.bot.me
                mention = f"@{bot_user.username.lower()}"
                return mention in text_or_caption.lower()

            return False

        except Exception as error:
            logger.exception(
                f"[MentionBotFilter] Ошибка при проверке упоминания бота: {error}"
            )
            return False


def setup_filters(dp: Dispatcher) -> None:
    dp.filters_factory.bind(GroupAutoRegisterFilter)
    dp.filters_factory.bind(MentionBotFilter)
    logger.info(
        "[Filters] GroupAutoRegisterFilter и MentionBotFilter подключены."
    )
