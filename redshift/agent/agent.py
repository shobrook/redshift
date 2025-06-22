# Standard library
import time
import threading
import multiprocessing

# Third party
from rich.live import Live
from rich.text import Text
from rich.console import Console
from rich.markdown import Markdown
from saplings.dtos import Message
from saplings import COTAgent, Model

# Local
try:
    from redshift.config import Config
    from redshift.agent.tools import (
        MoveFrameTool,
        PrintExpressionTool,
        PrintArgsTool,
        PrintRetvalTool,
        ReadFileTool,
        ShowSourceTool,
        GenerateAnswerTool,
    )
    from redshift.shared.truncator import Truncator
except ImportError:
    from ..config import Config
    from agent.tools import (
        MoveFrameTool,
        PrintExpressionTool,
        PrintArgsTool,
        PrintRetvalTool,
        ReadFileTool,
        ShowSourceTool,
        GenerateAnswerTool,
    )
    from shared.truncator import Truncator


#########
# HELPERS
#########


SYSTEM_PROMPT = """You are an AI assistant that helps users debug Python code. \
You are activated when the user's program throws an exception or hits a breakpoint. \
You will receive a query from the user about the state of their program at that breakpoint. \
Your job is to choose the best action. Call tools to find information that will help answer the user's query. \
Call functions.none when you have enough information to answer.

<tool_calling>
You have tools (functions) that allow you to operate the Python debugger (pdb). \
Follow these rules when calling tools:
- DO NOT call a tool that you've used before with the same arguments, unless you're in a different frame.
- DO NOT use functions.file to get the definition of a function or class. Use functions.source instead.
- If the user is referring to, or asking for, information that is in your history, call functions.none.
- If after attempting to gather information you are still unsure how to answer the query, call functions.none.
- If the query is a greeting, or neither a question nor an instruction, call functions.none.
- If the output of a function is empty or an error message, try calling the function again with DIFFERENT arguments OR try calling a different function.
- You MUST call functions.expression at least once. Use it to get the value of a variable or expression that you believe is relevant to the user's query.
- Call functions.args or functions.retval to understand the current state of the function call.
- Call functions.source or functions.file to get context on relevant code (e.g. function definitions, dependencies, etc.).
- Call functions.move if you need to inspect a different function call in the stack trace.
- Call functions.none when you have enough information to answer the user's query.
</tool_calling>

--

Below is information about the state of your debugger:

<debugger_state>
This is the stack trace, with the most recent frame at the bottom:

<stack_trace>
{stack_trace}
</stack_trace>

This is the current frame, which determines the context of your tool calls:

<current_frame>
{curr_frame}
</current_frame>

This is your position in the file associated with the current frame:

<current_file>
<path>
{curr_file_path}
</path>
<code>
{curr_file_code}
</code>
</current_file>
</debugger_state>

Use this information to understand the current frame you're in as you're calling tools \
to operate the debugger."""


