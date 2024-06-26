"""Visualize CPython's specializing, adaptive interpreter."""

import pathlib
import sys
import types

if sys.version_info < (3, 11) or sys.implementation.name != "cpython":
    raise RuntimeError("Specialist only supports CPython 3.11+!")  # pragma: no cover

_code = {}


def _audit_imports(event: str, args: "typing.Sequence[object]") -> None:
    """Intercept all exec() calls and grab a reference to the code they execute.

    This is the only way I know of to actually get ahold of module-level code
    objects without modifying the code being run.
    """
    match event, args:
        case "exec", [types.CodeType(co_name="<module>") as code]:
            _code[pathlib.Path(code.co_filename).resolve()] = code


_audit_imports.__cantrace__ = True  # type: ignore [attr-defined]
sys.addaudithook(_audit_imports)

# pylint: disable = wrong-import-order, wrong-import-position
import _opcode  # type: ignore [import-not-found]
import argparse
import collections
import colorsys
import contextlib
import ctypes
import dataclasses
import dis
import gc
import html
import http.server
import importlib.util
import itertools
import opcode
import os
import re
import runpy
import shlex
import sysconfig
import tempfile
import threading
import typing
import webbrowser

_RE_WHITESPACE = re.compile(r"(\s*\n\s*)")
_FIRST_POSTION = (1, 0)
_LAST_POSITION = (sys.maxsize, 0)
if sys.version_info < (3, 13):  # pragma: no cover
    _CACHE_FORMAT = frozenset(opcode._cache_format)  # type: ignore [attr-defined] # pylint: disable = protected-access
else:  # pragma: no cover
    _CACHE_FORMAT = frozenset(opcode._cache_format) - {  # type: ignore [attr-defined] # pylint: disable = protected-access
        "JUMP_BACKWARD",
        "POP_JUMP_IF_FALSE",
        "POP_JUMP_IF_NONE",
        "POP_JUMP_IF_NOT_NONE",
        "POP_JUMP_IF_TRUE",
    }
if sys.version_info < (3, 13):  # pragma: no cover
    _SPECIALIZED_INSTRUCTIONS = frozenset(opcode._specialized_instructions)  # type: ignore [attr-defined] # pylint: disable = no-member, protected-access
else:  # pragma: no cover
    _SPECIALIZED_INSTRUCTIONS = frozenset(opcode._specialized_opmap) - {"RESUME_CHECK"}  # type: ignore [attr-defined] # pylint: disable = no-member, protected-access
if sys.version_info < (3, 12):  # pragma: no cover
    _SUPERDUPERINSTRUCTIONS = frozenset({"PRECALL_NO_KW_LIST_APPEND"})
    _SUPERINSTRUCTIONS = _SUPERDUPERINSTRUCTIONS | {
        "BINARY_OP_INPLACE_ADD_UNICODE",
        "COMPARE_OP_FLOAT_JUMP",
        "COMPARE_OP_INT_JUMP",
        "COMPARE_OP_STR_JUMP",
        "LOAD_CONST__LOAD_FAST",
        "LOAD_FAST__LOAD_CONST",
        "LOAD_FAST__LOAD_FAST",
        "PRECALL_BUILTIN_CLASS",
        "PRECALL_BUILTIN_FAST_WITH_KEYWORDS",
        "PRECALL_METHOD_DESCRIPTOR_FAST_WITH_KEYWORDS",
        "PRECALL_NO_KW_BUILTIN_FAST",
        "PRECALL_NO_KW_BUILTIN_O",
        "PRECALL_NO_KW_ISINSTANCE",
        "PRECALL_NO_KW_LEN",
        "PRECALL_NO_KW_METHOD_DESCRIPTOR_FAST",
        "PRECALL_NO_KW_METHOD_DESCRIPTOR_NOARGS",
        "PRECALL_NO_KW_METHOD_DESCRIPTOR_O",
        "PRECALL_NO_KW_STR_1",
        "PRECALL_NO_KW_TUPLE_1",
        "PRECALL_NO_KW_TYPE_1",
        "STORE_FAST__LOAD_FAST",
        "STORE_FAST__STORE_FAST",
    }
