import os
import pytest
from unittest.mock import patch, mock_open
from migrations.migration import Migration
from pytest import fixture

@fixture
def migration_instance():
    # Create a Migration instance
    migration = Migration()
    # Populate migrations_locations manually for testing purposes
    migration.migrations_locations = {
        'migration1_file': None,
        'migration2_file': 'migration2',
        'migration3_file': 'migration3'
    }

    return migration

@fixture
def mock_get_previous_migration_id():
    with patch.object(Migration, 'get_previous_migration_id') as mock:
        yield mock

def test_build_migration_sequence_empty(migration_instance):
    with patch.object(Migration, 'get_migrations', return_value=[]):
        migration_instance.build_migration_sequence()
        assert migration_instance.migration_sequence.head.data is None

def test_build_migration_sequence_with_dependencies(migration_instance, mock_get_previous_migration_id):
    mock_filenames = ['migration1', 'migration2', 'migration3']
    with patch.object(Migration, 'get_migrations', return_value=mock_filenames):
        mock_get_previous_migration_id.side_effect = {
            'migration2': 'migration1',
            'migration3': 'migration2',
            'migration1': 'None'
        }.get
        migration_instance.build_migration_sequence()
        assert migration_instance.migration_sequence.head.data == 'migration3'
        assert migration_instance.migration_sequence.head.prev_node.data == 'migration2'
        assert migration_instance.migration_sequence.head.prev_node.prev_node.data == 'migration1'
        assert migration_instance.migration_sequence.head.prev_node.prev_node.prev_node is None

def test_get_previous_migration_id_nonexistent_file(migration_instance):
    migration = "nonexistent_migration"
    down_revision = migration_instance.get_previous_migration_id(migration)
    assert down_revision is None

def test_build_migration_sequence_with_circular_dependency(migration_instance, mock_get_previous_migration_id):
    mock_filenames = ['migration1', 'migration2', 'migration3']
    with patch.object(Migration, 'get_migrations', return_value=mock_filenames):
        mock_get_previous_migration_id.side_effect = {
            'migration2': 'migration1',
            'migration1': 'migration3',
            'migration3': 'migration4',
            'migration4': 'migration2',
        }.get
        with pytest.raises(ValueError) as exc_info:
            Migration()
        assert str(exc_info.value) == "Cycle detected in migration sequence"

def test_get_migrations(migration_instance):
    migration_files = migration_instance.get_migrations()
    assert isinstance(migration_files, list)


def test_run_migrations_invalid_direction(migration_instance):
    with pytest.raises(ValueError):
        migration_instance.run_migrations(direction="invalid_direction")

def test_get_previous_migration(migration_instance):
    current_migration = "migration1_file"
    previous_migration = migration_instance.get_previous_migration(current_migration)
    assert previous_migration is None

def test_get_previous_migration_id_empty(migration_instance):
    migration = "migration2_file"
    mock_file_content = {f"{migration}.py": ""}
    
    with patch("builtins.open", mock_open()) as mock_file:
        # Configure the mock to return the appropriate content based on the filename
        mock_file.side_effect = lambda f: mock_file_content[f.name]

        # Call the method being tested
        prev_migration_id = migration_instance.get_previous_migration_id(migration)
    
    # Perform assertion
    assert prev_migration_id is None
