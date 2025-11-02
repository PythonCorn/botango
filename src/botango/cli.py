import click

from botango.utils.file_creator import FileCreator


@click.group()
def cli():
    pass

@cli.command()
def init():
    """Запуск построения схемы приложения"""
    creator = FileCreator()
    creator.create()