elif sys.version_info < (3, 13):  # pragma: no cover
    _SUPERDUPERINSTRUCTIONS: frozenset[str] = frozenset()
    _SUPERINSTRUCTIONS = _SUPERDUPERINSTRUCTIONS | {
        "BINARY_OP_INPLACE_ADD_UNICODE",
        "CALL_NO_KW_LIST_APPEND",
        "LOAD_CONST__LOAD_FAST",
        "LOAD_FAST__LOAD_CONST",
        "LOAD_FAST__LOAD_FAST",
        "STORE_FAST__LOAD_FAST",
        "STORE_FAST__STORE_FAST",
    }
else:  # pragma: no cover
    _SUPERDUPERINSTRUCTIONS: frozenset[str] = frozenset()
    _SUPERINSTRUCTIONS = _SUPERDUPERINSTRUCTIONS | {
        "BINARY_OP_INPLACE_ADD_UNICODE",
        "CALL_LIST_APPEND",
    }
_PURELIB = pathlib.Path(sysconfig.get_path("purelib")).resolve()
assert _PURELIB.is_dir(), _PURELIB
_STDLIB = pathlib.Path(sysconfig.get_path("stdlib")).resolve()
assert _STDLIB.is_dir(), _STDLIB
_TMP = pathlib.Path(tempfile.gettempdir()).resolve()
assert _TMP.is_dir(), _TMP


class _HTMLWriter:
    """Write HTML for a source code view."""

    def __init__(self, *, blue: bool, dark: bool) -> None:
        self._blue = blue
        self._dark = dark
        background_color, color = ("black", "white") if dark else ("white", "black")
        self._parts = [
            "<!doctype html>",
            "<html>",
            "<head>",
            "<meta http-equiv='content-type' content='text/html;charset=utf-8'/>",
            "</head>",
            f"<body style='background-color:{background_color};color:{color}'>",
            "<pre>",
        ]

    def add(self, source: str, stats: "_Stats") -> None:
        """Add a chunk of code to the output."""
        color = self._color(stats)
        attribute = "color" if self._dark else "background-color"
        source = html.escape(source)
        if color == "#ffffff":
            self._parts.append(source)
        else:
            for part in filter(None, _RE_WHITESPACE.split(source)):
                if _RE_WHITESPACE.fullmatch(part) is None:
                    part = f"<span style='{attribute}:{color}'>{part}</span>"
                self._parts.append(part)

    def emit(self) -> str:
        """Emit the HTML."""
        return "".join([*self._parts, "</pre></body></html>"])

    def _color(self, stats: "_Stats") -> str:
        """Compute an RGB color code for this chunk."""
        quickened = stats.specialized + stats.adaptive
        if not quickened:
            return "#ffffff"
        # Red is 0/3, green is 1/3. This gives a hue along the red-green gradient
        # that reflects the hit rate:
        hue = 1 / 3 * stats.specialized / quickened
        if self._blue:
            # This turns our red-green (0/3 to 1/3) gradient into a red-blue (0/3 to
            # -1/3) gradient:
            hue = -hue
        lightness = max(1 / 2, stats.unquickened / (quickened + stats.unquickened))
        # Always fully saturate the color:
        saturation = 1
        rgb = colorsys.hls_to_rgb(hue, lightness, saturation)
        return f"#{int(255 * rgb[0]):02x}{int(255 * rgb[1]):02x}{int(255 * rgb[2]):02x}"


def _stderr(*args: object) -> None:
    """Print to stderr."""
    print("specialist:", *args, file=sys.stderr, flush=True)


def _is_superinstruction(instruction: dis.Instruction | None) -> bool:
    """Check if an instruction is a superinstruction."""
    return instruction is not None and instruction.opname in _SUPERINSTRUCTIONS


