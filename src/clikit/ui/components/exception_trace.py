import ast
import inspect
import io
import keyword
import sys
import tokenize
import traceback

from clikit.api.io import IO
from clikit.utils._compat import PY2
from clikit.utils._compat import PY36
from clikit.utils._compat import encode


class Highlighter(object):

    TOKEN_DEFAULT = "token_default"
    TOKEN_COMMENT = "token_comment"
    TOKEN_STRING = "token_string"
    TOKEN_NUMBER = "token_number"
    TOKEN_KEYWORD = "token_keyword"
    TOKEN_BUILTIN = "token_builtin"
    TOKEN_OP = "token_op"
    LINE_MARKER = "line_marker"
    LINE_NUMBER = "line_number"

    DEFAULT_THEME = {
        TOKEN_STRING: "fg=light_yellow",
        TOKEN_NUMBER: "fg=green",
        TOKEN_COMMENT: "fg=default;options=dark,italic",
        TOKEN_KEYWORD: "fg=light_blue",
        TOKEN_BUILTIN: "fg=light_magenta",
        TOKEN_DEFAULT: "fg=default",
        TOKEN_OP: "fg=default;options=dark",
        LINE_MARKER: "fg=red;options=bold",
        LINE_NUMBER: "fg=default;options=dark",
    }

    KEYWORDS = set(keyword.kwlist)
    BUILTINS = set(
        __builtins__.keys() if type(__builtins__) is dict else dir(__builtins__)
    )

    def __init__(self):
        self._theme = self.DEFAULT_THEME.copy()

    def code_snippet(self, source, line, lines_before=2, lines_after=2):
        token_lines = self.highlighted_lines(source)
        token_lines = self.line_numbers(token_lines, line)

        offset = line - lines_before - 1
        offset = max(offset, 0)
        length = lines_after + lines_before + 1
        token_lines = token_lines[offset : offset + length]

        return token_lines

    def highlighted_lines(self, source):
        source = source.replace("\r\n", "\n").replace("\r", "\n")

        return self.split_to_lines(source)

    def split_to_lines(self, source):
        lines = []
        current_line = 1
        current_col = 0
        buffer = ""
        current_type = None
        tokens = tokenize.tokenize(io.BytesIO(encode(source)).readline)
        line = ""
        current_token_info = None
        for token_info in tokens:
            token_type, token_string, start, end, _ = token_info
            lineno = start[0]
            if lineno == 0:
                # Encoding line
                continue

            if token_type == tokenize.ENDMARKER:
                # End of source
                lines.append(line)
                break

            if lineno > current_line:
                diff = lineno - current_line
                if diff > 1:
                    lines += [""] * (diff - 1)

                line += "<{}>{}</>".format(
                    self._theme[current_type], buffer.rstrip("\n")
                )

                # New line
                lines.append(line)
                line = ""
                current_line = lineno
                current_col = 0
                buffer = ""

            if start[1] > current_col:
                buffer += token_info.line[current_col : start[1]]

            if token_string in self.KEYWORDS:
                new_type = self.TOKEN_KEYWORD
            elif token_string in self.BUILTINS:
                new_type = self.TOKEN_BUILTIN
            elif token_type == tokenize.STRING:
                new_type = self.TOKEN_STRING
            elif token_type == tokenize.NUMBER:
                new_type = self.TOKEN_NUMBER
            elif token_type == tokenize.COMMENT:
                new_type = self.TOKEN_COMMENT
            elif token_type == tokenize.OP:
                new_type = self.TOKEN_OP
            elif token_type == tokenize.NEWLINE:
                continue
            else:
                new_type = self.TOKEN_DEFAULT

            if current_type is None:
                current_type = new_type

            if current_type != new_type:
                line += "<{}>{}</>".format(self._theme[current_type], buffer)
                buffer = ""
                current_type = new_type

            buffer += token_string
            current_col = end[1]
            current_token_info = token_info

        return lines

    def line_numbers(self, lines, mark_line=None):
        max_line_length = len(str(len(lines)))

        snippet_lines = []
        for i, line in enumerate(lines):
            if mark_line is not None:
                if mark_line == i + 1:
                    snippet = "  <{}>></> ".format(self._theme[self.LINE_MARKER])
                else:
                    snippet = "    "

            line_number = "{:>{}}".format(i + 1, max_line_length)
            snippet += "<{}>{}</><{}>|</> {}".format(
                "b" if mark_line == i + 1 else self._theme[self.LINE_NUMBER],
                line_number,
                self._theme[self.LINE_NUMBER],
                line,
            )
            snippet_lines.append(snippet)

        return snippet_lines


