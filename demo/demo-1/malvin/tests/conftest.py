"""Shared test fixtures."""

import shutil
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from knn_cli import dataset


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for tests."""
    temp_dir = Path(tempfile.mkdtemp())
    with mock.patch.object(dataset, "DATA_DIR", temp_dir):
        yield temp_dir
    shutil.rmtree(temp_dir)