def _is_superduperinstruction(instruction: dis.Instruction | None) -> bool:
    """Check if an instruction is a superduperinstruction."""
    return instruction is not None and instruction.opname in _SUPERDUPERINSTRUCTIONS


def _adaptive_counter_value(
    instruction: dis.Instruction, raw_bytecode: bytes
) -> tuple[int, int]:
    """Get the value of the adaptive counter for this instruction."""
    next_code_unit = raw_bytecode[instruction.offset + 2 : instruction.offset + 4]
    counter = int.from_bytes(next_code_unit, sys.byteorder)
    return counter >> 4, counter & 0b1111


def _score_instruction(
    instruction: dis.Instruction,
    previous: dis.Instruction | None,
    previous_previous: dis.Instruction | None,
    raw_bytecode: bytes,
) -> "_Stats":
    """Return stats for the given instruction."""
    if _is_superinstruction(previous) or _is_superduperinstruction(previous_previous):
        return _Stats(specialized=True)
    if sys.version_info < (3, 12):  # pragma: no cover
        if instruction.opname in _SPECIALIZED_INSTRUCTIONS:
            if not instruction.opname.endswith("_ADAPTIVE"):
                return _Stats(specialized=True)
            if any(_adaptive_counter_value(instruction, raw_bytecode)):
                return _Stats(adaptive=True)
    else:  # pragma: no cover
        if instruction.opname in _SPECIALIZED_INSTRUCTIONS:
            return _Stats(specialized=True)
        if instruction.opname in _CACHE_FORMAT and _adaptive_counter_value(
            instruction, raw_bytecode
        ) > (1, 1):
            return _Stats(adaptive=True)
    return _Stats(unquickened=True)


@contextlib.contextmanager
def _catch_exceptions() -> typing.Generator[list[BaseException], None, None]:
    """Suppress exceptions, and gather them into a list."""
    caught: list[BaseException] = []
    try:
        yield caught
    except BaseException as exception:  # pylint: disable = broad-except
        caught.append(exception)


@contextlib.contextmanager
def _patch_sys_argv(argv: typing.Iterable[str]) -> typing.Generator[None, None, None]:
    """Patch sys.argv to simulate a command line."""
    sys_argv = sys.argv[1:]
    sys.argv[1:] = argv
    try:
        yield
    finally:
        sys.argv[1:] = sys_argv


@contextlib.contextmanager
def _insert_sys_path(path: pathlib.Path) -> typing.Generator[None, None, None]:
    """Patch sys.path to simulate a normal python execution."""
    sys_path = sys.path[:]
    sys.path.insert(0, str(path))
    try:
        yield
    finally:
        sys.path[:] = sys_path


def _main_file_for_module(module: str) -> pathlib.Path | None:
    """Get the main file for a module."""
    spec = importlib.util.find_spec(module)
    if spec is None:
        return None
    if spec.submodule_search_locations is not None:
        spec = importlib.util.find_spec(f"{module}.__main__")
        if spec is None:
            return None
    if not spec.has_location:
        return None
    assert spec.origin is not None
    return pathlib.Path(spec.origin).resolve()


@dataclasses.dataclass(frozen=True, slots=True)
class _Stats:
    """Statistics about a source chunk."""

    specialized: int = 0
    adaptive: int = 0
    unquickened: int = 0

    def __add__(self, other: "_Stats") -> "_Stats":
        if not isinstance(other, _Stats):
            return NotImplemented  # pragma: no cover
        return _Stats(
            specialized=self.specialized + other.specialized,
            adaptive=self.adaptive + other.adaptive,
            unquickened=self.unquickened + other.unquickened,
        )

    def __sub__(self, other: "_Stats") -> "_Stats":
        if not isinstance(other, _Stats):
            return NotImplemented  # pragma: no cover
        return _Stats(
            specialized=self.specialized - other.specialized,
            adaptive=self.adaptive - other.adaptive,
            unquickened=self.unquickened - other.unquickened,
        )


