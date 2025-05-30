# redshift

Redshift is an AI-powered breakpoint for Python. When it's hit, you can ask questions about your program:

- "..."
- "..."
- "..."

An agent will navigate the call stack, examine variable values, and inspect source code to answer your question. Think of this as a chat-based debugger.

Redshift has all the same features as `pdb` and is designed to be a drop-in replacement, with three additional features:

- `ask`: Ask a question about the state of your program
- `why`: Find the root cause of an exception and propose a fix
- `run`: Generate and execute code in the context of the program

## Installation

```bash
> pip install redshift-py
```

After installing, you need an OpenAI API key. Get one [here,]() then add it to your environment:

```bash
> export OPENAI_API_KEY="..."
```

You can also use other models, including local ones. Redshift wraps LiteLLM, so you can use any model listed [here.](https://docs.litellm.ai/docs/providers)

## Usage

Adding a breakpoint to your code is easy:

```python
from redshift import breakpoint

x = 10
breakpoint()
y = x * 2
```

When hit, you'll be prompted to enter a command. You can submit any `pdb` command (e.g. `up`, `down`, `p`, etc.), or a redshift command: `ask`, `why`, and `run`.
