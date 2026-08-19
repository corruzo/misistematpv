from abc import ABC, abstractmethod


class CardReader(ABC):
    """Adapter contract for RFID readers, regardless of transport."""

    @abstractmethod
    def read_card_code(self) -> str:
        raise NotImplementedError


class SimulatedCardReader(CardReader):
    def __init__(self, card_code: str):
        self.card_code = card_code

    def read_card_code(self) -> str:
        return self.card_code.strip()