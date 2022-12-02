"""Tests for the Specialist command-line tool."""
import contextlib
import pathlib
import runpy
import sys
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
def assert_browses(
    expected: typing.Sequence[str],
) -> typing.Generator[None, None, None]:
    """Patch webbrowser.open_new_tab, and assert that it browses the expected output."""
    expected_iter = iter(expected)

    def open_new_tab(url: str) -> None:
        with urllib.request.urlopen(url, timeout=1) as actual:
            assert next(expected_iter) == actual.read().decode("utf-8")

    with unittest.mock.patch("webbrowser.open_new_tab", open_new_tab):
        yield
    assert next(expected_iter, None) is None


@contextlib.contextmanager
def without_tracing() -> typing.Generator[None, None, None]:
    """Context manager that disables tracing and profiling."""
    trace = sys.gettrace()
    profile = sys.getprofile()
    try:
        sys.settrace(None)
        sys.setprofile(None)
        yield
    finally:
        sys.settrace(trace)
        sys.setprofile(profile)


def no_trace_main(args: list[str]) -> None:
    """Run specialist.main without tracing or profiling during runpy calls."""
    run_module = without_tracing()(runpy.run_module)  # pylint: disable = not-callable
    run_path = without_tracing()(runpy.run_path)  # pylint: disable = not-callable
    with (
        unittest.mock.patch("runpy.run_module", run_module),
        unittest.mock.patch("runpy.run_path", run_path),
    ):
        specialist.main(args)


