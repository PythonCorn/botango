from pathlib import Path
from typing import Union, List, Callable, Any, Dict, Optional
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field
import ast

TEMPLATE_PATH = Path(__file__).parent.parent / "templates"

ENVIRONMENT = Environment(
    loader=FileSystemLoader(TEMPLATE_PATH),
    trim_blocks=True,
    lstrip_blocks=True
)

# По безопасности: не кладём реальные токены в исходники.
ENV_DATA: Dict[str, str] = {
    "BOT_TOKEN": "This is your bot's token!"
}

POSTGRES_DATA: Dict[str, Any] = {
    "POSTGRES_USER": "postgres",
    "POSTGRES_PASSWORD": "postgres",
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": 5432,
    "POSTGRES_NAME": "bot_database"
}

AIOSQLITE: Dict[str, str] = {
    "DATABASE_NAME": "bot_database.db"
}

DATABASES = {
    "postgres": POSTGRES_DATA,
    "aiosqlite": AIOSQLITE
}

def _del_other_database(data: Dict[str, Any]):
    global ENV_DATA
    if data.get("DATABASE_NAME", None):
        for value in POSTGRES_DATA.keys():
            try:
                del ENV_DATA[value]
            except KeyError:
                continue
    elif data.get("POSTGRES_USER", None):
        try:
            del ENV_DATA["DATABASE_NAME"]
        except KeyError:
            pass

def write_env(env_file: str = "data/.env", data: Optional[Dict[str, Any]] = None) -> None:
    """
    Записывает пары KEY=VALUE. Если data is None — записывает текущее ENV_DATA.
    Значения экранируем (если в них есть пробелы или символы =), берём их как есть.
    """
    if data is None:
        data = ENV_DATA

    path = Path(env_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    _del_other_database(data)

    # Пишем в понятном виде, но не добавляем кавычки автоматически — можно добавить при необходимости.
    with path.open("w", encoding="utf-8") as f:
        for name, value in data.items():
            if value is None:
                continue
            # Приводим к строку; если значение содержит переводы строки — экранируем их.
            s = str(value).replace("\n", "\\n")
            f.write(f"{name.upper()}={s}\n")


def read_env(env_file: str = "data/.env") -> Dict[str, str]:
    """
    Читает файл .env в ENV_DATA. Правила:
    - Игнор пустых строк и строк, начинающихся с '#'
    - Разделение по первому '=' (split('=', 1))
    - Стришимся пробелы вокруг name и value
    - Обновляем глобальную ENV_DATA (вставки сохраняют порядок в Python 3.7+)
    """
    global ENV_DATA
    path = Path(env_file)
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            for raw in f:
                row = raw.rstrip("\n")
                if not row:
                    continue
                stripped = row.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" not in stripped:
                    continue
                name, value = stripped.split("=", 1)
                name = name.strip().upper()
                value = value.strip()
                # Если значение было записано с экранированными \n, возвращаем обратно
                value = value.replace("\\n", "\n")
                if name:
                    ENV_DATA[name] = value

    # Гарантируем, что файл существует и содержит хотя бы текущий ENV_DATA
    write_env(env_file, ENV_DATA)
    return ENV_DATA


def _check_type(value: str) -> str:
    """
    Попытка классифицировать строковое значение в типовую метку:
    int, float, list, dict, set, tuple, str

    Используем ast.literal_eval для безопасного разбора. Если не парсится —
    считаем str.
    """
    if value is None:
        return "str"
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        # Не литерал Python — возможно обычная строка
        # Специальная проверка: целые числа (включая отрицательные)
        sv = value.strip()
        if sv.lstrip("-").isdigit():
            return "int"
        # проверка на float (простая локальная проверка)
        try:
            float(sv)
            return "float"
        except Exception:
            return "str"
    else:
        if isinstance(parsed, bool):
            return "bool"
        if isinstance(parsed, int):
            return "int"
        if isinstance(parsed, float):
            return "float"
        if isinstance(parsed, list):
            return "list"
        if isinstance(parsed, tuple):
            return "tuple"
        if isinstance(parsed, set):
            return "set"
        if isinstance(parsed, dict):
            return "dict"
        return "str"


def data_for_settings() -> Dict[str, str]:
    """
    Возвращает mapping {ENV_NAME: inferred_type_name}.
    dict в Python 3.7+ сохраняет порядок вставки.
    """
    data = read_env()
    settings_data: Dict[str, str] = {}
    for k, v in data.items():
        settings_data[k] = _check_type(v)
    return settings_data


class Directory(BaseModel):
    target_file: Optional[Union[str, Path]] = None
    template_file: Optional[Union[str, Path]] = None
    use_path: bool = True
    # functions может быть callable или список callables; при вызове мы передаём kwargs
    functions: Optional[Union[List[Callable[..., Any]], Callable[..., Any]]] = None

    def _render_template(self, /, **kwargs) -> str:
        if self.template_file:
            template = ENVIRONMENT.get_template(str(self.template_file))
            return template.render(**kwargs)
        return ""

    def create(self, directory_name: str, /, **kwargs) -> None:
        # Создаём файл по шаблону
        if self.target_file:
            target_path = Path(directory_name) / self.target_file
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if self.use_path:
                kwargs["path"] = str(target_path)
            text = self._render_template(**kwargs)
            # Если шаблон вернул None — приводим к пустой строке
            target_path.write_text(data=(text or ""), encoding="utf-8")

        # Вызываем функции (если есть). Передаём kwargs — это гибче, чем без аргументов.
        if self.functions is not None:
            if isinstance(self.functions, list):
                for func in self.functions:
                    if callable(func):
                        try:
                            func(**kwargs)
                        except TypeError:
                            # функция не принимает kwargs — вызываем без аргументов
                            func()
            elif callable(self.functions):
                try:
                    self.functions(**kwargs)
                except TypeError:
                    self.functions()


class Schema(BaseModel):
    directory_name: str
    files: List[Directory] = Field(default_factory=list)

    def add_directory(self, directory: Directory) -> None:
        self.files.append(directory)

    def create(self, /, **kwargs) -> None:
        if self.files:
            for f in self.files:
                f.create(self.directory_name, **kwargs)


DEFAULT_INIT_TEMP = "default_init.j2"

DEFAULT_BOT_SCHEMA = Schema(
    directory_name="bot",
    files=[
        Directory(target_file="__init__.py", template_file=DEFAULT_INIT_TEMP),
        Directory(target_file="middlewares/__init__.py", template_file=DEFAULT_INIT_TEMP),
        Directory(target_file="handlers/__init__.py", template_file="example_init_handler.j2"),
        Directory(target_file="services/__init__.py", template_file=DEFAULT_INIT_TEMP),
        Directory(target_file="utils/__init__.py", template_file=DEFAULT_INIT_TEMP),
        Directory(functions=read_env)  # read_env будет вызвана при create()
    ]
)

DEFAULT_ROOT_SCHEMA = Schema(
    directory_name=".",
    files=[
        Directory(target_file="settings.py", template_file="settings.j2"),
        Directory(target_file=".gitignore", template_file="gitignore.j2", use_path=False)
    ]
)

DEFAULT_DATABASE_SCHEMA = Schema(
    directory_name="database",
    files=[
        Directory(target_file="__init__.py", template_file="database/init.j2"),
        Directory(target_file="connection.py", template_file="database/connection.j2"),
        Directory(target_file="models/__init__.py")
    ]
)
