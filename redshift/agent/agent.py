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
Your job is to answer user queries about the state of their program at that breakpoint. \
To do this, you will call tools to gather information that will help you answer the query.

<tool_calling>
You have tools that allow you to run pdb-like commands on the stopped program. \
Use them to navigate the call stack, inspect variable values, view source code, \
etc. to gather information that will help you answer the user's query. \
Once you have enough context, call the 'done' tool when you're ready to answer.
</tool_calling>

--

Below is some information about the user's program and the current state of your debugger:

<program_info>
This is the command the user ran to start their program:

<start_command>
{run_command}
</start_command>

This is the input (stdin) to the program, if any:

<input>
{input}
</input>
</program_info>

<debugger_info>
This is the stack trace, with the most recent frame at the bottom. \
An arrow (>) indicates the current frame, which determines the context of your tool calls:

<stack_trace>
{stack_trace}
</stack_trace>

This is the file associated with the current frame in the stack trace:

<current_file>
<path>{curr_file_path}</path>
<code>
{curr_file_code}
</code>
</current_file>
</debugger_info>

Use this information to call tools, steer the debugger, and answer the user's query."""


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


# TODO: Handle progress updates
class Agent:
    def __init__(self, pdb, model: str, max_iters: int):
        self.pdb = pdb
        self.model = model
        self.max_iters = max_iters
        self.history = []

    def _update_system_prompt(self):
        pass

    # TODO: Make synchronous
    async def run(self, prompt: str):
        tools = [
            MoveFrameTool(self.pdb),
            PrintExpressionTool(self.pdb),
            PrintArgsTool(self.pdb),
            PrintRetvalTool(self.pdb),
            ReadFileTool(self.pdb),
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
        )
        messages = await agent.run_async(prompt, self.history)

        output = messages[-1].raw_output
        if not was_tool_called(messages, "done"):
            # TODO: Check that history is included
            tool_call = await agent.call_tool("done", messages)
            tool_result = await agent.run_tool(tool_call, messages)
            output = tool_result.raw_output

        self.history += [Message.user(prompt), Message.assistant(output)]
        return output
