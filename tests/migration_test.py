import os
import re
import pytest
from unittest.mock import patch
from migrations.migration import Migration

@pytest.fixture
def migration_instance():
    return Migration()

def test_build_migration_sequence(migration_instance):
    migration_sequence = migration_instance.build_migration_sequence()
    assert isinstance(migration_sequence, dict)

def test_get_migration_files(migration_instance):
    migration_files = migration_instance.get_migration_files()
    assert isinstance(migration_files, list)

def test_get_previous_migration_id(migration_instance):
    filename = "test_migration_0.py"
    prev_migration_id = migration_instance.get_previous_migration_id(filename)
    assert prev_migration_id is None

def test_generate_migration_script(migration_instance):
    migration_name = "new_test_migration"
    migration_filename = migration_instance.generate_migration_script(migration_name)
    assert isinstance(migration_filename, str)
    assert migration_filename.endswith('.py')
    migration_path = os.path.join(migration_instance.migrations_dir, migration_filename)
    assert os.path.exists(migration_path)

def test_run_migrations_invalid_direction(migration_instance):
    with pytest.raises(ValueError):
        migration_instance.run_migrations(direction="invalid_direction")

def test_get_next_migration(migration_instance):
    current_migration = "current_migration"
    next_migration = migration_instance.get_next_migration(current_migration)
    assert next_migration is None

def test_get_previous_migration(migration_instance):
    current_migration = "current_migration"
    previous_migration = migration_instance.get_previous_migration(current_migration)
    assert previous_migration is None

# TODO: test FHIR management logic
