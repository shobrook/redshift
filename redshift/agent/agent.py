# Standard library
import linecache

# Third party
from saplings.dtos import Message
from saplings import COTAgent, Model

# Local
try:
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


SYSTEM_PROMPT = """You are an agentic AI assistant called 'redshift' that helps users debug Python code. \
You are activated when the user's program throws an exception or hits a breakpoint. \
You will receive a query from the user about the state of their program at that breakpoint. \
Your job is to choose the best action. Call tools to find information that will help answer the user's query. \
Call the 'done' tool when you have enough information to answer.

<tool_calling>
You have tools that allow you to operate the Python debugger (pdb). \
You can move up and down the call stack, get variable values, read source code, etc. \
Use these tools to gather context for the user's query. \
Call 'done' when you have enough to answer the query.
</tool_calling>

--

Below is information about the current state of your debugger:

<debugger_info>
This is the stack trace, with the most recent frame at the bottom. \
An arrow (>) indicates your current frame, which determines the context of your tool calls:

<stack_trace>
{stack_trace}
</stack_trace>

This is your position in the file associated with the current frame:

<current_file>
<path>{curr_file_path}</path>
<code>
{curr_file_code}
</code>
</current_file>
</debugger_info>

Use this information to understand the current state of your debugger as you call tools to gather context."""
# TODO: Add rules in the <tool_calling> section


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
    def __init__(self, pdb, model: str, max_iters: int):
        self.pdb = pdb
        self.model = model
        self.max_iters = max_iters
        self.history = []

    def _code_snapshot(self, window: int = 5) -> str:
        curr_filename = self.pdb.curframe.f_code.co_filename
        curr_lineno = self.pdb.curframe.f_lineno
        lines = linecache.getlines(curr_filename, self.pdb.curframe.f_globals)
        breaklist = self.pdb.get_file_breaks(curr_filename)

        first = max(1, curr_lineno - window)
        last = min(len(lines), curr_lineno + window)

        snapshot = self.pdb.format_lines(
            lines[first - 1 : last], first, breaklist, self.pdb.curframe
        )
        return snapshot

    def _stack_trace(self) -> str:
        stack_trace = ""
        for frame_lineno in self.pdb.iter_stack():
            frame, _ = frame_lineno
            if frame is self.pdb.curframe:
                prefix = "> "
            else:
                prefix = "  "

            stack_trace += (
                f"{prefix}{self.pdb.format_stack_entry(frame_lineno, '\n-> ')}\n"
            )
        stack_trace = stack_trace.rstrip()

        return stack_trace

    def _update_system_prompt(self, *args, **kwargs):
        # TODO: Formatting issues with the stack trace and code
        curr_filename = self.pdb.curframe.f_code.co_filename
        curr_file_code = self._code_snapshot()
        stack_trace = self._stack_trace()

        return SYSTEM_PROMPT.format(
            stack_trace=stack_trace,
            curr_file_path=curr_filename,
            curr_file_code=curr_file_code,
        )

    def reset(self):
        self.history = []

    def run(self, prompt: str):
        tools = [
            MoveFrameTool(self.pdb),
            PrintExpressionTool(self.pdb),
            PrintArgsTool(self.pdb),
            PrintRetvalTool(self.pdb),
            ReadFileTool(self.pdb, self.model),
            ShowSourceTool(self.pdb),
            GenerateAnswerTool(self.pdb, self.model),
        ]
        model = Model(self.model)
        agent = COTAgent(
            tools,
            model,
            SYSTEM_PROMPT,
            tool_choice="required",
            max_depth=self.max_iters,
            verbose=False,
            update_prompt=self._update_system_prompt,
        )
        messages = agent.run(prompt, self.history)

        output = messages[-1].raw_output
        if not was_tool_called(messages, "done"):
            messages = self.history + messages
            tool_call = agent.call_tool("done", messages)
            tool_result = agent.run_tool(tool_call, messages)
            output = tool_result.raw_output

        self.history += [Message.user(prompt), Message.assistant(output)]
        return output
