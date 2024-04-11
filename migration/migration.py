import click
from datetime import datetime
import os
from flask import Blueprint, jsonify, request
from flask import current_app

from isacc_messaging.api.isacc_record_creator import IsaccRecordCreator
from isacc_messaging.audit import audit_entry
from twilio.request_validator import RequestValidator

base_blueprint = Blueprint('base', __name__, cli_group=None)


@base_blueprint.route('/')
def root():
    return {'ok': True}


@base_blueprint.cli.command("migrate")
@click.argument('migration_name')
def migrate(migration_name):
    # Generate a new migration script
    generate_migration_script(migration_name)

@base_blueprint.cli.command("upgrade")
def upgrade():
    # Run migrations to upgrade the schema
    run_migrations("upgrade")

@base_blueprint.cli.command("downgrade")
def downgrade():
    # Run migrations to downgrade the schema
    run_migrations("downgrade")

def run_migrations(action: str):
    migrations_dir = os.path.join(current_app.root_path, "migrations")
    migration_files = sorted(os.listdir(migrations_dir))

    # Find the most recent migration number
    most_recent_migration = 0
    for filename in migration_files:
        migration_number = int(filename.split("_")[0])
        if migration_number > most_recent_migration:
            most_recent_migration = migration_number

    # Find the latest applied migration number from the FHIR store
    latest_applied_migration = get_latest_applied_migration()

    # Determine which migrations need to be run based on the action
    if action == "upgrade":
        migrations_to_run = [filename for filename in migration_files if int(filename.split("_")[0]) > latest_applied_migration]
    elif action == "downgrade":
        migrations_to_run = [filename for filename in reversed(migration_files) if int(filename.split("_")[0]) <= latest_applied_migration]

    # Run each migration script
    for filename in migrations_to_run:
        migration_path = os.path.join(migrations_dir, filename)
        with open(migration_path, "r") as migration_file:
            migration_code = migration_file.read()
            exec(migration_code)

    # Update the latest applied migration number in the FHIR store
    update_latest_applied_migration(latest_applied_migration, most_recent_migration)

def get_latest_applied_migration():
    # TODO: add logic to retrieve an FHIR element with latest applied
    # migration with a HAPI call, such as Basic
    return 0

def update_latest_applied_migration(latest_applied_migration, most_recent_migration):
    # TODO: add logic to do a HAPI call according to the
    # given resource's id and then update its content
    # to most_recent_migration number
    return 0

def generate_migration_script(migration_name):
    # TODO: add logic to add a new migration script
    # given the most most_recent_migration
    # and a template header with metadata about the migration
    migrations_dir = os.path.join(current_app.root_path, "migrations")

    # Find the most recent migration number
    most_recent_migration = 0
    for filename in os.listdir(migrations_dir):
        migration_number = int(filename.split("_")[0])
        if migration_number > most_recent_migration:
            most_recent_migration = migration_number

    # Generate the next migration number
    next_migration_number = most_recent_migration + 1

    # Create the filename for the new migration script
    migration_filename = f"{next_migration_number:03d}_migration_{migration_name}.py"
    migration_path = os.path.join(migrations_dir, migration_filename)

    # Write the header and any initial content to the migration file
    with open(migration_path, "w") as migration_file:
        migration_file.write("# Migration script generated\n")
        migration_file.write(f"# Version: {next_migration_number}\n")
        migration_file.write("\n")
        migration_file.write("# Add your migration code here\n")

