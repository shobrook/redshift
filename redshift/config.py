# Standard library
import os
import argparse

DEFAULT_AGENT_MODEL = "anthropic/claude-sonnet-4-20250514"
DEFAULT_RESPONSE_MODEL = "anthropic/claude-sonnet-4-20250514"
DEFAULT_MAX_ITERS = 25
DEFAULT_HIDE_EXTERNAL_FRAMES = True


class Config:
    def __init__(
        self,
        agent_model: str = DEFAULT_AGENT_MODEL,
        response_model: str = DEFAULT_RESPONSE_MODEL,
        max_iters=DEFAULT_MAX_ITERS,
        hide_external_frames=DEFAULT_HIDE_EXTERNAL_FRAMES,
    ):
        self.agent_model = agent_model
        self.response_model = response_model
        self.max_iters = max_iters
        self.hide_external_frames = hide_external_frames

    @classmethod
    def from_args(cls):
        parser = argparse.ArgumentParser(
            description="An AI-powered debugger for Python."
        )
        parser.add_argument(
            "--agent-model",
            type=str,
            required=False,
            default=DEFAULT_AGENT_MODEL,
            help="LLM to use for tool calls made by the agent.",
        )
        parser.add_argument(
            "--response-model",
            type=str,
            required=False,
            default=DEFAULT_RESPONSE_MODEL,
            help="LLM to use for generating a response to your query.",
        )
        parser.add_argument(
            "--max-iters",
            type=int,
            required=False,
            default=DEFAULT_MAX_ITERS,
            help="Maximum number of iterations for the agent.",
        )
        parser.add_arguments(
            "--hide-external-frames",
            action="store_true",
            default=DEFAULT_HIDE_EXTERNAL_FRAMES,
            help="Hide frames from external modules in the debugger.",
        )
        args = parser.parse_args()

        return cls(
            agent_model=args.agent_model,
            response_model=args.response_model,
            max_iters=args.max_iters,
            hide_external_frames=args.hide_external_frames,
        )

    @classmethod
    def from_env(cls):
        return cls(
            agent_model=os.getenv("REDSHIFT_AGENT_MODEL", DEFAULT_AGENT_MODEL),
            response_model=os.getenv("REDSHIFT_RESPONSE_MODEL", DEFAULT_RESPONSE_MODEL),
            max_iters=int(os.getenv("REDSHIFT_MAX_ITERS", DEFAULT_MAX_ITERS)),
            hide_external_frames=os.getenv(
                "REDSHIFT_HIDE_EXTERNAL_FRAMES", str(DEFAULT_HIDE_EXTERNAL_FRAMES)
            )
            .strip()
            .lower()
            == "true",
        )
