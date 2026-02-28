from abc import ABC, abstractmethod
import httpx
from models import ScanResult


class BaseScanner(ABC):
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=4.0,
            headers={
                "User-Agent": "paraguay-idea-mcp/0.1.0 (research; contact@example.com)",
                "Accept": "application/json, text/html",
            },
            follow_redirects=True
        )

    @abstractmethod
    async def scan(self, keywords: list[str]) -> ScanResult:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()
