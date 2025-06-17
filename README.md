# redshift

Redshift is a vibe debugger for Python. When a breakpoint is hit, you can ask questions like:

- "Why is this function returning null?"
- "How many items are in `array`?"
- "Which condition made the loop break?"
- "Why isn't training loss decreasing?"

An agent will navigate the call stack, inspect variables, and look at your code to figure out an answer. Think of this as Claude Code but for debugging.

![Demo](./demo.gif)

## Features

Redshift is an extension of Python's native debugger, [pdb](https://docs.python.org/3/library/pdb.html). It can do everything pdb does, plus a few new commands:

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
> export ANTHROPIC_API_KEY="..."
```

You can also use [OpenAI](https://platform.openai.com/api-keys) or other models, including local ones. Redshift wraps LiteLLM, which [supports over 100 models.](https://docs.litellm.ai/docs/providers)

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

You can set some environment variables to customize Redshift:

**`REDSHIFT_AGENT_MODEL`**

LLM that's used by the agent for tool-calling. Default is `"anthropic/claude-sonnet-4-20250514"`. Use the [LiteLLM names](https://docs.litellm.ai/docs/providers) to identify the model (e.g. `"openai/gpt-4o"`).

**`REDSHIFT_RESPONSE_MODEL`**

LLM that's used to generate the final response. This is used _after_ the agent has collected context. Default is `"anthropic/claude-sonnet-4-20250514"`.

**`REDSHIFT_MAX_ITERS`**

Number of tool calls the agent is allowed to make before generating a response. Default is `25`.

**`REDSHIFT_HIDE_EXTERNAL_FRAMES`**

Toggles whether or not stack frames from external libraries are ignored by Redshift. Default is `True`, which means Redshift only cares about the frames in your codebase.
