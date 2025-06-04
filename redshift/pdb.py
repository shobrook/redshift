# Standard library
import pdb
import sys
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


class RedshiftPdb(pdb.Pdb):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prompt = "\033[31m(redshift)\033[0m "
        self.config = (
            Config.from_env() if kwargs.get("config") is None else kwargs["config"]
        )
        self.agent = Agent(self, self.config.model, self.config.max_iters)
        # TODO: Store command history (use in _build_query_prompt as context)

    ## Helpers ##

    def _build_query_prompt(self, query: str) -> str:
        # TODO: Breakpoint
        # TODO: Run command (" ".join(sys.argv))
        # TODO: Stdin (input to the program)
        return query

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
    #     prompt = build_exception_prompt()  # Error message, enriched stack trace, etc.
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
