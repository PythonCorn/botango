import click

from botango.core.project_cli import ProjectCli


@click.group()
def cli():
    pass

@cli.command()
def init():
    """Запуск построения схемы приложения"""
    model = ProjectCli().build_project()
    print(model.install_packages(dry_run=False))
