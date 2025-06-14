# Standard library
import linecache

# Third party
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

Below is information about the current state of your debugger:

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

Use this information as context as you're calling tools to operate the debugger."""


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
        "file": "Searching {arg}",
        "none": "Generating answer",
    }

    def __init__(self, pdb):
        self.pdb = pdb
        self.history = []

    def tool_call(self, tool_name: str, value: str | list[str], arg: str = ""):
        message = self.MESSAGES[tool_name].format(arg=arg)

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

    def final_output(self, response):
        for part in response:
            print(part.choices[0].delta.content or "", end="")

        print("\n\n")


######
# MAIN
######


class Agent:
    def __init__(self, pdb, config: Config):
        self.pdb = pdb
        self.config = config
        self.printer = Printer(pdb)
        self._history = []

    def _update_system_prompt(self, *args, **kwargs):
        curr_filename = self.pdb.curframe.f_code.co_filename
        curr_file_code = self.pdb.format_frame_line(self.pdb.curframe)
        stack_trace = self.pdb.format_stack_trace()

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
            PrintExpressionTool(self.pdb, self.printer),
            PrintArgsTool(self.pdb, self.printer),
            PrintRetvalTool(self.pdb, self.printer),
            # ReadFileTool(self.pdb, self.printer, self.config.agent_model),
            ShowSourceTool(self.pdb, self.printer),
            GenerateAnswerTool(
                self.pdb, self.printer, self.config.answer_model, prompt, self._history
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
            # TODO: Fix these synchronous methods
            tool_call = agent.call_tool("none", messages)
            tool_result = agent.run_tool(tool_call, messages)
            output = tool_result.raw_output

        self._history += [Message.user(prompt), Message.assistant(output)]
        self.printer.history = []
        return output
