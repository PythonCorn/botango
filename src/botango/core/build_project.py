import asyncio
import sys
from typing import List, Optional

import click
from aiogram import Bot
from aiogram.utils.token import TokenValidationError

CONNECTIONS = ["long_polling", "webhook", "ngrok"]
DATABASES = ["aiosqlite", "postgres"]
PAYMENTS = ["cryptobot", "xrocket", "yoomoney"]




class ProjectBuilder:
    def __init__(self):
        self.data = {}

    @staticmethod
    def _step(step: int):
        click.echo(message=click.style(text=f"Шаг № {step}", fg="white", bold=True))

    @staticmethod
    def style(text: str,  fg: str = None,  bold=False,  italic=False):
        return click.style(text=text, fg=fg, bold=bold, italic=italic)

    def _get_token(self):
        self._step(1)
        token: str = click.prompt(
            text=self.style(text="Введите токен бота", fg="green", bold=True, italic=True),
            hide_input=True,
            type=str
        )

        try:
            bot = Bot(token=token.strip())

            async def _validate_token():
                async with bot:
                    me = (await bot.get_me()).username
                    return me

            username = asyncio.run(_validate_token())

            self.data["BOT_TOKEN"] = token
            self.data["BOT_USERNAME"] = username
            self.data["BOT_URL"] = f"https://t.me/{username}"

            click.echo(
                message=f"{self.style(text=f"✅ Токен бота валидный!!!\n", fg="green", bold=True)}"
                        f"{self.style(text="Username: ", fg="blue", bold=True)}"
                        f"{self.style(text=f"@{self.data.get("BOT_USERNAME")}", fg="green", bold=True)}"
            )
        except TokenValidationError as e:
            click.BadParameter(f"{e.args[0]}")
            click.echo(
                message=f"{self.style(text="Неверный токен бота!\n", fg="red", bold=True)}"
                        f"{self.style(text="Для получения перейдите по ссылке:", fg="blue", italic=True)} "
                        f"https://t.me/BotFather,\n"
                        f"{self.style(
                            text="Создайте бота и начните процесс создания заново!",
                            fg="white",
                            bold=True,
                            italic=True
                        )}"
            )
            sys.exit(1)

    def _get_choice(self, text: str, items: List[str], key: str, step: Optional[int] = None, many: bool = False):
        if step:
            self._step(step)
        click.echo(self.style(f"{text}:\n", fg="white", bold=True))

        # выводим список вариантов
        for i, conn in enumerate(items, start=1):
            click.echo(self.style(text=f"{i}. {conn}", fg="cyan", italic=True))

        click.echo("")
        if not many:
            conn_type = self._one_variant(items)
        else:
            conn_type = self._many_variants(items)

        click.secho(f"✅ Вы выбрали: {conn_type}\n", fg="green", bold=True)
        self.data[key.upper()] = conn_type

    def _one_variant(self, items):
        while True:
            try:
                choice: int = click.prompt(
                    text=self.style("Введите номер варианта. По умолчанию", fg="green", bold=True),
                    type=int,
                    default=1,
                    show_default=True
                )
                if 1 <= choice <= len(items):
                    conn_type = items[choice - 1]  # type: ignore
                    return conn_type
                else:
                    click.secho("❌ Некорректный выбор! Введите число из списка.", fg="red")
            except click.Abort:
                raise click.ClickException("Операция прервана пользователем.")
            except Exception:
                click.secho("❌ Введите число!", fg="red")

    def _many_variants(self, items):
        variants = []
        while True:
            try:
                choice: str = click.prompt(
                    text=self.style("Введите номер варианта (можно несколько через пробел). По умолчанию", fg="green", bold=True),
                    type=str,
                    default="1",
                    show_default=True
                )
                if choice == "None":
                    return variants

                if isinstance(choice, int):
                    if 1 <= choice <= len(items):
                        conn_type = items[choice - 1]  # type: ignore
                        return [items[conn_type]]

                parts = choice.split()

                if parts:
                    parts = list(map(int, parts))
                    for p in parts:
                        if 1 <= p <= len(items) and p not in variants:
                            variants.append(items[p - 1])
                    return variants
                else:
                    click.secho("❌ Некорректный выбор! Введите число из списка.", fg="red")
            except click.Abort:
                raise click.ClickException("Операция прервана пользователем.")
            except Exception:
                click.secho("❌ Введите число!", fg="red")

    def _bool_question(
            self,
            text: str,
            step: Optional[int] = None,
            default: bool = True
    ):
        if step:
            self._step(step)
        click.echo()
        choice = click.confirm(
            text=self.style(f"{text}", fg="white", bold=True),
            default=default
        )
        return choice

    def _get_type_connection(self):
        self._get_choice(
            text="Выберите тип соединения:",
            items=CONNECTIONS,
            key="connection_type",
            step=2
        )

    def _get_engine_database(self):
        if self._bool_question(
            text="Добавить базу данных?",
            step=3
        ):
            self._get_choice(
                text="Выберите тип базы данных",
                items=DATABASES,
                key="type_database"
            )

    def _get_payments(self):
        if self._bool_question(
                text=f"Добавить платежные системы? Доступные платежные системы: {PAYMENTS}",
                step=4,
                default=False
        ):
            self._get_choice(
                text="Выберите типы платежных систем",
                items=PAYMENTS,
                key="payments",
                many=True
            )

    def _get_docker_file(self):
        if self._bool_question(
                text="Добавить DockerFile?",
                step=5
        ):
            self.data["DOCKER_FILE"] = True

    def _get_docker_compose(self):
        if self._bool_question(
                text="Добавить docker-compose.yaml?",
                step=6
        ):
            self.data["DOCKER_COMPOSE"] = True

    def _get_github_actions(self):
        if self._bool_question(
                text="Добавить папку .github для CI/CD?",
                step=7
        ):
            self.data["GITHUB"] = True

    def build_project(self):
        self._get_token()
        self._get_type_connection()
        self._get_engine_database()
        self._get_payments()
        self._get_docker_file()
        self._get_docker_compose()
        self._get_github_actions()