@dataclasses.dataclass(frozen=True, slots=True)
class _SourceChunk:
    """A chunk of source code."""

    start: tuple[int, int]
    stop: tuple[int, int]
    stats: _Stats


def _walk_code(code: types.CodeType) -> typing.Generator[types.CodeType, None, None]:
    """Walk a code object, yielding all of its sub-code objects."""
    yield code
    for constant in code.co_consts:
        if isinstance(constant, types.CodeType):
            yield from _walk_code(constant)


def _parse(code: types.CodeType) -> typing.Generator[_SourceChunk, None, None]:
    """Parse a code object's source code into SourceChunks."""
    events: collections.defaultdict[tuple[int, int], _Stats] = collections.defaultdict(
        _Stats
    )
    events[_FIRST_POSTION] = _Stats()
    events[_LAST_POSITION] = _Stats()
    previous_two: tuple[None, None] | tuple[dis.Instruction, dis.Instruction | None] = (
        None,
        None,
    )
    jit_code = _find_jit_code()
    have_jit_code = any(jit_code.values())
    for child in _walk_code(code):
        for instruction in dis.get_instructions(child, adaptive=True):
            if instruction.is_jump_target:
                previous_two = None, None
            if instruction.positions is None or None in instruction.positions:
                previous_two = instruction, previous_two[0]
                continue
            lineno, end_lineno, col_offset, end_col_offset = instruction.positions
            assert lineno is not None
            assert end_lineno is not None
            assert col_offset is not None
            assert end_col_offset is not None
            stats = _score_instruction(
                instruction, previous_two[0], previous_two[1], child._co_code_adaptive  # type: ignore [attr-defined]  # pylint: disable = protected-access
            )
            if have_jit_code:  # pragma: no cover
                if stats.specialized and instruction.offset // 2 not in jit_code[child]:
                    stats = _Stats(unquickened=True)
                elif (
                    stats.adaptive or stats.unquickened
                ) and instruction.offset // 2 in jit_code[child]:
                    stats = _Stats(specialized=True)
            events[lineno, col_offset] += stats
            events[end_lineno, end_col_offset] -= stats
            previous_two = instruction, previous_two[0]
    stats = _Stats()
    for (start, event), (stop, _) in itertools.pairwise(sorted(events.items())):
        stats += event
        yield _SourceChunk(start, stop, stats)


def _source_and_stats(
    path: pathlib.Path,
) -> typing.Generator[tuple[str, _Stats], None, None]:
    """Get the source code for a file, and its statistics."""
    code = _code[path]
    parser = _parse(code)
    chunk = next(parser, None)
    assert chunk is not None
    group: list[str] = []
    with path.open() as file:
        for lineno, line in enumerate(file, 1):
            col_offset = 0
            for character in line:
                position = lineno, col_offset
                # Technically this should be "if chunk.stop == position: ...",
                # but the current form gives us a better chance of recovering if
                # something's off with the source file:
                while chunk.stop <= position:
                    yield "".join(group), chunk.stats
                    group.clear()
                    new_chunk = next(parser, None)
                    assert new_chunk is not None
                    assert new_chunk.start == chunk.stop
                    chunk = new_chunk
                    assert chunk is not None
                assert chunk.start <= position < chunk.stop
                group.append(character)
                col_offset += len(character.encode("utf-8"))
    yield "".join(group), chunk.stats
    extra_chunk = next(parser, None)
    assert extra_chunk is None or (
        extra_chunk.start == chunk.stop
        and extra_chunk.stop == _LAST_POSITION
        and extra_chunk.stats == _Stats()
    ), extra_chunk


def _is_quickened(code: types.CodeType) -> bool:
    return any(  # pragma: no cover
        chunk.stats.specialized or chunk.stats.adaptive for chunk in _parse(code)
    )


