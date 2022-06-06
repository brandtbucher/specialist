"""Tests for the Specialist command-line tool."""
import pathlib
import types

import pytest

import specialist


@pytest.mark.parametrize("code", specialist.CODE)
def test_get_code_for_path(code: types.CodeType) -> None:
    """Test that the correcct code is returned for a given path."""
    path = pathlib.Path(code.co_filename)
    if not path.is_file():
        pytest.skip()
    assert specialist.get_code_for_path(path) is code