class ExceptionTrace(object):
    """
    Renders the trace of an exception.
    """

    THEME = {
        "comment": "<fg=black;options=bold>",
        "keyword": "<fg=yellow>",
        "builtin": "<fg=blue>",
        "literal": "<fg=magenta>",
    }

    AST_ELEMENTS = {
        "builtins": __builtins__.keys()
        if type(__builtins__) is dict
        else dir(__builtins__),
        "keywords": [
            getattr(ast, cls)
            for cls in dir(ast)
            if keyword.iskeyword(cls.lower())
            and inspect.isclass(getattr(ast, cls))
            and issubclass(getattr(ast, cls), ast.AST)
        ],
    }

    def __init__(self, exception):  # type: (Exception) -> None
        self._exception = exception
        self._exc_info = sys.exc_info()
        self._higlighter = Highlighter()

    def render(self, io, simple=False):  # type: (IO, bool) -> None
        if simple:
            io.write_line("<error>{}</error>".format(str(self._exception)))
            return

        if not PY36:
            return self._render_legacy(io)

        return self._render_exception(io, self._exception)

    def _render_legacy(self, io):
        if hasattr(self._exception, "__traceback__"):
            tb = self._exception.__traceback__
        else:
            tb = self._exc_info[2]

        title = "\n<error>{}</error>\n\n<b>{}</b>".format(
            self._exception.__class__.__name__, str(self._exception)
        )

        io.write_line(title)

        if io.is_verbose():
            io.write_line("")
            self._render_traceback(io, tb)

    def _render_exception(self, io, exception):
        from woops.inspector import Inspector

        inspector = Inspector(exception)
        if not inspector.frames:
            return

        title = "\n<error>{}</error>\n\n<b>{}</b>\n".format(
            inspector.exception_name, inspector.exception_message
        )

        io.write_line(title)

        frame = inspector.frames[-1]
        code_lines = self._higlighter.code_snippet(
            frame.file_content, frame.lineno, 4, 4
        )

        io.write_line(
            "at <fg=light_cyan>{}</>:<b>{}</b> in <fg=light_green>{}</>".format(
                frame.filename, frame.lineno, frame.function
            )
        )
        for code_line in code_lines:
            io.write_line(code_line)

        remaining_frames_length = len(inspector.frames[:-1])
        if io.is_verbose() and remaining_frames_length:
            io.write_line("")
            io.write_line("<fg=yellow;options=bold>Stack trace</>:")
            max_frame_length = len(str(remaining_frames_length))
            for i, frame in enumerate(reversed(inspector.frames[:-1])):
                io.write_line("")
                io.write_line(
                    "<fg=light_magenta>{:>{}}</> at <fg=light_cyan>{}</>:<b>{}</b> in <fg=light_green>{}</>".format(
                        i + 1,
                        max_frame_length,
                        frame.filename,
                        frame.lineno,
                        frame.function,
                    )
                )

                code_lines = self._higlighter.code_snippet(
                    frame.file_content, frame.lineno,
                )

                for code_line in code_lines:
                    io.write_line(code_line)

        if inspector.has_previous_exception():
            io.write_line("")
            io.write_line("")
            io.write_line("occurred when handling the following error:")
            io.write_line("")
            self._render_exception(io, inspector.previous_exception)

    def _render_traceback(self, io, tb):  # type: (IO, ...) -> None
        frames = []
        while tb:
            frames.append(self._format_traceback_frame(io, tb))

            tb = tb.tb_next

        io.write_line("<b>Traceback (most recent call last):</b>")
        io.write_line("".join(traceback.format_list(frames)))

    def _format_traceback_frame(self, io, tb):  # type: (IO, ...) -> Tuple[Any]
        frame_info = inspect.getframeinfo(tb)
        filename = frame_info.filename
        lineno = frame_info.lineno
        function = frame_info.function
        line = frame_info.code_context[0]

        stripped_line = line.lstrip(" ")
        try:
            tree = ast.parse(stripped_line, mode="exec")
            formatted = self._format_tree(tree, stripped_line, io)
            formatted = (len(line) - len(stripped_line)) * " " + formatted
        except SyntaxError:
            formatted = line

        return (
            io.format("<c1>{}</c1>".format(filename)),
            "<fg=blue;options=bold>{}</>".format(lineno) if not PY2 else lineno,
            "<b>{}</b>".format(function),
            formatted,
        )

    def _format_tree(self, tree, source, io):
        offset = 0
        chunks = []

        nodes = [n for n in ast.walk(tree)]

        displayed_nodes = []

        for node in nodes:
            nodecls = node.__class__
            nodename = nodecls.__name__

            if "col_offset" not in dir(node):
                continue

            if nodecls in self.AST_ELEMENTS["keywords"]:
                displayed_nodes.append((node, nodename.lower(), "keyword"))
            elif nodecls == ast.Name and node.id in self.AST_ELEMENTS["builtins"]:
                displayed_nodes.append((node, node.id, "builtin"))
            elif nodecls == ast.Str:
                displayed_nodes.append((node, "'{}'".format(node.s), "literal"))
            elif nodecls == ast.Num:
                displayed_nodes.append((node, str(node.n), "literal"))

        displayed_nodes.sort(key=lambda elem: elem[0].col_offset)

        for dn in displayed_nodes:
            node = dn[0]
            s = dn[1]
            theme = dn[2]

            begin_col = node.col_offset

            src_chunk = source[offset:begin_col]
            chunks.append(src_chunk)
            chunks.append(io.format("{}{}</>".format(self.THEME[theme], s)))
            offset = begin_col + len(s)

        chunks.append(source[offset:])

        return "".join(chunks)