def _find_executors() -> (
    typing.Generator[
        tuple[types.CodeType, typing.Sequence[tuple[str, int, int, int]]], None, None
    ]
):  # pragma: no cover
    for code in _code.values():
        for child in _walk_code(code):
            for i in range(0, len(child._co_code_adaptive), 2):  # type: ignore [attr-defined] # pylint: disable = protected-access
                if child._co_code_adaptive[i] == opcode.opmap["ENTER_EXECUTOR"]:  # type: ignore [attr-defined] # pylint: disable = protected-access
                    try:
                        executor = _opcode.get_executor(  # pylint: disable = no-member
                            child, i
                        )
                    except (RuntimeError, ValueError):
                        continue
                    yield (child, executor)


def _callee_from_operand(operand: int) -> types.CodeType | None:  # pragma: no cover
    if operand & 1:
        return typing.cast(
            types.CodeType, ctypes.cast(operand - 1, ctypes.py_object).value
        )
    if operand:
        return typing.cast(
            types.CodeType, ctypes.cast(operand, ctypes.py_object).value.__code__
        )
    return None


def _handle_inlining(
    stack: list[types.CodeType | None], opname: str, operand: int
) -> None:  # pragma: no cover
    if opname == "_PUSH_FRAME":
        stack.append(_callee_from_operand(operand))
    elif opname == "_POP_FRAME":
        assert stack[-1] is not None
        del stack[-1]


def _find_jit_code() -> (
    collections.defaultdict[types.CodeType, set[int]]
):  # pragma: no cover
    if "ENTER_EXECUTOR" not in opcode.opmap:
        return collections.defaultdict(set)
    todo: set[
        tuple[types.CodeType | None, typing.Sequence[tuple[str, int, int, int]]]
    ] = set(_find_executors())
    jit_code: collections.defaultdict[types.CodeType, set[int]] = (
        collections.defaultdict(set)
    )
    done: set[
        tuple[types.CodeType | None, typing.Sequence[tuple[str, int, int, int]]]
    ] = set()
    while todo - done:
        for code, executor in todo - done:
            done.add((code, executor))
            stack: list[types.CodeType | None] = [code]
            side_exits = gc.get_referents(executor)
            assert all(type(side_exit) is type(executor) for side_exit in side_exits)
            for opname, _, target, operand in executor:
                if opname in {"_DEOPT", "_ERROR_POP_N", "_EXIT_TRACE", "_DYNAMIC_EXIT"}:
                    continue
                jump_target = target & 0xFFFF
                error_target = target >> 16
                valid_jump = jump_target < len(executor) and (
                    (jump_target == 0)
                    or executor[jump_target][0]
                    in {"_DEOPT", "_EXIT_TRACE", "_DYNAMIC_EXIT"}
                )
                valid_error = error_target < len(executor) and (
                    (error_target == 0) or executor[error_target][0] in {"_ERROR_POP_N"}
                )
                if (
                    valid_jump
                    and valid_error
                    and jump_target
                    and executor[jump_target][0]
                    in {
                        "_EXIT_TRACE",
                        "_DYNAMIC_EXIT",
                    }
                ):
                    side_exit = side_exits[executor[jump_target][2] & 0xFFFF]
                    todo.add((stack[-1], side_exit))
                elif valid_jump and valid_error and jump_target:
                    assert executor[jump_target][0] == "_DEOPT"
                    target = executor[jump_target][2]
                    assert (
                        stack[-1] is None or target < len(stack[-1]._co_code_adaptive) // 2  # type: ignore [attr-defined] # pylint: disable = protected-access
                    )
                    if stack[-1] is not None:
                        jit_code[stack[-1]].add(target)
                if valid_jump and valid_error and error_target:
                    assert executor[jump_target][0] == "_ERROR_POP_N"
                    target = executor[error_target][3]
                    assert stack[-1] is None or target < len(stack[-1]._co_code_adaptive) // 2  # type: ignore [attr-defined] # pylint: disable = protected-access
                    if stack[-1] is not None:
                        jit_code[stack[-1]].add(target)
                else:
                    assert stack[-1] is None or target < len(stack[-1]._co_code_adaptive) // 2  # type: ignore [attr-defined] # pylint: disable = protected-access
                    if stack[-1] is not None:
                        jit_code[stack[-1]].add(target)
                _handle_inlining(stack, opname, operand)
    return jit_code


