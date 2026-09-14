# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
from enum import Enum

class AskRequestEdition(str, Enum):
    BOTH = "both"
    VALUE_0 = "1e"
    VALUE_1 = "2e"

    def __str__(self) -> str:
        return str(self.value)
