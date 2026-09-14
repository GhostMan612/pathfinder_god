# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
from enum import Enum

class AskResponseBackend(str, Enum):
    OLLAMA = "ollama"
    RAW_EXCERPTS = "raw-excerpts"

    def __str__(self) -> str:
        return str(self.value)
