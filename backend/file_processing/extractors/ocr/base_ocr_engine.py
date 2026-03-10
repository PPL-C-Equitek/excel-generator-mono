from abc import ABC, abstractmethod

class BaseOCREngine(ABC):
    @abstractmethod
    def extract_text(self, image) -> str:
        raise NotImplementedError
