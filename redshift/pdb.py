# Standard library
import pdb
import sys
import json
import linecache
from typing import Generator

# Local
try:
    from redshift.agent import Agent
    from redshift.config import Config
    from redshift.shared.truncator import Truncator
    from redshift.shared.serializers import serialize_vars
    from redshift.shared.is_internal_frame import is_internal_frame
except ImportError:
    from .agent import Agent
    from .config import Config
    from .shared.truncator import Truncator
    from .shared.serializers import serialize_vars
    from .shared.is_internal_frame import is_internal_frame


class RedshiftPdb(pdb.Pdb):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prompt = "\033[31m(Redshift)\033[0m "
        self.config = (
            Config.from_env() if kwargs.get("config") is None else kwargs["config"]
        )
        self._agent = Agent(self, self.config)
        self._last_command = None  # Used to detect follow-ups
        # TODO: Capture command history; use as context for agent
        # TODO: Capture stdin; use as context for agent
        # TODO: Get program run command (" ".join(sys.argv)); use as context for agent

    ## Helpers ##

    def _build_query_prompt(self, arg: str) -> str:
        query = arg.strip()
        if self._last_command == "ask":  # Follow-up, context is already attached
            return f"<user_query>\n{query}\n</user_query>"

        prompt = "This is the breakpoint (-> indicates the line where the program is currently paused):\n\n"
        prompt += self.format_breakpoint()
        prompt += "\n\nThis is my question:\n\n"
        prompt += f"<user_query>\n{query}\n</user_query>"

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

    def _is_follow_up(self, cmd: str) -> bool:
        if cmd and cmd.lower().lstrip().startswith("ask "):
            if self._last_command == "ask":
                return True

        return False

    def format_breakpoint(self) -> str:
        filename = self.curframe.f_code.co_filename
        code = self.format_frame_line(self.curframe)
        breakpoint_prompt = f"<breakpoint>\n<path>\n{filename}\n</path>\n<code>\n{code}\n</code>\n</breakpoint>"
        return breakpoint_prompt

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

    def format_variables(self, model: str, max_tokens: int = 4096) -> str:
        locals_ = self.curframe_locals
        locals_ = serialize_vars(locals_)
        locals_ = json.loads(locals_)

        globals_ = self.curframe.f_globals
        globals_ = serialize_vars(globals_)
        globals_ = json.loads(globals_)

        truncator = Truncator(model)
        tokens_per_val = max_tokens // (len(locals_) + len(globals_))

        formatted_str = "<globals>\n"
        for key, value in globals_.items():
            value = truncator.truncate_middle(value, tokens_per_val)
            formatted_str += f"{key} = {value}\n"
        formatted_str += "</globals>\n"
        formatted_str += "<locals>\n"
        for key, value in locals_.items():
            value = truncator.truncate_middle(value, tokens_per_val)
            formatted_str += f"{key} = {value}\n"
        formatted_str += "</locals>\n"

        return formatted_str

    def format_stack_trace(self, model: str, max_tokens: int = 4096) -> str:
        stack_trace = ""
        hidden_count = 0
        for frame_lineno in self.stack:
            frame, _ = frame_lineno
            is_hidden = self.config.hide_external_frames and not is_internal_frame(
                frame
            )

            if is_hidden:
                hidden_count += 1
                continue
            elif hidden_count > 0:
                plural = "s" if hidden_count > 1 else ""
                stack_trace += f"[... {hidden_count} hidden frame{plural} ...]"
                hidden_count = 0

            if frame is self.curframe:
                prefix = "> "
            else:
                prefix = "  "

            stack_entry = f"{prefix}{self.format_stack_entry(frame_lineno, '\n-> ')}\n"
            if not stack_entry.strip():
                continue

            stack_trace += stack_entry

        if hidden_count > 0:
            plural = "s" if hidden_count > 1 else ""
            stack_trace += f"[... {hidden_count} hidden frame{plural} ...]"

        stack_trace = stack_trace.rstrip()

        # Truncation
        truncator = Truncator(model)
        rev_stack_trace = "\n".join(stack_trace.splitlines()[::-1])
        rev_stack_trace = truncator.truncate_end(
            rev_stack_trace, max_tokens, type="line"
        )
        stack_trace = "\n".join(rev_stack_trace.splitlines()[::-1])

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

    def execute_code(self, code: str):
        locals = self.curframe_locals
        globals = self.curframe.f_globals

        try:
            code = compile(code, "<stdin>", "exec")
            save_stdout = sys.stdout
            save_stdin = sys.stdin
            save_displayhook = sys.displayhook
            try:
                sys.stdin = self.stdin
                sys.stdout = self.stdout
                sys.displayhook = self.displayhook
                exec(code, globals, locals)
            finally:
                sys.stdout = save_stdout
                sys.stdin = save_stdin
                sys.displayhook = save_displayhook
        except:
            self._error_exc()

    def get_curr_file_lines(self) -> list[str]:
        filename = self.curframe.f_code.co_filename
        if filename.startswith("<frozen"):
            tmp = self.curframe.f_globals.get("__file__")
            if isinstance(tmp, str):
                filename = tmp

        lines = linecache.getlines(filename, self.curframe.f_globals)
        return lines

    ## Overloads ##

    def default(self, line):
        # TODO: Wrong overload
        if not self._is_follow_up(line):
            self._agent.reset()
            self._last_command = None

        return super().default(line)

    def onecmd(self, line):
        if not self._is_follow_up(line):
            self._agent.reset()
            self._last_command = None

        return super().onecmd(line)

    ## New commands ##

    def do_ask(self, arg: str):
        """ask question

        Ask a question about the state of the program. An LLM will steer the
        debugger to find the answer to your question.

        Example: `ask why is x null?`
        """

        if not self.curframe:
            self.message("You can only use redshift if a frame is available")
            return

        self._save_state()
        prompt = self._build_query_prompt(arg)
        self._agent.ask(prompt)
        self._last_command = "ask"
        self._restore_state()

    def do_run(self, arg: str):
        """generate prompt

        Generate and execute code in the context of the current stack frame.
        Generated code is based off the prompt you provide and will not be
        executed without your approval.

        Example: `generate visualize the training loss using matplotlib`
        """

        if not self.curframe:
            self.message("You can only use redshift if a frame is available")
            return

        prompt = arg.strip()
        self._agent.run(prompt)
        # TODO: Handle follow-ups


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


# TODO: Test post-mortem / exception handling
# TODO: Test async + multithreading
