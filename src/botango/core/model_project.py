from dataclasses import dataclass
import subprocess
from typing import List, Optional, Set
from importlib.metadata import distributions

import click
from pydantic import BaseModel, Field


@dataclass(frozen=True)
class PackageSpec:
    friendly_name: str        # человекочитаемое имя
    package_name: str         # имя для pip install
    version: str              # фиксированная версия


# Список пакетов как константы
AIO_SQLITE = PackageSpec("aiosqlite", "aiosqlite", "0.21.0")
AIO_POSTGRES = PackageSpec("asyncpg", "asyncpg", "0.30.0")
SYNC_POSTGRES = PackageSpec("psycopg2-binary", "psycopg2-binary", "2.9.11")
SQLALCHEMY = PackageSpec("sqlalchemy", "SQLAlchemy", "2.0.44")
CRYPTobot = PackageSpec("cryptobot", "aiocryptopay", "0.4.8")
XROCKET = PackageSpec("xrocket", "xrocket", "0.2.1")
YOOMONEY = PackageSpec("yoomoney", "aioyoomoney", "0.1.0")


def get_installed_package_names() -> Set[str]:
    """Возвращает набор имён установленных дистрибутивов (lowercase)."""
    names = set()
    for dist in distributions():
        # metadata может быть Mapping; Name иногда отсутствует — защитимся
        try:
            name = dist.metadata.get("Name") or dist.metadata.get("name")
        except Exception:
            name = None
        if name:
            names.add(name.lower())
    return names


class ModelProject(BaseModel):
    bot_token: str = Field(alias="BOT_TOKEN")
    bot_username: str = Field(alias="BOT_USERNAME")
    bot_url: str = Field(alias="BOT_URL")
    connection_type: str = Field(alias="CONNECTION_TYPE", default="long_polling")
    type_database: Optional[str] = Field(alias="TYPE_DATABASE", default=None)
    payments: List[str] = Field(alias="PAYMENTS", default_factory=list)
    dockerfile: bool = Field(alias="DOCKER_FILE", default=False)
    docker_compose: bool = Field(alias="DOCKER_COMPOSE", default=False)
    github: bool = Field(alias="GITHUB", default=False)

    def _add_packages(self) -> List[PackageSpec]:
        need_packages: List[PackageSpec] = []
        if self.type_database:
            need_packages.append(SQLALCHEMY)
            if self.type_database.lower() == AIO_SQLITE.friendly_name.lower():
                need_packages.append(AIO_SQLITE)
            else:
                # предполагаем, что все прочие варианты — postgres-подобные
                need_packages.append(AIO_POSTGRES)
                need_packages.append(SYNC_POSTGRES)

        payments_lower = {p.lower() for p in self.payments}
        if CRYPTobot.friendly_name.lower() in payments_lower:
            need_packages.append(CRYPTobot)
        if XROCKET.friendly_name.lower() in payments_lower:
            need_packages.append(XROCKET)
        if YOOMONEY.friendly_name.lower() in payments_lower:
            need_packages.append(YOOMONEY)

        return need_packages

    def _sort_need_packages(self) -> List[PackageSpec]:
        need_packages = self._add_packages()
        installed = get_installed_package_names()
        to_install = []
        for p in need_packages:
            if p.package_name.lower() not in installed:
                to_install.append(p)
        return to_install

    def install_packages(self, dry_run: bool = True, upgrade: bool = False) -> None:
        """
        Устанавливает отсутствующие пакеты.
        По умолчанию dry_run=True — просто печатает, что будет сделано.
        Установку выполняй с dry_run=False.
        """
        not_installed = self._sort_need_packages()
        if not not_installed:
            click.secho(message="Все необходимые пакеты уже установлены.", fg="green", bold=True)
            return

        for p in not_installed:
            spec = f"{p.package_name}=={p.version}"
            cmd = ["uv", "add", spec]
            if upgrade:
                cmd.append("--upgrade")
            if dry_run:
                click.secho(message=f"[dry-run] would run: {' '.join(cmd)}", fg="cyan", bold=True)
            else:
                click.secho(message=f"Installing {spec} ...", fg="green", bold=True)
                try:
                    subprocess.run(cmd, check=True)
                except subprocess.CalledProcessError as exc:
                    click.secho(message=f"Ошибка при установке {spec}: {exc}", fg="red", bold=True)
