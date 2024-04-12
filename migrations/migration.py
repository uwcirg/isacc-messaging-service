import os
from typing import List
from flask import current_app

class Migration:
    def __init__(self, path=current_app.root_path):
        self.migrations_dir = os.path.join(path, "versions")
        self.latest_applied_migration = self.get_applied_migration_from_fhir()

    def get_migration_files(self) -> List[str]:
        """Retrieve the list of migration files."""
        migration_files = sorted(os.listdir(self.migrations_dir))
        return migration_files

    def get_latest_migration(self) -> int:
        """Find the latest migration number."""
        migration_files = self.get_migration_files()
        if migration_files:
            latest_migration = int(migration_files[-1].split("_")[0])
            return latest_migration
        else:
            return 0

    def get_applied_migration_from_fhir(self) -> int:
        """Retrieve the latest applied migration number from FHIR."""
        # TODO: Implement logic to retrieve the latest applied migration number from FHIR
        return 0

    def update_applied_migration_in_fhir(self, latest_applied_migration: int):
        """Update the latest applied migration number in FHIR."""
        # TODO: add logic to update the latest applied migration number in FHIR
        self.latest_applied_migration = latest_applied_migration

    def generate_migration_script(self, migration_name: str):
        """Generate a new migration script."""
        latest_migration = self.get_latest_migration()
        if self.latest_applied_migration != latest_migration:
            raise ValueError(f"Update the system to migration {latest_migration} first")

        next_migration_number = latest_migration + 1
        migration_filename = f"{next_migration_number:03d}_migration_{migration_name}.py"
        migration_path = os.path.join(self.migrations_dir, migration_filename)
        with open(migration_path, "w") as migration_file:
            migration_file.write("# Migration script generated\n")
            migration_file.write(f"# Revision: {next_migration_number}\n")
            migration_file.write(f"# Down revision: {latest_migration}\n")
            migration_file.write("\n")
            migration_file.write("# Add your migration code here\n")
        return migration_filename

    def run_migrations(self, direction: str):
        """Run migrations based on the specified direction ("upgrade" or "downgrade")."""
        migration_files = self.get_migration_files()
        if direction == "upgrade":
            migrations_to_run = [filename for filename in migration_files if int(filename.split("_")[0]) > self.latest_applied_migration]
        elif direction == "downgrade":
            migration_to_run = next((filename for filename in reversed(migration_files) if int(filename.split("_")[0]) < self.latest_applied_migration), None)
            migrations_to_run = [migration_to_run] if migration_to_run else []
        else:
            raise ValueError("Invalid migration direction. Use 'upgrade' or 'downgrade'.")

        if not migrations_to_run:
            print("No migrations to apply.")
            return

        for filename in migrations_to_run:
            migration_path = os.path.join(self.migrations_dir, filename)
            with open(migration_path, "r") as migration_file:
                migration_code = migration_file.read()
                try:
                    exec(migration_code)
                except Exception as e:
                    print(f"Error executing migration {filename}: {e}")
                    break
                else:
                    # Update the latest applied migration after each successful migration
                    migration_number = int(filename.split("_")[0])
                    if direction == "upgrade":
                        self.update_applied_migration_in_fhir(migration_number)  # Upgrade one step back
                    elif direction == "downgrade":
                        self.update_applied_migration_in_fhir(migration_number)  # Downgrade one step back
                    print(f"Migration {migration_number} {direction} applied.")
