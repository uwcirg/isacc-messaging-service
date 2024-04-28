"""Migration Module

Captures common methods needed by the system for migration
"""

import os
from typing import List
from datetime import datetime
import uuid
import imp

from migrations.migration_resource import MigrationManager
from isacc_messaging.audit import audit_entry
from isacc_messaging.models.fhir import (
    first_in_bundle,
)

class Migration:
    def __init__(self, migrations_dir=None):
        if migrations_dir is None:
            migrations_dir = os.path.join(os.path.dirname(__file__), "versions")
        self.migrations_dir = migrations_dir
        self.migration_sequence = self.build_migration_sequence()

    def build_migration_sequence(self) -> dict:
        """Build the reference sequence dictionary for migration scripts."""
        migration_sequence = {}
        migration_files = self.get_migration_files()

        # Dictionary to keep track of nodes visited during traversal
        visited = set()
        # Set to keep track of nodes currently being traversed in the DFS
        traversing = set()

        def dfs(node):
            if node in traversing:
                error_message = f"Cycle detected in migration sequence for {node}"
                audit_entry(
                    error_message,
                    extra={"node": node},
                    level='error'
                )

                raise ValueError(error_message)
            if node in visited:
                return
            visited.add(node)
            traversing.add(node)
            if migration_sequence.get(node):
                dfs(migration_sequence[node])
            traversing.remove(node)

        for filename in migration_files:
            curr_migration = filename[:-3]
            prev_migration = self.get_previous_migration_id(filename)
            migration_sequence[curr_migration] = prev_migration

        # Perform DFS from each node
        for node in migration_sequence:
            if node not in visited:
                dfs(node)

        return migration_sequence

    def get_migration_files(self) -> List[str]:
        """Retrieve the list of valid migration files."""
        migration_files = os.listdir(self.migrations_dir)
        python_files = [file for file in migration_files if file.endswith(".py")]

        return python_files

    def get_previous_migration_id(self, filename: str) -> str:
        """Retrieve the down_revision from a migration script."""
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
        else:
            message = f"Migration script {filename} does not exist."
            audit_entry(
                message,
                level='debug'
            )

        return down_revision

    def generate_migration_script(self, migration_name: str):
        """Generate a new migration script."""
        current_id = self.get_latest_applied_migration_from_fhir()
        new_id = str(uuid.uuid4())  # Random string as the migration identifier
        migration_filename = f"{new_id}.py"
        migration_path = os.path.join(self.migrations_dir, migration_filename)

        with open(migration_path, "w") as migration_file:
            migration_file.write(f"# Migration script generated for {migration_name}\n")
            migration_file.write(f"revision = '{new_id}'\n")
            migration_file.write(f"down_revision = '{current_id}'\n")
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
        self.migration_sequence = self.build_migration_sequence()

        if direction not in ["upgrade", "downgrade"]:
            raise ValueError("Invalid migration direction. Use 'upgrade' or 'downgrade'.")

        current_migration = self.get_latest_applied_migration_from_fhir()
        applied_migration = 'None'
        next_migration = 'None'

        if direction == "upgrade":
            applied_migration = str(self.get_next_migration(current_migration))
            next_migration = applied_migration
        elif direction == "downgrade" and current_migration is not None:
            applied_migration = self.get_previous_migration(current_migration)
            next_migration = current_migration

        if next_migration == 'None':
            raise ValueError("No valid migration files to run.")

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

    def get_next_migration(self, current_migration) -> str:
        """Retrieve the latest."""
        for current_node, previous_node in self.migration_sequence.items():
            if str(previous_node) == str(current_migration):
                return current_node
        return None

    def get_previous_migration(self, current_migration) -> str:
        """Retrieve the latest."""
        if current_migration in self.migration_sequence:
            return self.migration_sequence.get(current_migration)
        else:
            return None

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
