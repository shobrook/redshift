# redshift

Redshift is a vibe debugger for Python. When a breakpoint is hit, you can ask questions about your program:

- "Why is this function returning null?"
- "How many items are in `array`?"
- "Which condition made the loop break?"
- "Why isn't training loss decreasing?"

An LLM agent will navigate the call stack, inspect variables, and look at your code to figure out an answer. Think of this as the Claude Code of debugging.

## Features

Redshift is an extension of Python's native debugger, [pdb.](https://docs.python.org/3/library/pdb.html) It supports all of pdb's commands, and introduces a few new commands:

_`ask PROMPT`_

Ask a question about the state of your program at a breakpoint or exception. An agent will autonomously operate the debugger to investigate and figure out an answer.

_`fix [PROMPT]`_

(Coming soon) If an exception is thrown, you can run this to find the root cause of the issue and propose a fix. The output will be a patch (diff) that you can auto-apply to your codebase. You may provide an optional prompt describing the issue.

_`run PROMPT`_

(Coming soon) Generates and executes code in the context of the current scope. Code will not be executed without your approval, and it'll run in an interpret whose global namespace is a copy of the variables defined at the current line of code.

## Installation

```bash
> pip install redshift-cli
```

After installing, you need an Anthropic API key. Get one [here,](https://console.anthropic.com/settings/keys) then add it to your environment:

```bash
> export OPENAI_API_KEY="..."
```

You can also use [OpenAI](https://platform.openai.com/api-keys) or other models, including local ones. Redshift wraps LiteLLM, so you can use any model [it supports.](https://docs.litellm.ai/docs/providers)

## Usage

You can set a breakpoint the same way you would in pdb:

```python
import redshift

def foo():
    # ...
    redshift.set_trace()
    # ...
```

You can also avoid the import by overriding the built-in `breakpoint` function:

```bash
export PYTHONBREAKPOINT=redshift.set_trace
```

Then you can do this:

```python
def foo():
    # ...
    breakpoint()
    # ...
```

<!-- You can also invoke Redshift from the command-line:

```bash
> redshift [-c command] (-m module | pyfile) [args ...]
```

Redshift will automatically enter post-mortem debugging if your program throws an exception. -->

## Configuration

You can set the following environment variables to configure Redshift:

**`REDSHIFT_AGENT_MODEL`**

This is the model that's used by the agent for tool-calling. Default is `"openai/gpt-4o"`. Use the [LiteLLM syntax](https://docs.litellm.ai/docs/providers) to specify the model (e.g. `"anthropic/claude-4"`).

**`REDSHIFT_ANSWER_MODEL`**

This is the model that's used to generate the final answer to your question, _after_ the agent has collected context. Default is `"openai/gpt-4o"`. Use the [LiteLLM syntax](https://docs.litellm.ai/docs/providers) to specify the model (e.g. `"anthropic/claude-4"`).

**`REDSHIFT_MAX_ITERS`**

Controls the number of tool calls the agent is allowed to make before generating a final answer. Default is `25`.

**`REDSHIFT_HIDE_EXTERNAL_FRAMES`**

If `True`, any frames in the stack trace that are from imported packaged rather than your codebase will be ignored by Redshift. If `False`, all frames will be treated equally. Default is `True`.
