from pathlib import Path
from typing import Dict, Any, Optional

from botango.utils.template_creator import BotangoTemplate


class BaseFileSystem:
    base_directory: Path
    def __init__(
            self,
            env_data: Optional[Dict[str, Any]] = None
    ):
        self.env_data = env_data
        self.base_directory.parent.mkdir(parents=True, exist_ok=True)

    def create(self, *args, **kwargs): ...

class HandlerFileSystem(BaseFileSystem):

    base_directory = Path("bot/handlers")

    def create(self):
        files = [
            BotangoTemplate(
                filename=self.base_directory / "__init__.py",
                template_name="default_init.j2",
                data={
                    "path": self.base_directory / "__init__.py",
                    "imports": ["from .example_handler import example_router"]
                }
            ),
            BotangoTemplate(
                filename=self.base_directory / "example_handler.py",
                template_name="example_handler.j2",
                data={"path": self.base_directory / "example_handler.py"}
            )
        ]
        [f.render() for f in files]

