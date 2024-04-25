import os
from typing import List
from datetime import datetime
import uuid
import re

from isacc_messaging.audit import audit_entry
from isacc_messaging.models.fhir import (
    HAPI_request,
    first_in_bundle,
)
from migrations.migration_resource import MigrationManager

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
                raise ValueError(f"Cycle detected in migration sequence for {node}")
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
        """Retrieve the list of migration files."""
        migration_files = os.listdir(self.migrations_dir)
        return migration_files

    def get_previous_migration_id(self, filename: str) -> str:
        """Retrieve the id of the previously ran (downstream) migration script."""
        prev_migration_id = None
        with open(os.path.join(self.migrations_dir, filename), "r") as migration_file:
            for line in migration_file:
                match = re.match(r"# Previous version: (.+)", line)
                if match:
                    prev_migration_id = match.group(1) if match.group(1) != 'None' else None
                    break
        return prev_migration_id

    def generate_migration_script(self, migration_name: str):
        """Generate a new migration script."""
        current_id = str(self.get_latest_applied_migration_from_fhir())
        new_id = str(uuid.uuid4())  # Random string as the migration identifier
        migration_filename = f"{new_id}.py"
        migration_path = os.path.join(self.migrations_dir, migration_filename)
        with open(migration_path, "w") as migration_file:
            migration_file.write(f"# Migration script generated for {migration_name}\n")
            migration_file.write(f"# Current version: {new_id}\n")
            migration_file.write(f"# Previous version: {current_id}\n")
            migration_file.write("\n")
            migration_file.write("# Add your migration code here\n")
        return migration_filename

    def run_migrations(self, direction: str):
        """Run migrations based on the specified direction ("upgrade" or "downgrade")."""
        if direction not in ["upgrade", "downgrade"]:
            raise ValueError("Invalid migration direction. Use 'upgrade' or 'downgrade'.")

        current_migration = self.get_latest_applied_migration_from_fhir()
        applied_migration = None

        if direction == "upgrade":
            applied_migration = self.get_next_migration(current_migration)
        elif direction == "downgrade" and current_migration is not None:
            applied_migration = self.get_previous_migration(current_migration)

        if applied_migration is None:
            raise ValueError("No valid migration files to run.")

        migration_path = os.path.join(self.migrations_dir, applied_migration)
        with open(migration_path, "r") as migration_file:
            migration_code = migration_file.read()
            try:
                exec(migration_code)
                self.update_latest_applied_migration_in_fhir(applied_migration)

            except Exception as e:
                print(f"Error executing migration {applied_migration}: {e}")

    def get_next_migration(self, current_migration) -> str:
        """Retrieve the latest."""
        for current_node, previous_node in self.migration_sequence.items():
            if previous_node == current_migration:
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
        basic = HAPI_request('GET', 'Basic', params={
            "identifier": f"http://isacc.app/twilio-message-sid|{id}"
        })
        basic = first_in_bundle(basic)

        if basic is None:
            self.create_applied_migration_manager()

            return None

        manager = MigrationManager(basic)
        latest_applied_migration = manager.get_migration()

        return latest_applied_migration

    def update_latest_applied_migration_in_fhir(self, latest_applied_migration: str):
        """Update the latest applied migration id in FHIR."""
        # Logic to update the latest applied migration number in FHIR
        basic = HAPI_request('GET', 'Basic', params={
            "identifier": f"http://isacc.app/twilio-message-sid|{id}"
        })
        basic = first_in_bundle(basic)

        if basic is None:
            self.create_applied_migration_manager()

        manager = MigrationManager(basic)
        manager.update_migration(latest_applied_migration)


    def create_applied_migration_manager(self, initial_applied_migration: str = ""):
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
            'identifier': [{"system": "http://our.migration.system", "value": system_wide_id_or_latest_applied_migration}],
            'code': {"coding": [{ "system": "http://our.migration.system", "code": initial_applied_migration}]},
            'created': created_time,
        }

        HAPI_request('POST', 'Basic', resource=m)