@pytest.mark.parametrize("source, expected", TESTS)
def test_main(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist <source>"""
    with assert_browses([expected.read_text()]):
        no_trace_main([str(source)])


@pytest.mark.parametrize("source, expected", TESTS_BLUE)
def test_main_blue(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist --blue <file>"""
    with assert_browses([expected.read_text()]):
        no_trace_main(["--blue", str(source)])


@pytest.mark.parametrize("source, expected", TESTS)
def test_main_c(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist -c ..."""
    with assert_browses([expected.read_text()]):
        no_trace_main(["-c", source.read_text()])


def test_main_c_raises() -> None:
    """$ specialist -c '[i * i for i in range(100)]; 42 / 0'"""
    expected = (
        "<!doctype html><html><head><meta http-equiv='content-type' content='text/html;"
        "charset=utf-8'/></head><body style='background-color:white;color:black'><pre><"
        "span style='background-color:#d4fed4'>[</span><span style='background-color:#9"
        "1fe91'>i</span><span style='background-color:#b0ffb0'> * </span><span style='b"
        "ackground-color:#91fe91'>i</span><span style='background-color:#d4fed4'> for <"
        "/span><span style='background-color:#b0ffb0'>i</span><span style='background-c"
        "olor:#d4fed4'> in </span><span style='background-color:#dfffdf'>range</span><s"
        "pan style='background-color:#daffda'>(</span><span style='background-color:#dd"
        "ffdd'>100</span><span style='background-color:#daffda'>)</span><span style='ba"
        "ckground-color:#d4fed4'>]</span>; 42 / 0</pre></body></html>"
    )
    with assert_browses([expected]), pytest.raises(ZeroDivisionError):
        no_trace_main(["-c", "[i * i for i in range(100)]; 42 / 0"])


@pytest.mark.parametrize("source, expected", TESTS_DARK)
def test_main_dark(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist --dark <file>"""
    with assert_browses([expected.read_text()]):
        no_trace_main(["--dark", str(source)])


@pytest.mark.parametrize("source, expected", TESTS_DARK_BLUE)
def test_main_dark_blue(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist --dark --blue <file>"""
    with assert_browses([expected.read_text()]):
        no_trace_main(["--dark", "--blue", str(source)])


@pytest.mark.parametrize("source, expected", TESTS)
def test_main_m(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist -m <source>"""
    module = ".".join(source.with_suffix("").relative_to(pathlib.Path.cwd()).parts)
    with assert_browses([expected.read_text()]):
        no_trace_main(["-m", module])


def test_main_m_raises_a() -> None:
    """$ specialist -m __hello__"""
    no_trace_main(["-m", "__hello__"])


def test_main_m_raises_b() -> None:
    """$ specialist -m __phello__"""
    with pytest.raises(ImportError):
        no_trace_main(["-m", "__phello__"])


def test_main_m_raises_c() -> None:
    """$ specialist -m __hello__"""
    with pytest.raises(ImportError):
        no_trace_main(["-m", "__phello__.nonexistent"])


def test_main_no_location() -> None:
    """$ specialist -c 'def g(): yield from range(100)\nlist(g())'"""
    expected = (
        "<!doctype html><html><head><meta http-equiv='content-type' content='text/html;"
        "charset=utf-8'/></head><body style='background-color:white;color:black'><pre>d"
        "ef g(): <span style='background-color:#d4fed4'>yield from </span><span style='"
        "background-color:#ddffdd'>range</span><span style='background-color:#daffda'>("
        "</span><span style='background-color:#ddffdd'>100</span><span style='backgroun"
        "d-color:#daffda'>)</span>\nlist(g())</pre></body></html>"
    )
    with assert_browses([expected]):
        no_trace_main(["-c", "def g(): yield from range(100)\nlist(g())"])


def test_main_no_quickened_code_found() -> None:
    """$ specialist -c 'pass'"""
    no_trace_main(["-c", "pass"])


@pytest.mark.parametrize("source", [source for source, _ in TESTS])
def test_main_no_quickened_code_found_suggestion(source: pathlib.Path) -> None:
    """$ specialist -c ..."""
    no_trace_main(
        ["-c", f'import runpy; runpy.run_path("{source}", run_name="__main__")']
    )


def test_main_no_quickened_code_found_suggestions() -> None:
    """$ specialist -c ..."""
    lines = ["import runpy"]
    lines.extend(
        f'runpy.run_path("{source}", run_name="__main__")' for source, _ in TESTS
    )
    no_trace_main(["-c", "\n".join(lines)])


def test_main_no_quickened_code_found_suggestions_deep() -> None:
    """$ specialist -c ..."""
    input_package = TEST_DATA / "input-package"
    lines = ["import runpy"]
    lines.append(f'runpy.run_path("{input_package}", run_name="__main__")')
    lines.extend(
        f'runpy.run_path("{source}", run_name="__main__")' for source, _ in TESTS
    )
    no_trace_main(["-c", "\n".join(lines)])


@pytest.mark.parametrize("source, expected", TESTS)
def test_main_output(
    source: pathlib.Path, expected: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """$ specialist --output <tmp_path> <source>"""
    no_trace_main(["--output", str(tmp_path), str(source)])
    children = list(tmp_path.iterdir())
    assert len(children) == 1
    assert children[0].read_text() == expected.read_text()


@pytest.mark.parametrize("source", [source for source, _ in TESTS])
def test_main_targets_missing(source: pathlib.Path) -> None:
    """$ specialist --targets XXX <source>"""
    no_trace_main(["--targets", "XXX", str(source)])


@pytest.mark.parametrize("source, expected", TESTS)
def test_main_targets(source: pathlib.Path, expected: pathlib.Path) -> None:
    """$ specialist --targets <source> <source>"""
    targets = source.relative_to(pathlib.Path.cwd())
    with assert_browses([expected.read_text()]):
        no_trace_main(["--targets", str(targets), str(source)])


def test_main_targets_output_c(tmp_path: pathlib.Path) -> None:
    """$ specialist --targets 'test-data/input/*' -c 'pass'"""
    lines = ["import runpy"]
    lines.extend(
        f'runpy.run_path("{source}", run_name="__main__")' for source, _ in TESTS
    )
    no_trace_main(
        [
            "--targets",
            "test-data/input/*",
            "--output",
            str(tmp_path),
            "-c",
            "\n".join(lines),
        ]
    )
    for actual, expected in zip(
        sorted(tmp_path.iterdir()),
        sorted((TEST_DATA / "output").glob("output-*.html")),
        strict=True,
    ):
        assert actual.read_text() == expected.read_text()


def test_main_package() -> None:
    """$ specialist -m test-data.input-package"""
    expected = (
        "<!doctype html><html><head><meta http-equiv='content-type' content='text/html;"
        "charset=utf-8'/></head><body style='background-color:white;color:black'><pre><"
        "span style='background-color:#daffda'>[</span><span style='background-color:#9"
        "fff9f'>i</span><span style='background-color:#bbffbb'> * </span><span style='b"
        "ackground-color:#9fff9f'>i</span><span style='background-color:#daffda'> for <"
        "/span><span style='background-color:#bbffbb'>i</span><span style='background-c"
        "olor:#daffda'> in </span><span style='background-color:#e2ffe2'>range</span><s"
        "pan style='background-color:#dfffdf'>(</span><span style='background-color:#e1"
        "ffe1'>100</span><span style='background-color:#dfffdf'>)</span><span style='ba"
        "ckground-color:#daffda'>]</span>\n</pre></body></html>"
    )
    module = ".".join(
        (TEST_DATA / "input-package").relative_to(pathlib.Path.cwd()).parts
    )
    with assert_browses([expected]):
        no_trace_main(["-m", module])
