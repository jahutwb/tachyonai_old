"""
Pool Image Item module for TachyonAI.
This module provides a class for representing images in the genetic pool.
"""
import re
from typing import Dict, Any, List, Optional


class PoolImageItem:
    """Class representing an image in the genetic pool.

    Attributes:
        id: Image ID
        origin: Origin of the image ("random", "bought", or "child_of_*")
        successes: Number of successful selections
        failures: Number of failed selections
    """

    def __init__(self, id: int, origin: str = "random", successes: int = 0, failures: int = 0):
        """Initialize a PoolImageItem.

        Args:
            id: Image ID
            origin: Origin of the image (default: "random")
            successes: Number of successful selections (default: 0)
            failures: Number of failed selections (default: 0)
        """
        self.id = id
        self.origin = origin
        self.successes = successes
        self.failures = failures

    def to_dict(self) -> Dict[str, Any]:
        """Convert the PoolImageItem to a dictionary.

        Returns:
            Dictionary representation of the PoolImageItem
        """
        return {
            "id": self.id,
            "origin": self.origin,
            "successes": self.successes,
            "failures": self.failures
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PoolImageItem':
        """Create a PoolImageItem from a dictionary.

        Args:
            data: Dictionary containing PoolImageItem data

        Returns:
            New PoolImageItem instance
        """
        return cls(
            id=data.get("id"),
            origin=data.get("origin", "random"),
            successes=data.get("successes", 0),
            failures=data.get("failures", 0)
        )

    @classmethod
    def from_parents(cls, id: int, parent_ids: List[int]) -> 'PoolImageItem':
        """Create a PoolImageItem based on parent images.

        Args:
            id: Image ID
            parent_ids: List of parent image IDs (1 or 2)

        Returns:
            New PoolImageItem instance

        Raises:
            ValueError: If the number of parents is not 1 or 2
        """
        if len(parent_ids) == 1:
            origin = f"child_of_{parent_ids[0]}"
        elif len(parent_ids) == 2:
            origin = f"child_of_{parent_ids[0]}_{parent_ids[1]}"
        else:
            raise ValueError("Invalid number of parents. Allowed: 1 or 2.")
        return cls(id=id, origin=origin)

    @classmethod
    def from_noise(cls, id: int, parent_id: int, attempt: int) -> 'PoolImageItem':
        """Create a PoolImageItem for a child from noise.

        Args:
            id: Image ID
            parent_id: Parent image ID
            attempt: Noise attempt number

        Returns:
            New PoolImageItem instance
        """
        origin = f"child_of_{parent_id}_noise_{attempt}"
        return cls(id=id, origin=origin)

    # Helper methods

    def is_child(self) -> bool:
        """Check if the image is a child of other images.

        Returns:
            True if the image is a child, False otherwise
        """
        return self.origin.startswith("child_of_")

    def get_parents(self) -> List[int]:
        """Get the list of parent image IDs.

        Examples:
            "child_of_123" → [123]
            "child_of_123_456" → [123, 456]
            "child_of_123_noise_2" → [123]

        Returns:
            List of parent image IDs
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
        """Check if the image is generated from noise.

        Returns:
            True if the image is from noise, False otherwise
        """
        return "noise_" in self.origin

    def get_noise_attempt(self) -> Optional[int]:
        """Get the noise attempt number.

        Examples:
            "child_of_123_noise_3" → 3

        Returns:
            Noise attempt number or None if not applicable
        """
        match = re.search(r"noise_(\d+)", self.origin)
        if match:
            return int(match.group(1))
        return None
