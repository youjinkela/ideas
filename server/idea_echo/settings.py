from dataclasses import dataclass, field
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("IDEA_ECHO_DATA", "data/server")))
    max_image_bytes: int = 20 * 1024 * 1024
    max_images: int = 20
    max_total_bytes: int = 200 * 1024 * 1024
    max_pixels: int = 100_000_000
    token_days: int = 30

