import os
import pytest
import json
from unittest.mock import patch
from migrations.migration import Migration
from pytest import fixture


def load_json(datadir, filename):
    with open(os.path.join(datadir, filename), "r") as json_file:
        data = json.load(json_file)
    return data


class mock_response:
    """Wrap data in response like object"""

    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code == 200:
            return
        raise Exception("status code ain't 200")


@fixture
def migration_instance():
    return Migration()


@fixture
def mock_get_previous_migration_id():
    with patch.object(Migration, 'get_previous_migration_id') as mock:
        yield mock


def test_build_migration_sequence_empty():
    # Mock the output of get_migration_files
    with patch.object(Migration, 'get_migration_files', return_value=[]):
        # Instantiate Migration class
        migration_instance = Migration()

        # Call the method to test
        migration_instance.build_migration_sequence()

        # Assert that the result is an empty dictionary
        assert migration_instance.migration_sequence.get_head() == None


def test_build_migration_sequence_with_dependencies(mock_get_previous_migration_id):
    # Mock the output of get_migration_files
    mock_filenames = ['migration1.py', 'migration2.py', 'migration3.py']
    with patch.object(Migration, 'get_migration_files', return_value=mock_filenames):
        # Mock the output of get_previous_migration_id
        mock_get_previous_migration_id.side_effect = {
            'migration2': 'migration1',
            'migration3': 'migration2',
            'migration1': 'None'
        }.get

        # Instantiate Migration class
        migration_instance = Migration()

        # Call the method to test
        migration_instance.build_migration_sequence()

        # Assert the result
        assert migration_instance.migration_sequence.get_head().migration == 'migration3'
        assert migration_instance.migration_sequence.get_head().prev_node.migration == 'migration2'
        assert migration_instance.migration_sequence.get_head().prev_node.prev_node.migration == 'migration1'
        assert migration_instance.migration_sequence.get_head().prev_node.prev_node.prev_node is None


def test_get_previous_migration_id_nonexistent_file(migration_instance):
    migration = "nonexistent_migration"

    down_revision = migration_instance.get_previous_migration_id(migration)

    assert down_revision is None


def test_build_migration_sequence_with_circular_dependency(mock_get_previous_migration_id):
    # Mock the output of get_migration_files
    mock_filenames = ['migration1.py', 'migration2.py', 'migration3.py']
    with patch.object(Migration, 'get_migration_files', return_value=mock_filenames):
        # Mock the output of get_previous_migration_id to create circular dependency
        mock_get_previous_migration_id.side_effect = {
            'migration2': 'migration1',
            'migration1': 'migration3',
            'migration3': 'migration2'
        }.get

        with pytest.raises(ValueError) as exc_info:
            # Instantiate Migration class
            # Since build_migration_sequence is ran automatically
            # It should raises an error
            Migration()

        assert str(exc_info.value) == "Cycle detected in migration sequence"


def test_get_migration_files(migration_instance):
    migration_files = migration_instance.get_migration_files()
    assert isinstance(migration_files, list)


def test_get_previous_migration_id(migration_instance):
    filename = "test_7c929f8e-bd11-4283-9603-40613839d23a"
    prev_migration_id = migration_instance.get_previous_migration_id(filename)
    assert prev_migration_id is 'None'


def test_run_migrations_invalid_direction(migration_instance):
    with pytest.raises(ValueError):
        migration_instance.run_migrations(direction="invalid_direction")


def test_get_previous_migration(migration_instance):
    current_migration = "current_migration"
    previous_migration = migration_instance.get_previous_migration(current_migration)
    assert previous_migration is None


def test_get_previous_migration_id_exists(migration_instance):
    migration = "migration123"
    migration_content = "down_revision = 'migration122'\n"
    migration_path = os.path.join(migration_instance.migrations_dir, migration + ".py")
    with open(migration_path, "w") as migration_file:
        migration_file.write(migration_content)

    down_revision = migration_instance.get_previous_migration_id(migration)

    assert down_revision == "migration122"

    # Delete the migration file after assertion
    os.remove(migration_path)
