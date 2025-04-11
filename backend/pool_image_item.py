import re
from typing import Dict, Any, List, Optional


class PoolImageItem:
    def __init__(self, id: int, origin: str = "random", successes: int = 0, failures: int = 0):
        self.id = id
        self.origin = origin
        self.successes = successes
        self.failures = failures

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "origin": self.origin,
            "successes": self.successes,
            "failures": self.failures
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PoolImageItem':
        return cls(
            id=data.get("id"),
            origin=data.get("origin", "random"),
            successes=data.get("successes", 0),
            failures=data.get("failures", 0)
        )

    @classmethod
    def from_parents(cls, id: int, parent_ids: List[int]) -> 'PoolImageItem':
        """
        Tworzy instancję PoolImageItem na podstawie rodziców.
        """
        if len(parent_ids) == 1:
            origin = f"child_of_{parent_ids[0]}"
        elif len(parent_ids) == 2:
            origin = f"child_of_{parent_ids[0]}_{parent_ids[1]}"
        else:
            raise ValueError("Niepoprawna liczba rodziców. Dozwolone: 1 lub 2.")
        return cls(id=id, origin=origin)

    @classmethod
    def from_noise(cls, id: int, parent_id: int, attempt: int) -> 'PoolImageItem':
        """
        Tworzy instancję PoolImageItem dla dziecka z szumu.
        """
        origin = f"child_of_{parent_id}_noise_{attempt}"
        return cls(id=id, origin=origin)

    # 🔍 Metody pomocnicze

    def is_child(self) -> bool:
        return self.origin.startswith("child_of_")

    def get_parents(self) -> List[int]:
        """
        Zwraca listę ID rodziców (jednego lub dwóch).
        Przykłady:
            "child_of_123" → [123]
            "child_of_123_456" → [123, 456]
            "child_of_123_noise_2" → [123]
        """
        if not self.is_child():
            return []

        match = re.match(r"child_of_(\d+)(_)?(\d+)?", self.origin)
        if match:
            id1 = int(match.group(1))
            id2 = match.group(3)
            return [id1] if id2 is None else [id1, int(id2)]

        match_noise = re.match(r"child_of_(\d+)_noise_\d+", self.origin)
        if match_noise:
            return [int(match_noise.group(1))]

        return []

    def is_from_noise(self) -> bool:
        return "noise_" in self.origin

    def get_noise_attempt(self) -> Optional[int]:
        """
        Zwraca numer próby szumu (jeśli dotyczy), np. z "child_of_123_noise_3" → 3
        """
        match = re.search(r"noise_(\d+)", self.origin)
        if match:
            return int(match.group(1))
        return None
