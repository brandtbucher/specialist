"""Tests for the Specialist command-line tool."""
import contextlib
import pathlib
import typing
import unittest.mock
import urllib.request

import pytest

import specialist

TEST_DATA = pathlib.Path(__file__).parent / "test-data"

TESTS = list(
    zip(
        sorted((TEST_DATA / "input").glob("input-*.py")),
        sorted((TEST_DATA / "output").glob("output-*.html")),
        strict=True,
    )
)

TESTS_BLUE = list(
    zip(
        sorted((TEST_DATA / "input").glob("input-*.py")),
        sorted((TEST_DATA / "output-blue").glob("output-*.html")),
        strict=True,
    )
)

TESTS_DARK = list(
    zip(
        sorted((TEST_DATA / "input").glob("input-*.py")),
        sorted((TEST_DATA / "output-dark").glob("output-*.html")),
        strict=True,
    )
)

TESTS_DARK_BLUE = list(
    zip(
        sorted((TEST_DATA / "input").glob("input-*.py")),
        sorted((TEST_DATA / "output-dark-blue").glob("output-*.html")),
        strict=True,
    )
)


@contextlib.contextmanager
def assert_browses(expected: str) -> typing.Generator[None, None, None]:
    """Patch webbrowser.open_new_tab, and assert that it browses the expected output."""

    def open_new_tab(url: str) -> None:
        with urllib.request.urlopen(url, timeout=1) as actual:
            assert expected == actual.read().decode("utf-8")

    with unittest.mock.patch(
        "webbrowser.open_new_tab", side_effect=open_new_tab
    ) as patched:
        yield
    patched.assert_called_once()


@pytest.mark.parametrize("source, expected", TESTS)
def test_main(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist <source>"""
    args = [str(source)]
    with specialist.patch_sys_argv(args), assert_browses(expected.read_text()):
        specialist.main()


@pytest.mark.parametrize("source, expected", TESTS_BLUE)
def test_main_blue(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist --blue <file>"""
    args = ["--blue", str(source)]
    with specialist.patch_sys_argv(args), assert_browses(expected.read_text()):
        specialist.main()


@pytest.mark.parametrize("source, expected", TESTS)
def test_main_c(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist -c ..."""
    args = ["-c", source.read_text()]
    with specialist.patch_sys_argv(args), assert_browses(expected.read_text()):
        specialist.main()


def test_main_c_raises() -> None:
    """$ specialist -c '[i * i for i in range(100)]; 42 / 0'"""
    expected = "<!doctype html><html><head><meta http-equiv='content-type' content='text/html;charset=utf-8'/></head><body style='background-color:white;color:black'><pre><span style='background-color:#d4fed4'>[</span><span style='background-color:#dafe91'>i</span><span style='background-color:#ffffb0'> * </span><span style='background-color:#dafe91'>i</span><span style='background-color:#d4fed4'> for </span><span style='background-color:#b0ffb0'>i</span><span style='background-color:#d4fed4'> in </span><span style='background-color:#dfffdf'>range</span><span style='background-color:#daffda'>(</span><span style='background-color:#ddffdd'>100</span><span style='background-color:#daffda'>)</span><span style='background-color:#d4fed4'>]</span>; 42 / 0</pre></body></html>"  # pylint: disable = line-too-long
    args = ["-c", "[i * i for i in range(100)]; 42 / 0"]
    with specialist.patch_sys_argv(args), assert_browses(expected), pytest.raises(
        ZeroDivisionError
    ):
        specialist.main()


@pytest.mark.parametrize("source, expected", TESTS_DARK)
def test_main_dark(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist --dark <file>"""
    args = ["--dark", str(source)]
    with specialist.patch_sys_argv(args), assert_browses(expected.read_text()):
        specialist.main()


@pytest.mark.parametrize("source, expected", TESTS_DARK_BLUE)
def test_main_dark_blue(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist --dark --blue <file>"""
    args = ["--dark", "--blue", str(source)]
    with specialist.patch_sys_argv(args), assert_browses(expected.read_text()):
        specialist.main()


@pytest.mark.parametrize("source, expected", TESTS)
def test_main_m(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist -m <source>"""
    module = ".".join(source.with_suffix("").relative_to(pathlib.Path.cwd()).parts)
    args = ["-m", module]
    with specialist.patch_sys_argv(args), assert_browses(expected.read_text()):
        specialist.main()


def test_main_m_raises_a() -> None:
    """$ specialist -m __hello__"""
    args = ["-m", "__hello__"]
    with specialist.patch_sys_argv(args):
        specialist.main()


def test_main_m_raises_b() -> None:
    """$ specialist -m __phello__"""
    args = ["-m", "__phello__"]
    with specialist.patch_sys_argv(args), pytest.raises(ImportError):
        specialist.main()


def test_main_m_raises_c() -> None:
    """$ specialist -m __hello__"""
    args = ["-m", "__phello__.nonexistent"]
    with specialist.patch_sys_argv(args), pytest.raises(ImportError):
        specialist.main()


def test_main_no_location() -> None:
    """$ specialist -c 'def g(): yield from range(100)\nlist(g())'"""
    expected = "<!doctype html><html><head><meta http-equiv='content-type' content='text/html;charset=utf-8'/></head><body style='background-color:white;color:black'><pre>def g(): <span style='background-color:#d4fed4'>yield from </span><span style='background-color:#ffbb76'>range</span><span style='background-color:#feda91'>(</span><span style='background-color:#ffdd99'>100</span><span style='background-color:#feda91'>)</span>\nlist(g())</pre></body></html>"  # pylint: disable = line-too-long
    args = ["-c", "def g(): yield from range(100)\nlist(g())"]
    with specialist.patch_sys_argv(args), assert_browses(expected):
        specialist.main()


def test_main_o_quickened_code_found() -> None:
    """$ specialist -c 'pass'"""
    args = ["-c", "pass"]
    with specialist.patch_sys_argv(args):
        specialist.main()


@pytest.mark.parametrize("source, expected", TESTS)
def test_main_output(
    source: pathlib.Path, expected: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """$ specialist --output <tmp_path> <source>"""
    args = ["--output", str(tmp_path), str(source)]
    with specialist.patch_sys_argv(args):
        specialist.main()
    children = list(tmp_path.iterdir())
    assert len(children) == 1
    assert children[0].read_text() == expected.read_text()


@pytest.mark.parametrize("source, expected", TESTS)
def test_main_targets(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist --targets <source> <source>"""
    targets = source.relative_to(pathlib.Path.cwd())
    args = ["--targets", str(targets), str(source)]
    with specialist.patch_sys_argv(args), assert_browses(expected.read_text()):
        specialist.main()