class Printer(object):
    RED = "\033[31m"
    GREY = "\033[37m"
    RESET = "\033[0m"
    MESSAGES = {
        "move": "Moving {arg} the call stack",
        "args": "Getting arguments",
        "retval": "Getting return value",
        "source": "Reading source code",
        "expression": "Evaluating expression",
        "semantic": "Searching {arg}",
        "read": "Reading file",
        "none": "Thinking",
    }

    def __init__(self, pdb):
        self.pdb = pdb
        self.history = []

        self._is_thinking = False
        self._thinking_thread = None
        self._thinking_start_time = None

    def _animate_thinking(self):
        self._is_thinking = multiprocessing.Value("b", True)

        def ellipsis():
            with Live(refresh_per_second=4, transient=True) as live:
                dots = 0
                while self._is_thinking.value:
                    text = Text(f"{self.RED}└──{self.RESET} Thinking")
                    text.append("." * dots)
                    text.append("\n")
                    live.update(text)
                    dots = (dots + 1) % 4
                    time.sleep(0.25)

        # Start the animation in a separate thread
        self._thinking_thread = threading.Thread(target=ellipsis)
        self._thinking_thread.daemon = True
        self._thinking_thread.start()

    def _stop_thinking_animation(self):
        self._is_thinking.value = False
        if self._thinking_thread and self._thinking_thread.is_alive():
            self._thinking_thread.join(timeout=1.0)

    def tool_call(self, tool_name: str, value: str | list[str] = "", arg: str = ""):
        message = self.MESSAGES[tool_name].format(arg=arg)

        if tool_name == "none":
            self._thinking_start_time = time.time()
            self.pdb.message(f"{self.RED}│{self.RESET}")
            self._animate_thinking()
            return

        if not self.history or tool_name == "move":
            self.pdb.message(f"{self.RED}│{self.RESET}")
            self.pdb.message(f"{self.RED}├──{self.RESET} {message}")
        elif self.history[-1] != tool_name:
            self.pdb.message(f"{self.RED}│{self.RESET}")
            self.pdb.message(f"{self.RED}├──{self.RESET} {message}")

        values = [value] if isinstance(value, str) else value
        for value in values:
            self.pdb.message(
                f"{self.RED}│   {self.RESET}{self.GREY}{value}{self.RESET}"
            )

        self.history.append(tool_name)

    def final_output(self, response: str):
        self._stop_thinking_animation()
        time_taken = f"{time.time() - self._thinking_start_time:.2f}"
        self.pdb.message(f"{self.RED}└──{self.RESET} Thought for {time_taken} seconds")

        console = Console()
        markdown = Markdown(
            response,
            code_theme="monokai",
            inline_code_lexer="python",
            inline_code_theme="monokai",
        )
        console.print()
        console.print(markdown)
        console.print()


def was_tool_called(messages: list[Message], tool_name: str) -> bool:
    for message in messages:
        if message.role != "assistant":
            continue

        if not message.tool_calls:
            continue

        for tool_call in message.tool_calls:
            if tool_call.name == tool_name:
                return True

    return False


######
# MAIN
######


class Agent:
    def __init__(self, pdb, config: Config):
        self.pdb = pdb
        self.config = config
        self.truncator = Truncator(self.config.agent_model)
        self.printer = Printer(pdb)
        self._history = []

    def _truncate_stack_trace(self, stack_trace: str, max_tokens: int = 4096) -> str:
        rev_stack_trace = "\n".join(stack_trace.splitlines()[::-1])
        rev_stack_trace = self.truncator.truncate_end(
            rev_stack_trace, max_tokens, type="line"
        )
        stack_trace = "\n".join(rev_stack_trace.splitlines()[::-1])
        return stack_trace

    def _update_system_prompt(self, *args, **kwargs):
        curr_filename = self.pdb.curframe.f_code.co_filename
        curr_file_code = self.pdb.format_frame_line(self.pdb.curframe)
        stack_trace = self.pdb.format_stack_trace()
        stack_trace = self._truncate_stack_trace(stack_trace)

        return SYSTEM_PROMPT.format(
            stack_trace=stack_trace,
            curr_frame=self.pdb.format_stack_entry(
                self.pdb.stack[self.pdb.curindex], "\n-> "
            ),
            curr_file_path=curr_filename,
            curr_file_code=curr_file_code,
        )

    def reset(self):
        self._history = []
        self.printer.history = []

    def run(self, prompt: str):
        tools = [
            MoveFrameTool(self.pdb, self.printer),
            PrintExpressionTool(self.pdb, self.printer, self.truncator),
            PrintArgsTool(self.pdb, self.printer, self.truncator),
            PrintRetvalTool(self.pdb, self.printer, self.truncator),
            ReadFileTool(self.pdb, self.printer, self.truncator),
            ShowSourceTool(self.pdb, self.printer, self.truncator),
            GenerateAnswerTool(
                self.pdb,
                self.printer,
                self.config.response_model,
                prompt,
                self._history,
            ),
        ]
        model = Model(self.config.agent_model)
        agent = COTAgent(
            tools,
            model,
            SYSTEM_PROMPT,
            tool_choice="required",
            max_depth=self.config.max_iters,
            verbose=False,
            update_prompt=self._update_system_prompt,
        )
        messages = agent.run(prompt, self._history)

        output = messages[-1].raw_output
        if not was_tool_called(messages, "none"):
            messages = self._history + messages
            tool_call = agent.call_tool("none", messages)
            tool_result = agent.run_tool(tool_call, messages)
            output = tool_result.raw_output

        self._history += [Message.user(prompt), Message.assistant(output)]
        self.printer.history = []
        return output
