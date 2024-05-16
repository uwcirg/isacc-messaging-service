# Migration Module README

## Overview

The Migration module provides methods to manage database migrations in a structured manner, ensuring the correct application of migration steps and resolving conflicts when necessary. It handles both upgrading and downgrading of migrations, tracking the applied migrations and ensuring that no more than one migration script is created at a time.

## Features

- **Upgrade and Downgrade Migrations**: Apply or revert migrations one step at a time.
- **Migration Sequence Management**: Uses a double-linked list to manage migration order and detect cycles.
- **Audit Logging**: Logs important actions and errors using a logging system.
- **Migration Script Generation**: Creates new migration scripts with basic upgrade and downgrade functions.
- **FHIR Integration**: Retrieves and updates the latest applied migration from a FHIR server.

## Prerequisites

- Python >= 3.7
- FHIR server (if using FHIR integration)
- Required Python packages: `os`, `uuid`, `imp`, `json`, `logging`, `requests`, `logging`, 

## Installation

1. Clone the repository:

   ```bash
   git clone https://your-repository-url.git
   cd your-repository-directory

1. Install the requirements.txt:

   `pip install -r requirements.txt`

## Usage

To initialize the Migration service and use a specific directory for migration scripts, you need to provide the path to the directory when creating an instance of the Migration class. By default, the service looks for migration scripts in the versions directory located in the same directory as the script.  

<pre>

import os  
from your_module import Migration  

# Set the directory where migration scripts are stored  
migrations_dir = os.path.join(os.path.dirname(__file__), "versions")

# Initialize the Migration service
migration_service = Migration(migrations_dir=migrations_dir)

# Running an upgrade
migration_service.run_migrations(direction="upgrade")

# Running a downgrade
migration_service.run_migrations(direction="downgrade")

# Generating a new migration script
migration_service.generate_migration_script(migration_name="example_migration")
</pre>

## File Structure

your_project/  
├── migrations/  
│   ├── migration_resource.py  
│   ├── migration_utils.py  
│   └── versions/  
│       ├── 0001_initial_migration.py  
│       └── 0002_add_field_to_table.py  

## Example
Provided is a simple migration script that creates a test patient and then modifies it. The operation was limited to one patient to limit potential interference with existing stores. However, the commands used in the examples can be expanded to any number of examples and were limited for the sake of demonstration.  
The generated migration script will contain basic functions for upgrading and downgrading together with migration ids.  
More example can be found in versions subdirectory.  

<pre>
# Migration script generated for example_migration
revision = 'your-unique-revision-id'
down_revision = 'previous-revision-id'

def upgrade():
    # Add your upgrade migration code here
    print('upgraded')

def downgrade():
    # Add your downgrade migration code here
    print('downgraded')
</pre>

## Notes

- Ensure all existing migrations are applied before creating a new migration script.  
- The system raises an error if there is more than one unapplied migration when generating a new script.  
- Manually review migration files for branching or conflict resolution. 
- Upgrade upgrades up to and including latest created migration, downgrade downgrades one migrations at a time. 

## Liscence
This project is licensed under the MIT License - see the LICENSE file for details.
