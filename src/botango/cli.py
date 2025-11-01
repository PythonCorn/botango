from pathlib import Path

import click

from botango.core.build_project import ProjectBuilder


@click.group()
def cli():
    pass

@cli.command()
def init():
    """Запуск построения схемы приложения"""
    ProjectBuilder().build_project()
#     DEFAULT_BOT_SCHEMA.create()
#     DEFAULT_ROOT_SCHEMA.create(env_data=data_for_settings())
#     click.echo("Начинается создание приложения!")
#
# @cli.command()
# @click.argument("db_key", default="aiosqlite", required=False)
# def database(db_key: str):
#     db_data = DATABASES.get(db_key)
#     if not db_data:
#         m = click.style(
#             text=f"Такой {db_key} базы данных нет. Используйте {[k for k in DATABASES.keys()]}",
#             bg="red",
#             reset=True
#         )
#         click.echo(message=m)
#         return
#     write_env(data=db_data)
#     DEFAULT_ROOT_SCHEMA.create(env_data=data_for_settings())
#     DEFAULT_DATABASE_SCHEMA.create(env_data=data_for_settings())
#
# @cli.command()
# @click.argument("resource")
# def add(resource):
#     """Добавление ресурса в проект"""
#     click.echo(f"Добавляем {resource}")