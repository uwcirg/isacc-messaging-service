"""Migration Module

Captures common methods needed by the system for migration.

When downgrading, the downgrade() function of the currently
applied migration is being run. Downgrade goes 1 step back.
When upgrading, the upgrade() function of the to-be-applied
migration is being run. Upgrade applies all unapplied migrations.

If cycle is present in the migration order, the error is raised,
and manual resolution is necessary.

In order to create a new migration, all existing migrations must
first be applied.

You cannot create mpre than one new migration file at a time.

For branching/conflict resolution, manually review the migration files.
"""

import os
import uuid
import imp

from migrations.migration_resource import MigrationManager
from migrations.utils import LinkedList
from isacc_messaging.audit import audit_entry


class Migration:
    def __init__(self, migrations_dir=None):
        '''Initializes Migration class, which contains the logic
        for managing the migration order'''
        if migrations_dir is None:
            migrations_dir = os.path.join(os.path.dirname(__file__), "versions")
        self.migrations_dir = migrations_dir
        self.migration_sequence = LinkedList()
        self.migrations_locations = {}
        self.build_migration_sequence()

    def build_migration_sequence(self):
        '''Builds the migration list, based on the double LInked List.
        Checks for cycles'''
        migration_files: list = self.get_migrations()
        migration_nodes: dict = {}

        for migration in migration_files:
            migration_nodes[migration] = self.get_previous_migration_id(migration)

        if len(migration_files) > 0:
            try:
                self.migration_sequence.build_list_from_dictionary(migration_nodes)
            except Exception as e:
                audit_entry(f"{str(e)}", level='error')
                raise e
        else:
            error_message = "No valid migration files."
            audit_entry(error_message, level='info')


    def get_migrations(self) -> list:
        '''Retrieves all valid   migrations from the files in the migration directory.'''
        migration_files = os.listdir(self.migrations_dir)
        python_files = [file for file in migration_files if file.endswith(".py")]

        revisions = []
        for file_name in python_files:
            file_path = os.path.join(self.migrations_dir, file_name)
            module_name = os.path.splitext(file_name)[0]
            try:
                migration_module = imp.load_source(module_name, file_path)
                revision = str(getattr(migration_module, "revision", None))
                if revision:
                    revisions.append(revision)
                    self.migrations_locations[revision] = module_name
            except KeyError as e:
                print(f"Error loading migration script {module_name}: {e}")
        return revisions

    def get_previous_migration_id(self, migration_id: str) -> str:
        """Retrieve the down_revision from a migration script.
        Revision variables are used to track the migration order."""
        try:
            filename = self.migrations_locations[migration_id] + ".py"
        except KeyError as e:
            message = f"No corresponding file found for migration {migration_id}"
            audit_entry(
                message,
                level='error'
            )
            raise ValueError(message)

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
        """Generate a new migration script with basic functions."""
        self.build_migration_sequence()
        if migration_name in self.migrations_locations.values():
            error_message = f"That name already exist. Use a new name for the migration"

            audit_entry(
                error_message,
                level='error'
            )

            raise ValueError(error_message)

        current_migration_id = str(self.get_latest_applied_migration_from_fhir())
        latest_created_migration_id = str(self.get_latest_created_migration())

        if current_migration_id != latest_created_migration_id:
            error_message = f"There exists an unapplied migration."

            audit_entry(
                error_message,
                level='error'
            )

            raise RuntimeError(error_message)

        new_id = str(uuid.uuid4())
        migration_filename = f"{migration_name}.py"
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
            # If no migrations are left to run, silently exit
            return

        if direction == "upgrade":
            # Run all available migrations
            for migration in unapplied_migrations:
                self.run_migration(direction, migration, migration)
        if direction == "downgrade":
            # Run one migration down
            self.run_migration(direction, unapplied_migrations, applied_migrations)

    def run_migration(self, direction: str, next_migration: str, applied_migration: str):
        """Run migration(s) based on the specified direction ("upgrade" or "downgrade")."""
        # Update the migration to acquire most recent updates in the system
        migration_path = os.path.join(self.migrations_dir, self.migrations_locations[next_migration] + ".py")
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
        """Retrieve all migrations that have not yet been ran."""
        return self.migration_sequence.get_sublist(applied_migration)

    def get_previous_migration(self, current_migration) -> str:
        """Retrieve the previous migration."""
        return self.migration_sequence.previous(current_migration)

    def get_latest_created_migration(self) -> str:
        """Retrieve the latest created migration."""
        return self.migration_sequence.head

    ## FHIR MANAGEMENT LOGIC
    def get_latest_applied_migration_from_fhir(self) -> str:
        """Retrieve the latest applied migration migration id from FHIR."""
        # Logic to retrieve the latest applied migration number from FHIR
        manager = MigrationManager.get_resource(create_if_not_found=False)
        if manager is None:
            return None

        return manager.get_latest_migration()

    def update_latest_applied_migration_in_fhir(self, latest_applied_migration: str):
        """Update the latest applied migration id in FHIR."""
        # Logic to update the latest applied migration number in FHIR
        manager = MigrationManager.get_resource(create_if_not_found=True)
        manager.update_migration(latest_applied_migration)
