"""Migration Module

Captures common methods needed by the system for migration
"""

import os
from typing import List
from datetime import datetime
import uuid
import imp

from migrations.migration_resource import MigrationManager
from migrations.utils import Node, LinkedList
from isacc_messaging.audit import audit_entry
from isacc_messaging.models.fhir import (
    first_in_bundle,
)


class Migration:
    def __init__(self, migrations_dir=None):
        if migrations_dir is None:
            migrations_dir = os.path.join(os.path.dirname(__file__), "versions")
        self.migrations_dir = migrations_dir
        self.migration_sequence = LinkedList()
        self.build_migration_sequence()

    def build_migration_sequence(self):
        migration_files: list = self.get_migrations()
        migration_nodes: dict = {}

        for migration in migration_files:
            migration_nodes[migration] = self.get_previous_migration_id(migration)

        if len(migration_files) > 0:
            try:
                self.migration_sequence.build_list_from_dictionary(migration_nodes)
            except:
                error_message = "Cycle detected in migration sequence"
                audit_entry(error_message, level='error')
                raise ValueError(error_message)
        else:
            error_message = "No valid migration files."
            audit_entry(error_message, level='info')


    def get_migrations(self) -> list:
        migration_files = os.listdir(self.migrations_dir)
        python_files = [file for file in migration_files if file.endswith(".py")]

        revisions = []
        for file_name in python_files:
            file_path = os.path.join(self.migrations_dir, file_name)
            module_name = os.path.splitext(file_name)[0]
            try:
                migration_module = imp.load_source(module_name, file_path)
                revision = getattr(migration_module, "revision", None)
                if revision:
                    revisions.append(str(revision))
            except Exception as e:
                print(f"Error loading migration script {file_name}: {e}")
        return revisions

    def get_previous_migration_id(self, migration_id: str) -> str:
        """Retrieve the down_revision from a migration script."""
        filename = migration_id + ".py"
        down_revision = None
        migration_path = os.path.join(self.migrations_dir, filename)
        if os.path.exists(migration_path):
            try:
                migration_module = imp.load_source("migration_module", migration_path)
                down_revision = getattr(migration_module, "down_revision", None)
            except Exception as e:
                message = f"Error loading migration script {filename}: {e}"
                audit_entry(
                    message,
                    level='debug'
                )
                raise e
        else:
            message = f"Migration script {filename} does not exist."
            audit_entry(
                message,
                level='debug'
            )

        return down_revision

    def generate_migration_script(self, migration_name: str):
        """Generate a new migration script."""
        self.build_migration_sequence()
        current_migration_id = str(self.get_latest_applied_migration_from_fhir())
        latest_created_migration_id = str(self.get_latest_created_migration())

        if current_migration_id != latest_created_migration_id:
            error_message = f"There exists an unapplied migration."

            audit_entry(
                error_message,
                level='error'
            )

            raise ValueError(error_message)

        new_id = str(uuid.uuid4())
        migration_filename = f"{new_id}.py"
        migration_path = os.path.join(self.migrations_dir, migration_filename)

        with open(migration_path, "w") as migration_file:
            migration_file.write(f"# Migration script generated for {migration_name}\n")
            migration_file.write(f"revision = '{new_id}'\n")
            migration_file.write(f"down_revision = '{current_migration_id}'\n")
            migration_file.write("\n")
            migration_file.write("def upgrade():\n")
            migration_file.write("    # Add your upgrade migration code here\n")
            migration_file.write("    print('upgraded')\n")
            migration_file.write("\n")
            migration_file.write("def downgrade():\n")
            migration_file.write("    # Add your downgrade migration code here\n")
            migration_file.write("    print('downgraded')\n")
            migration_file.write("\n")

        return migration_filename

    def run_migrations(self, direction: str):
        """Run migrations based on the specified direction ("upgrade" or "downgrade")."""
        # Update the migration to acquire most recent updates in the system
        self.build_migration_sequence()
        if direction not in ["upgrade", "downgrade"]:
            raise ValueError("Invalid migration direction. Use 'upgrade' or 'downgrade'.")

        current_migration = self.get_latest_applied_migration_from_fhir()
        if current_migration and self.migration_sequence.find(current_migration) is None:
            message = "Applied migration does not exist in the migration system"
            audit_entry(
                message,
                level='info'
            )

            raise KeyError(message)

        applied_migrations = None
        unapplied_migrations = None
        if direction == "upgrade":
            unapplied_migrations = self.get_unapplied_migrations(current_migration)
        elif direction == "downgrade" and current_migration is not None:
            applied_migrations = self.get_previous_migration(current_migration)
            unapplied_migrations = current_migration

        if not unapplied_migrations or unapplied_migrations == 'None':
            raise ValueError("No valid migration files to run.")

        if direction == "upgrade":
            # Run all available migrations
            for migration in unapplied_migrations:
                self.run_migration(direction, migration, migration)
        if direction == "downgrade":
            # Run one migration down
            self.run_migration(direction, unapplied_migrations, applied_migrations)

    def run_migration(self, direction: str, next_migration: str, applied_migration: str):
        """Run single migration based on the specified direction ("upgrade" or "downgrade")."""
        # Update the migration to acquire most recent updates in the system
        migration_path = os.path.join(self.migrations_dir, next_migration + ".py")
        try:
            audit_entry(
                "running migration",
                level='info'
            )

            migration_module = imp.load_source('migration_module', migration_path)

            if direction == "upgrade":
                migration_module.upgrade()
            elif direction == "downgrade":
                migration_module.downgrade()

            self.update_latest_applied_migration_in_fhir(applied_migration)
        except Exception as e:
            message = f"Error executing migration {applied_migration}: {e}"
            audit_entry(
                message,
                level='debug'
            )

    def get_unapplied_migrations(self, applied_migration) -> list:
        """Retrieve all migrations after the applied migration."""
        return self.migration_sequence.get_sublist(applied_migration)

    def get_previous_migration(self, current_migration) -> str:
        """Retrieve the previous migration."""
        return self.migration_sequence.get_previous_node(current_migration)

    def get_latest_created_migration(self) -> str:
        """Retrieve the latest migration in the entire migration sequence."""
        return self.migration_sequence.get_head()

    ## FHIR MANAGEMENT LOGIC
    def get_latest_applied_migration_from_fhir(self) -> str:
        """Retrieve the latest applied migration migration id from FHIR."""
        # Logic to retrieve the latest applied migration number from FHIR
        basic = MigrationManager.get_resource()
        basic = first_in_bundle(basic)

        if basic is None:
            return None

        manager = MigrationManager(basic)
        latest_applied_migration = manager.get_latest_migration()

        return latest_applied_migration

    def update_latest_applied_migration_in_fhir(self, latest_applied_migration: str):
        """Update the latest applied migration id in FHIR."""
        # Logic to update the latest applied migration number in FHIR
        basic = MigrationManager.get_resource()
        basic = first_in_bundle(basic)

        if basic is None:
            basic = self.create_applied_migration_manager(latest_applied_migration)

        manager = MigrationManager(basic)
        manager.update_migration(latest_applied_migration)


    def create_applied_migration_manager(self, initial_applied_migration: str = None):
        """Create new FHIR resource to keep track of Migration History."""
        message = "No Migration History for this repository. Initializing new Migration Manager"

        audit_entry(
            message,
            level='info'
        )

        # Logic to create new Basic resource keeping track of the migration
        created_time = datetime.now().astimezone().isoformat()
        m = {
            'resourceType': 'Basic',
            'code': {"coding": [{ "system": "http://our.migration.system", "code": initial_applied_migration}]},
            'created': created_time,
        }

        return MigrationManager.create_resource(resource=m)
