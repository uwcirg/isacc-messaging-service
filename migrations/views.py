from flask import Blueprint, jsonify, request
import click

from migrations.migration import Migration

migration_blueprint = Blueprint('migration', __name__, cli_group=None)
migration_manager = Migration()


@migration_blueprint.cli.command("migrate")
@click.argument('migration_name')
def migrate(migration_name):
    # Generate a new migration script
    migration_manager.generate_migration_script(migration_name)


@migration_blueprint.cli.command("insert")
@click.argument('migration_name')
def migrate(migration_name):
    # Generate a new migration script
    migration_manager.generate_migration_script(migration_name)


@migration_blueprint.cli.command("upgrade")
def upgrade():
    # Run migrations to upgrade the schema
    migration_manager.run_migrations("upgrade")


@migration_blueprint.cli.command("downgrade")
def downgrade():
    # Run migrations to downgrade the schema
    migration_manager.run_migrations("downgrade")


@migration_blueprint.cli.command("restart")
def upgrade():
    # Run migrations to upgrade the schema
    migration_manager.update_latest_applied_migration_in_fhir(None)
