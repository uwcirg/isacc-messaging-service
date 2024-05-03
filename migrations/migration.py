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


class MigrationNode:
    def __init__(self, migration):
        self.migration: str = migration
        self.prev_node: MigrationNode = None
        self.next_node: MigrationNode = None

    def __repr__(self):
        return f"{self.migration}"

    def __eq__(self, other):
        if isinstance(other, MigrationNode):
            return self.migration == other.migration
        return False


class Migration:
    def __init__(self, migrations_dir=None):
        if migrations_dir is None:
            migrations_dir = os.path.join(os.path.dirname(__file__), "versions")
        self.migrations_dir = migrations_dir
        self.head: MigrationNode = None
        self.build_migration_sequence()

    def build_migration_sequence(self):
        migration_files: list = self.get_migration_files()
        migration_nodes: dict = {}
        print(migration_files)
        # First, create all migration nodes without linking them
        for filename in migration_files:
            migration = filename[:-3]
            node = MigrationNode(migration)
            migration_nodes[migration] = node

        # Second, link each migration node to its previous migration node
        for migration, node in migration_nodes.items():
            prev_node_id = self.get_previous_migration_id(migration)
            print("previous node id", prev_node_id)
            if prev_node_id:
                prev_node = migration_nodes.get(prev_node_id)
                print("previous node", prev_node_id)
                if prev_node:
                    print("previous node exists", prev_node_id)
                    # If there is a previous migration, link it to the current node
                    node.prev_node = prev_node
                    # Link the previous node to the current node as its next node
                    prev_node.next_node = node

        # Find the migration node that has no 'next_node' (i.e., the tail node)
        for node in migration_nodes.values():
            if node.next_node is None:
                self.head = node
                break

        # Set the head of the linked list to be the node with no 'next_node'
        self.check_for_cycles()

    def get_migration_files(self) -> list:
        migration_files = os.listdir(self.migrations_dir)
        python_files = [file for file in migration_files if file.endswith(".py")]
        return python_files

    def get_previous_migration_id(self, filename: str) -> str:
        """Retrieve the down_revision from a migration script."""
        filename = filename + ".py"
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

    def check_for_cycles(self):
        """Check the linked list for cycles using the Tortoise and Hare algorithm."""
        print("CHECKING MIGRATION FOR CYCLES")
        slow: MigrationNode = self.head
        fast: MigrationNode = self.head
        print(f"IS {slow} EQUAL {slow == fast}")
        print(f"{fast} and {fast.prev_node}")

        while slow and fast and fast.prev_node:
            print("new")
            slow = slow.prev_node
            fast = fast.prev_node.prev_node
            print(fast)
            print(slow)
            if slow == fast:
                    print("VICTORY")
                    error_message = "Cycle detected in migration sequence."
                    audit_entry(error_message, level='error')
                    raise ValueError(error_message)
        print("Skipped")
        return False

    def generate_migration_script(self, migration_name: str):
        """Generate a new migration script."""
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

    def get_next_migration(self, current_migration) -> str:
        """Retrieve the next migration."""
        current_node = self.head
        while current_node and current_node.prev_node:
            if current_node.prev_node.migration == current_migration:
                return current_node
            current_node = current_node.prev_node
        return None

    def get_unapplied_migrations(self, applied_migration) -> list:
        """Retrieve all migrations after the applied migration."""
        unapplied_migrations = []
        current_node = self.find_node(applied_migration)

        while current_node.next_node:
            current_node = current_node.next_node
            unapplied_migrations.append(current_node.migration)

        return unapplied_migrations

    def get_previous_migration(self, current_migration) -> str:
        """Retrieve the previous migration."""
        current_node = self.find_node(current_migration)
        if current_node and current_node.prev_node:
            return current_node.prev_node.migration
        return None

    def get_latest_created_migration(self) -> str:
        """Retrieve the latest migration in the entire migration sequence."""
        return self.head.migration

    def find_node(self, migration_name) -> MigrationNode:
        """Find a node in the migration sequence by migration name."""
        current_node = self.head
        while current_node:
            if current_node.migration == migration_name:
                return current_node
            current_node = current_node.prev_node
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
