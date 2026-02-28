from abc import ABC, abstractmethod
import httpx
from models import ScanResult, ScannerAnalysis


class BaseScanner(ABC):
    # -- Subclasses MUST set these --
    name: str = ""
    tier: str = "deep"                     # "quick" = included in fast scan, "deep" = full scan only
    weight: int = 10                       # scorer weight points (higher = more influence)
    signal_direction: str = "positive"     # "positive" (competition) or "negative" (opportunity/demand)
    requires_env: list[str] = []           # env vars needed; scanner skipped if any are missing
    display_label: str = ""                # human-friendly label for the frontend

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

    @classmethod
    def analyze(cls, result: ScanResult, score: int) -> ScannerAnalysis:
        """Override to provide source-specific strengths/weaknesses/actions."""
        return ScannerAnalysis()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()
