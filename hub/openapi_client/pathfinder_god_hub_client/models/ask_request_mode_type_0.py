# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
from enum import Enum

class AskRequestModeType0(str, Enum):
    BOSS = "boss"
    CAMPAIGN = "campaign"
    CHARACTER = "character"
    ENCOUNTER = "encounter"
    MAP = "map"
    MONSTER = "monster"
    NPC = "npc"

    def __str__(self) -> str:
        return str(self.value)
