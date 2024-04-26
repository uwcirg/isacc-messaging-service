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


# @fixture
# def active_migration_manager_match(datadir):
#     return load_json(datadir, "active_migration_manager_match.json")


# @fixture
# def active_migration_manager_miss(datadir):
#     return load_json(datadir, "active_migration_manager_miss.json")


# @fixture
# def new_migration_manager_result(datadir):
#     return load_json(datadir, "new_migration_manager_result.json")


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
        result = migration_instance.build_migration_sequence()

        # Assert that the result is an empty dictionary
        assert result == {}


def test_build_migration_sequence_with_dependencies(mock_get_previous_migration_id):
    # Mock the output of get_migration_files
    mock_filenames = ['migration1.py', 'migration2.py', 'migration3.py']
    with patch.object(Migration, 'get_migration_files', return_value=mock_filenames):
        # Mock the output of get_previous_migration_id
        mock_get_previous_migration_id.side_effect = {
            'migration2.py': 'migration1',
            'migration3.py': 'migration2',
            'migration1.py': None
        }.get

        # Instantiate Migration class
        migration_instance = Migration()

        # Call the method to test
        result = migration_instance.build_migration_sequence()

        # Assert the result
        expected_result = {'migration1': None, 'migration2': 'migration1', 'migration3': 'migration2'}
        assert result == expected_result


def test_get_previous_migration_id_nonexistent_file(migration_instance):
    migration_name = "nonexistent_migration.py"

    down_revision = migration_instance.get_previous_migration_id(migration_name)

    assert down_revision is None


def test_build_migration_sequence_with_circular_dependency(mock_get_previous_migration_id):
    # Mock the output of get_migration_files
    mock_filenames = ['migration1.py', 'migration2.py']
    with patch.object(Migration, 'get_migration_files', return_value=mock_filenames):
        # Mock the output of get_previous_migration_id to create circular dependency
        mock_get_previous_migration_id.side_effect = {
            'migration2.py': 'migration1',
            'migration1.py': 'migration2'
        }.get

        with pytest.raises(ValueError) as exc_info:
            # Instantiate Migration class
            # Since build_migration_sequence is ran automatically
            # It should raises an error
            Migration()

        assert str(exc_info.value) == "Cycle detected in migration sequence for migration1"


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


# def test_generate_migration_script(migration_instance, mocker, new_migration_manager_result):    
#     # Mock HAPI search failing to find a matching patient
#     mocker.patch(
#         "migrations.migration_resource.requests.get",
#         return_value=mock_response(new_migration_manager_result),
#     )

#     migration_name = "new_test_migration"
#     migration_filename = migration_instance.generate_migration_script(migration_name)
#     migration_path = os.path.join(migration_instance.migrations_dir, migration_filename)

#     assert isinstance(migration_filename, str)
#     assert migration_filename.endswith('.py')
#     assert os.path.exists(migration_path)


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


def test_get_previous_migration_id_exists(migration_instance):
    migration_name = "migration123.py"
    migration_content = "down_revision = 'migration122'\n"
    migration_path = os.path.join(migration_instance.migrations_dir, migration_name)
    with open(migration_path, "w") as migration_file:
        migration_file.write(migration_content)

    down_revision = migration_instance.get_previous_migration_id(migration_name)

    assert down_revision == "migration122"

    # Delete the migration file after assertion
    os.remove(migration_path)


# TODO: test FHIR management logic
