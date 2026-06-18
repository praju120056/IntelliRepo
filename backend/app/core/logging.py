import logging
import sys
from rich.logging import RichHandler
from rich.console import Console

console = Console()


def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging with Rich formatting."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=console,
                rich_tracebacks=True,
                show_path=True,
                markup=True,
            )
        ],
    )
    # Silence noisy third-party loggers
    for lib in ("httpx", "httpcore", "uvicorn.access", "chromadb", "git"):
        logging.getLogger(lib).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Always call after setup_logging()."""
    return logging.getLogger(name)
