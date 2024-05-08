from flask import Blueprint
import click

from migrations.migration import Migration

migration_blueprint = Blueprint('migration', __name__, cli_group=None)
migration_manager = Migration()

# Define CLI commands with help strings
@migration_blueprint.cli.command("migrate", default="new_migration", help="The name of the migration")
@click.argument('migration_name')
def migrate(migration_name):
    """
    Generate a new migration script.
    """
    migration_manager.generate_migration_script(migration_name)


@migration_blueprint.cli.command("upgrade")
def upgrade():
    """
    Run all unapplied migrations present in the versions folder to upgrade the schema.
    """
    migration_manager.run_migrations("upgrade")


@migration_blueprint.cli.command("downgrade")
def downgrade():
    """
    Run most recent migration to downgrade the schema.
    """
    migration_manager.run_migrations("downgrade")


@migration_blueprint.cli.command("reset")
def reset():
    """
    Reset the migration state by updating the latest applied migration in FHIR to None.
    """
    migration_manager.update_latest_applied_migration_in_fhir(None)
