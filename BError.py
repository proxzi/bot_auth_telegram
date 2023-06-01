from enum import Enum

class BError(Enum):
    BotBlocked = 1
    ChatNotFound = 2
    RetryAfter = 3
    UserDeactivated = 4
    TelegramAPIError = 5
    Success = 6