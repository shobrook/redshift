# Standard library
import pdb
import sys
import linecache
from typing import Generator

# Local
try:
    from redshift.agent import Agent
    from redshift.config import Config
    from redshift.shared.is_internal_frame import is_internal_frame
except ImportError:
    from agent import Agent
    from config import Config
    from shared.is_internal_frame import is_internal_frame


#########
# HELPERS
#########


# TODO: Make a printer class that handles progress messages and streaming final output


class RedshiftPdb(pdb.Pdb):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prompt = "\033[31m(redshift)\033[0m "
        self.config = (
            Config.from_env() if kwargs.get("config") is None else kwargs["config"]
        )
        self.agent = Agent(self, self.config)
        # TODO: Store command history (use in _build_query_prompt as context)

    ## Helpers ##

    def _build_query_prompt(self, query: str) -> str:
        filename = self.curframe.f_code.co_filename
        code = self.format_frame_line(self.curframe)
        prompt = f"<breakpoint>\n<path>\n{filename}\n</path>\n<code>\n{code}\n</code>\n</breakpoint>"
        prompt += f"\n\n<user_query>\n{query}\n</user_query>"

        # TODO: Run command (" ".join(sys.argv))
        # TODO: Stdin (input to the program)
        return prompt

    def _save_state(self):
        self._original_curindex = self.curindex
        self._original_lineno = self.lineno

    def _restore_state(self):
        self.curindex = self._original_curindex
        self.curframe = self.stack[self.curindex][0]
        self.curframe_locals = self.curframe.f_locals
        self.set_convenience_variable(self.curframe, "_frame", self.curframe)
        self.lineno = self._original_lineno

    def format_lines(
        self,
        lines: list[str],
        start: int,
        breaks: tuple[int] = (),
        frame=None,
    ) -> str:
        if frame:
            curr_lineno = frame.f_lineno
            exc_lineno = self.tb_lineno.get(frame, -1)
        else:
            curr_lineno = exc_lineno = -1

        lines_str = ""
        for lineno, line in enumerate(lines, start):
            s = str(lineno).rjust(3)
            if len(s) < 4:
                s += " "
            if lineno in breaks:
                s += "B"
            else:
                s += " "
            if lineno == curr_lineno:
                s += "->"
            elif lineno == exc_lineno:
                s += ">>"

            lines_str += f"{s}\t{line.rstrip()}\n"

        lines_str = lines_str.rstrip()
        return lines_str

    def iter_stack(self) -> Generator[tuple[any, int], None, None]:
        for frame_lineno in self.stack:
            frame, _ = frame_lineno
            if self.config.hide_external_frames:
                if not is_internal_frame(frame):
                    continue

            yield frame_lineno

    def format_stack_trace(self) -> str:
        # TODO: Optionally enrich the stack trace with serialized locals
        # TODO: Mark hidden (e.g. external) frames

        stack_trace = ""
        for frame_lineno in self.iter_stack():
            frame, _ = frame_lineno
            if frame is self.curframe:
                prefix = "> "
            else:
                prefix = "  "

            # TODO: Remove common file path prefix from each frame
            stack_entry = f"{prefix}{self.format_stack_entry(frame_lineno, '\n-> ')}\n"
            if not stack_entry.strip():
                continue

            stack_trace += stack_entry

        stack_trace = stack_trace.rstrip()
        return stack_trace

    def format_frame_line(self, frame, window: int = 5) -> str:
        curr_filename = frame.f_code.co_filename
        curr_lineno = frame.f_lineno
        lines = linecache.getlines(curr_filename, frame.f_globals)
        breaklist = self.get_file_breaks(curr_filename)

        first = max(1, curr_lineno - window)
        last = min(len(lines), curr_lineno + window)

        snapshot = self.format_lines(lines[first - 1 : last], first, breaklist, frame)
        return snapshot

    ## New commands ##

    def do_ask(self, arg: str):
        self._save_state()

        query = arg.strip()
        prompt = self._build_query_prompt(query)
        output = self.agent.run(prompt)
        self.message(output)

        # TODO: Handle follow-up questions

        self._restore_state()

    # def do_fix(self):
    #     # Use agent with more codebase tools
    #     output = self.agent.run(prompt)

    #     self._restore_state()

    def do_run(self, arg: str):
        # Generates and executes code within the program context
        pass


######
# MAIN
######


def run(statement, globals=None, locals=None):
    RedshiftPdb().run(statement, globals, locals)


def runeval(expression, globals=None, locals=None):
    return RedshiftPdb().runeval(expression, globals, locals)


def runctx(statement, globals, locals):
    run(statement, globals, locals)


def runcall(*args, **kwds):
    return RedshiftPdb().runcall(*args, **kwds)


def set_trace(*, header=None):
    redshift_pdb = RedshiftPdb()
    if header is not None:
        redshift_pdb.message(header)

    redshift_pdb.set_trace(sys._getframe().f_back)


def post_mortem(t=None):
    if t is None:
        exc = sys.exception()
        if exc is not None:
            t = exc.__traceback__

    if t is None or (isinstance(t, BaseException) and t.__traceback__ is None):
        raise ValueError(
            "A valid traceback must be passed if no exception is being handled"
        )

    redshift_pdb = RedshiftPdb()
    redshift_pdb.reset()
    redshift_pdb.interaction(None, t)


def pm():
    post_mortem(sys.last_exc)


def main():
    pass  # TODO
