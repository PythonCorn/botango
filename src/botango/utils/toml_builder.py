from pathlib import Path
from typing import Union, Mapping, Any, Dict

import toml


def _struct_path(filename: Union[str, Path]):
    if isinstance(filename, str):
        file = Path(filename)
        file.parent.mkdir(parents=True, exist_ok=True)
        return file
    return filename

def write_toml(filename: Union[str, Path], data: Mapping[..., Any]):
    file = _struct_path(filename)
    with file.open(mode="w", encoding="utf-8") as f:
        toml.dump(data, f)

def read_toml(filename: Union[str, Path]) -> Dict[Any, Any]:
    file = _struct_path(filename)
    if file.exists():
        with file.open(mode="r", encoding="utf-8") as f:
            return toml.load(f)
    return {}

def rewrite_toml(filename: Union[str, Path], data: Mapping[..., Any]):
    toml_data = read_toml(filename)
    toml_data.update(data)
    write_toml(filename, toml_data)