import uuid
from pathlib import Path
from typing import Dict, Any

from botango.core.project_cli import ProjectCli
from botango.utils.file_systems import HandlerFileSystem
from botango.utils.template_creator import BotangoTemplate

DATABASE_ROWS = {
    "aiosqlite": {
        "DATABASE_NAME": "botango.db"
    },
    "postgres": {
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "postgres",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": 5432,
        "POSTGRES_NAME": "botango"
    }
}

PAYMENTS_ROWS = {
    "cryptobot": {
        "CRYPTOBOT_TOKEN": "your token here"
    },
    "xrocket": {
        "XROCKET_TOKEN": "your token here"
    },
    "yoomoney": {
        "YOOMONEY_CLIENT_ID": "your client id here",
        "RECEIVER_YOOMONEY": "your receiver here",
        "YOOMONEY_TOKEN": "your token here"
    }
}

SECRET = str(uuid.uuid4())

WEBHOOK_ROWS = {
    "BASE_URL": "Ваш url. Обязательно должен начинаться с https://",
    "WEBHOOK_SECRET": SECRET,
    "WEBHOOK_PATH": "/webhook"
}

NGROK_ROWS = {
    "WEBHOOK_SECRET": SECRET,
    "WEBHOOK_PATH": "/telegram/webhook",
    "NGROK_TOKEN": "Это обязательный параметр для первого запуска! Прочтите как правильно пользоваться Ngrok. Не использовать в production!"
}


class FileCreator:
    exclude_keys = ["DOCKER_FILE", "DOCKER_COMPOSE", "GITHUB"]
    def __init__(self):
        self.project_cli = ProjectCli()
        self.env_dict: Dict[str, Any] = {}

    def _build_project(self):
        self.project_cli.build_project()

    def _install_packages(self):
        self.project_cli.model.install_packages(dry_run=False)

    def _env_dict(self):
        self.env_dict = self.project_cli.data.copy()
        database = self.env_dict.pop("TYPE_DATABASE")
        if database:
            self.env_dict.update(DATABASE_ROWS.get(database))
        payments = self.env_dict.pop("PAYMENTS")
        if payments:
            for p in payments:
                self.env_dict.update(PAYMENTS_ROWS.get(p))
        for value in self.exclude_keys:
            self.env_dict.pop(value)
        conn_type = self.env_dict.get("CONNECTION_TYPE")
        if conn_type == "webhook":
            self.env_dict.update(WEBHOOK_ROWS)
        elif conn_type == "ngrok":
            self.env_dict.update(NGROK_ROWS)
        return self.env_dict

    @staticmethod
    def _create_env_file(env_data: Dict[str, Any]):
        env_path = Path("data/.env")
        env_path.parent.mkdir(parents=True, exist_ok=True)
        str_list = [f"{k}={v}" for k, v in env_data.items()]
        with env_path.open(mode="w", encoding="utf-8") as file:
            file.write("\n".join(str_list))

    @staticmethod
    def _get_type_var(var: Any) -> str:
        if isinstance(var, int):
            return "int"
        elif isinstance(var, float):
            return "float"
        elif isinstance(var, bool):
            return "bool"
        elif isinstance(var, list):
            return "list"
        elif isinstance(var, dict):
            return "dict"
        elif isinstance(var, set):
            return "set"
        elif isinstance(var, tuple):
            return "tuple"
        else:
            return "str"

    def _settings_adapter(self, env_data: Dict[str, Any]) -> Dict[str, Any]:
        settings_data = {}
        for k, v in env_data.items():
            settings_data[k] = self._get_type_var(v)
        return settings_data

    def create(self):
        self._build_project()
        self._install_packages()
        self._env_dict()
        self._create_env_file(self.env_dict)
        data = self._settings_adapter(self.env_dict)
        settings_template = BotangoTemplate(
            filename="settings.py",
            template_name="settings.j2",
            data={"settings_data": data}
        )
        main_template = BotangoTemplate(
            filename="main.py",
            template_name="main.j2",
            data={"settings_data": self.env_dict}
        )
        settings_template.render()
        main_template.render()
        HandlerFileSystem(self.env_dict).create()



