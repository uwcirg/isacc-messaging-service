"""Migration flask commands

Defines number of commands relevant for creating and managing migrations.
"""

from flask import Blueprint
import click
import requests

from migrations.migration import Migration

migration_blueprint = Blueprint('migration', __name__, cli_group=None)
migration_manager = Migration()

@migration_blueprint.cli.command("migrate", help="The name of the migration file to create")
@click.argument('migration_name')
def migrate(migration_name):
    """
    Generates a new migration script in python.
    """
    migration_manager.generate_migration_script(migration_name)


@migration_blueprint.cli.command("upgrade")
def upgrade():
    """
    Runs all unapplied migrations present in the versions folder to upgrade the schema.
    """
    migration_manager.run_migrations("upgrade")


@migration_blueprint.cli.command("downgrade")
def downgrade():
    """
    Runs most recent migration to downgrade the schema.
    """
    migration_manager.run_migrations("downgrade")


@migration_blueprint.cli.command("reset")
def reset():
    """
    Resets the migration state by updating the latest applied migration in FHIR to None.
    """
    migration_manager.update_latest_applied_migration_in_fhir(None)


@migration_blueprint.cli.command("create")
def create():
    """
    Resets the migration state by updating the latest applied migration in FHIR to None.
    """
    migration_manager.create()


@migration_blueprint.cli.command("get")
def get():
    """
    Resets the migration state by updating the latest applied migration in FHIR to None.
    """
    migration_manager.get()



@migration_blueprint.cli.command("create_hapi")
def create_hapi():
    """
    Resets the migration state by updating the latest applied migration in FHIR to None.
    """
    migration_manager.create_hapi()


@migration_blueprint.cli.command("get_hapi")
def get_hapi():
    """
    Resets the migration state by updating the latest applied migration in FHIR to None.
    """
    migration_manager.get_hapi()


@migration_blueprint.cli.command("delete")
@click.argument('basic_number')
def downgrade(basic_number):
    """
    Delete specific basic.
    """
    raise NotImplementedError("this shouldn't be deleting our only Basic object, but rather rolling the value back to the down_revision")
    HEADERS = {
    'Content-Type': 'application/fhir+json'
    }
    response = requests.delete(f'http://fhir-internal:8080/fhir/Basic/{basic_number}', headers=HEADERS)
    if response.status_code == 200 or response.status_code == 204:
        print('Basic deleted successfully.')
    else:
        print(f'Failed to delete basic: {response.status_code} {response.text}')
