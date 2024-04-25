import os
import pytest
from unittest.mock import patch
from migrations.migration import Migration

@pytest.fixture
def migration_instance():
    return Migration()

@pytest.fixture
def mock_get_previous_migration_id():
    with patch.object(Migration, 'get_previous_migration_id') as mock:
        yield mock

def test_build_migration_sequence_empty(mock_get_previous_migration_id):
    # Mock the output of get_migration_files
    with patch.object(Migration, 'get_migration_files', return_value=[]):
        # Instantiate YourClass
        your_instance = Migration()

        # Call the method to test
        result = your_instance.build_migration_sequence()

        # Assert that the result is an empty dictionary
        assert result == {}

def test_build_migration_sequence_with_dependencies(mock_get_previous_migration_id):
    # Mock the output of get_migration_files
    mock_filenames = ['migration1.py', 'migration2.py', 'migration3.py']
    with patch.object(Migration, 'get_migration_files', return_value=mock_filenames):
        # Mock the output of get_previous_migration_id
        mock_get_previous_migration_id.side_effect = {
            'migration2': 'migration1',
            'migration3': 'migration2',
            'migration1': None
        }.get

        # Instantiate YourClass
        your_instance = Migration()

        # Call the method to test
        result = your_instance.build_migration_sequence()

        # Assert the result
        expected_result = {'migration1': None, 'migration2': 'migration1', 'migration3': 'migration2'}
        assert result == expected_result

def test_build_migration_sequence_with_circular_dependency(mock_get_previous_migration_id):
    # Mock the output of get_migration_files
    mock_filenames = ['migration1.py', 'migration2.py']
    with patch.object(Migration, 'get_migration_files', return_value=mock_filenames):
        # Mock the output of get_previous_migration_id to create circular dependency
        mock_get_previous_migration_id.side_effect = {
            'migration2': 'migration1',
            'migration1': 'migration2'
        }.get

        # Instantiate YourClass
        your_instance = Migration()

        # Call the method to test and assert the raised ValueError with the expected message
        with pytest.raises(ValueError) as exc_info:
            your_instance.build_migration_sequence()
        assert str(exc_info.value) == "Cycle detected in migration sequence for migration1.py"

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

# def test_generate_migration_script(migration_instance):
#     migration_name = "new_test_migration"
#     migration_filename = migration_instance.generate_migration_script(migration_name)
#     assert isinstance(migration_filename, str)
#     assert migration_filename.endswith('.py')
#     migration_path = os.path.join(migration_instance.migrations_dir, migration_filename)
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

# TODO: test FHIR management logic