def _view(
    path: pathlib.Path,
    *,
    blue: bool = False,
    dark: bool = False,
    out: pathlib.Path | None = None,
    name: str | None = None,
) -> bool:
    """View a code object's source code."""
    writer = _HTMLWriter(blue=blue, dark=dark)
    quickened = False
    for source, stats in _source_and_stats(path):
        if stats.specialized or stats.adaptive:
            quickened = True
        writer.add(source, stats)
    if not quickened:
        _stderr(
            f"The current process contains no quickened code for {name or path}! Try "
            f"modifying it to run longer, or use the --targets option to analyze "
            f"different source files."
        )
        return False
    written = writer.emit()
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.unlink(missing_ok=True)
        out.write_text(written)
        _stderr(path, "->", out)
    else:
        _browse(written)
    return True


def _suggest_target_glob(args: typing.Sequence[str]) -> None:
    """Suggest possible glob patterns for targets."""
    paths = [
        path
        for path, code in _code.items()
        if path.is_file()
        and _PURELIB not in path.parents
        and _STDLIB not in path.parents
        and _TMP not in path.parents
        and _is_quickened(code)
    ]
    if not paths:
        return
    if len(paths) == 1:
        glob = paths[0]
    else:
        try:
            common = pathlib.Path(os.path.commonpath(paths)).resolve()
        except ValueError:  # pragma: no cover
            # Different drives on Windows:
            return
        assert common.is_dir()
        assert _PURELIB not in common.parents, common
        assert _STDLIB not in common.parents, common
        assert _TMP not in common.parents, common
        if (
            common in _PURELIB.parents
            or common in _STDLIB.parents
            or common in _TMP.parents
        ):
            return  # pragma: no cover
        longest = max(len(path.parts) for path in paths)
        if len(common.parts) == longest - 1:
            glob = common / "*"
        else:
            glob = common / "**" / "*"
    cwd = pathlib.Path.cwd().resolve()
    if glob.is_relative_to(cwd):  # pragma: no cover
        glob = glob.relative_to(cwd)
    suggestion = shlex.join(["--targets", str(glob), *args])
    _stderr(f"Did you mean {suggestion}?")


def _browse(page: str) -> None:
    """Open a web browser to display a page."""

    class RequestHandler(http.server.BaseHTTPRequestHandler):
        """A simple handler for a single web page."""

        def do_GET(self) -> None:  # pylint: disable = invalid-name
            """Serve the given HTML."""
            self.send_response(200)
            self.end_headers()
            self.wfile.write(page.encode("utf-8"))

        def log_request(self, *_: object) -> None:
            """Don't log requests."""

    with http.server.HTTPServer(("localhost", 0), RequestHandler) as server:
        # server.handle_request doesn't really need its own thread, but using
        # one makes this easier to test (by patching webbrowser.open_new_tab):
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        webbrowser.open_new_tab(f"http://localhost:{server.server_port}")
        thread.join()


class _Args(typing.TypedDict):
    """Command line arguments."""

    blue: bool
    dark: bool
    output: pathlib.Path | None
    targets: str | None
    command: typing.Sequence[str]
    module: typing.Sequence[str]
    file: typing.Sequence[str]


