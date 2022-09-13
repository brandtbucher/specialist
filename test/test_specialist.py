"""Tests for the Specialist command-line tool."""
import pathlib
import tempfile

import pytest

import specialist

TESTS = list(
    zip(
        sorted((pathlib.Path(__file__).parent / "input").iterdir()),
        sorted((pathlib.Path(__file__).parent / "output").iterdir()),
        strict=True,
    )
)

TESTS_BLUE = list(
    zip(
        sorted((pathlib.Path(__file__).parent / "input").iterdir()),
        sorted((pathlib.Path(__file__).parent / "output-blue").iterdir()),
        strict=True,
    )
)

TESTS_DARK = list(
    zip(
        sorted((pathlib.Path(__file__).parent / "input").iterdir()),
        sorted((pathlib.Path(__file__).parent / "output-dark").iterdir()),
        strict=True,
    )
)

TESTS_DARK_BLUE = list(
    zip(
        sorted((pathlib.Path(__file__).parent / "input").iterdir()),
        sorted((pathlib.Path(__file__).parent / "output-dark-blue").iterdir()),
        strict=True,
    )
)


def run_specialist(args: list[str]) -> str:
    """Run Specialist with the provided args, and return the written HTML."""
    with tempfile.TemporaryDirectory() as tmp:
        with specialist.patch_sys_argv(["--output", tmp] + args):
            specialist.main()
        children = list(pathlib.Path(tmp).iterdir())
        assert len(children) == 1
        return children[0].read_text()


@pytest.mark.parametrize("source, expected", TESTS)
def test_main(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist <file>"""
    assert expected.read_text() == run_specialist([str(source)])


@pytest.mark.parametrize("source, expected", TESTS_BLUE)
def test_main_blue(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist --blue <file>"""
    assert expected.read_text() == run_specialist(["--blue", str(source)])


@pytest.mark.parametrize("source, expected", TESTS_DARK)
def test_main_dark(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist --dark <file>"""
    assert expected.read_text() == run_specialist(["--dark", str(source)])


@pytest.mark.parametrize("source, expected", TESTS_DARK_BLUE)
def test_main_dark_blue(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist --dark --blue <file>"""
    assert expected.read_text() == run_specialist(["--dark", "--blue", str(source)])


@pytest.mark.parametrize("source, expected", TESTS)
def test_main_c(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist -c ..."""
    assert expected.read_text() == run_specialist(["-c", source.read_text()])


@pytest.mark.parametrize("source, expected", TESTS_BLUE)
def test_main_blue_c(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist --blue -c ..."""
    assert expected.read_text() == run_specialist(["--blue", "-c", source.read_text()])


@pytest.mark.parametrize("source, expected", TESTS_DARK)
def test_main_dark_c(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist --dark -c ..."""
    assert expected.read_text() == run_specialist(["--dark", "-c", source.read_text()])


@pytest.mark.parametrize("source, expected", TESTS_DARK_BLUE)
def test_main_dark_blue_c(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist --dark --blue -c ..."""
    assert expected.read_text() == run_specialist(
        ["--dark", "--blue", "-c", source.read_text()]
    )
