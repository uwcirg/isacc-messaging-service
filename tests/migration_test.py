import os
import pytest
from unittest.mock import patch, mock_open
from migrations.migration import Migration
from pytest import fixture

@fixture
def migration_instance():
    return Migration()

@fixture
def mock_get_previous_migration_id():
    with patch.object(Migration, 'get_previous_migration_id') as mock:
        yield mock

def test_build_migration_sequence_empty(migration_instance):
    with patch.object(Migration, 'get_migrations', return_value=[]):
        migration_instance.build_migration_sequence()
        assert migration_instance.migration_sequence.get_head() is None

def test_build_migration_sequence_with_dependencies(migration_instance, mock_get_previous_migration_id):
    mock_filenames = ['migration1', 'migration2', 'migration3']
    with patch.object(Migration, 'get_migrations', return_value=mock_filenames):
        mock_get_previous_migration_id.side_effect = {
            'migration2': 'migration1',
            'migration3': 'migration2',
            'migration1': 'None'
        }.get
        migration_instance.build_migration_sequence()
        assert migration_instance.migration_sequence.get_head().data == 'migration3'
        assert migration_instance.migration_sequence.get_head().prev_node.data == 'migration2'
        assert migration_instance.migration_sequence.get_head().prev_node.prev_node.data == 'migration1'
        assert migration_instance.migration_sequence.get_head().prev_node.prev_node.prev_node is None

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
    current_migration = "current_migration"
    previous_migration = migration_instance.get_previous_migration(current_migration)
    assert previous_migration is None

def test_get_previous_migration_id_empty(migration_instance):
    migration = "test_8c929f8e-bd11-4283-9603-40613839d23a"
    mock_file_content = {f"{migration}.py": ""}
    
    with patch("builtins.open", mock_open()) as mock_file:
        # Configure the mock to return the appropriate content based on the filename
        mock_file.side_effect = lambda f: mock_file_content[f.name]

        # Call the method being tested
        prev_migration_id = migration_instance.get_previous_migration_id(migration)
    
    # Perform assertion
    assert prev_migration_id is None

@fixture
def mock_open_file(monkeypatch):
    mock_content = {}

    # Define a mock open function
    def mock_open(filename, mode='r'):
        if filename in mock_content:
            return mock_content[filename]
        else:
            raise FileNotFoundError(f"No such file or directory: '{filename}'")

    # Patch the built-in open function with the mock open function
    monkeypatch.setattr("builtins.open", mock_open)

    # Function to add content to the mock file
    def add_mock_file_content(filename, content):
        mock_content[filename] = content

    return add_mock_file_content

def test_get_previous_migration_id_exists(migration_instance, mock_open_file):
    migration = "test_8c929f8e-bd11-4283-9603-40613839d23a"
    migration_content = "down_revision = 'migration122'\n"

    # Add mock file content using the fixture
    mock_open_file(f"{migration}.py", migration_content)

    # Call the method being tested
    prev_migration_id = migration_instance.get_previous_migration_id(migration)

    # Perform assertion
    assert prev_migration_id == 'migration122'
