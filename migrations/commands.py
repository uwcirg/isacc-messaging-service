"""Migration flask commands

Defines number of commands relevant for creating and managing migrations.
"""

from flask import Blueprint
import click

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