def _parse_args(args: typing.Sequence[str] | None) -> _Args:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    options = parser.add_argument_group("Options")
    options.add_argument(
        "-b", "--blue", action="store_true", help="Use a red-blue color scheme."
    )
    options.add_argument(
        "-d", "--dark", action="store_true", help="Use a dark color scheme."
    )
    options.add_argument(
        "-h", "--help", action="help", help="Show this help message and exit."
    )
    options.add_argument(
        "-o",
        "--output",
        metavar="<output>",
        help="A directory to write HTML files to (rather than serving them).",
        type=pathlib.Path,
    )
    options.add_argument(
        "-t",
        "--targets",
        metavar="<targets>",
        help="A glob-style pattern indicating target files to analyze.",
    )
    script = parser.add_argument_group(
        "Script (terminates argument list)"
    ).add_mutually_exclusive_group(required=True)
    script.add_argument(
        "-c",
        action="extend",
        help="Equivalent to: python -c ...",
        nargs="...",
        default=[],
        dest="command",
    )
    script.add_argument(
        "-m",
        action="extend",
        help="Equivalent to: python -m ...",
        nargs="...",
        default=[],
        dest="module",
    )
    script.add_argument(
        "file",
        action="extend",
        help="Equivalent to: python <file> ...",
        nargs="?",
        default=[],
        metavar="<file> ...",
        type=lambda s: [s],
    )
    parser.add_argument(
        action="extend", nargs="...", dest="file", help=argparse.SUPPRESS
    )
    return typing.cast(_Args, vars(parser.parse_args(args)))


def main(  # pylint: disable = too-many-branches
    args: typing.Sequence[str] | None = None,
) -> None:
    """Run the main program."""
    parsed = _parse_args(args)
    output = parsed["output"]
    path: pathlib.Path | None
    with tempfile.TemporaryDirectory() as work:
        match parsed:
            case {"command": [source, *argv], "module": [], "file": []}:
                path = pathlib.Path(work, "__main__.py").resolve()
                path.write_text(source, encoding="utf-8")
                name: str | None = "the provided command"
                with _patch_sys_argv(argv), _catch_exceptions() as caught:
                    runpy.run_path(  # pylint: disable = no-member
                        str(path), run_name="__main__"
                    )
            case {"command": [], "module": [source, *argv], "file": []}:
                with (
                    _patch_sys_argv(argv),
                    _insert_sys_path(pathlib.Path().resolve()),
                    _catch_exceptions() as caught,
                ):
                    path = _main_file_for_module(source)
                    runpy.run_module(  # pylint: disable = no-member
                        source, run_name="__main__", alter_sys=True
                    )
                name = source
            case {"command": [], "module": [], "file": [source, *argv]}:
                with (
                    _patch_sys_argv(argv),
                    _insert_sys_path(pathlib.Path(source).parent.resolve()),
                    _catch_exceptions() as caught,
                ):
                    runpy.run_path(  # pylint: disable = no-member
                        source, run_name="__main__"
                    )
                path = pathlib.Path(source).resolve()
                name = source
            case _:  # pragma: no cover
                assert False, parsed
        paths: list[pathlib.Path] = []
        if parsed["targets"] is not None:
            name = None
            for match in pathlib.Path().resolve().glob(parsed["targets"]):
                if match.resolve() in _code:
                    paths.append(match.resolve())
        elif path is not None and path in _code:
            paths.append(path)
        if not paths:
            _stderr("No source files found!")
        else:
            if output is not None:
                try:
                    common = pathlib.Path(os.path.commonpath(paths)).resolve()
                except ValueError:  # pragma: no cover
                    _stderr("Unable to resolve source files (different drives)!")
                    if caught:
                        raise caught[0] from None
                    return
                if common.is_file():
                    common = common.parent
                assert common.is_dir(), common
                output = output.resolve()
                path_and_out: typing.Generator[
                    tuple[pathlib.Path, pathlib.Path | None], None, None
                ] = (
                    (path, output / path.relative_to(common).with_suffix(".html"))
                    for path in paths
                )
            else:
                path_and_out = ((path, None) for path in paths)
            found = False
            for path, out in sorted(path_and_out):
                found |= _view(
                    path, blue=parsed["blue"], dark=parsed["dark"], out=out, name=name
                )
            if not found and not parsed["targets"]:
                _suggest_target_glob(args or sys.argv[1:])
        if caught:
            raise caught[0] from None


if __name__ == "__main__":  # pragma: no cover
    main(sys.argv[1:])
