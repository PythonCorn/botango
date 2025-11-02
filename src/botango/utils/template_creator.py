from pathlib import Path
from typing import Union, Dict, Any

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field, ConfigDict

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

class BotangoTemplate(BaseModel):
    filename: Union[str, Path]
    template_name: Union[str, Path]
    data: Dict[str, Any] = Field(default_factory=dict)
    environment: Environment = Environment(
        loader=FileSystemLoader(searchpath=TEMPLATE_DIR, encoding="utf-8"),
        trim_blocks=True,
        lstrip_blocks=True
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _read_template(self) -> str:
        temp = self.environment.get_template(str(self.template_name))
        return temp.render(**self.data)

    def render(self):
        file_path = self.filename if isinstance(self.filename, Path) else Path(self.filename)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding="utf-8") as file:
            file.write(self._read_template())



if __name__ == '__main__':
    print(TEMPLATE_DIR)