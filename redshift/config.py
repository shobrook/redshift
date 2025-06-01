# Standard library
import os
import argparse

DEFAULT_MODEL = "gpt-4o"
DEFAULT_MAX_ITERS = 10
DEFAULT_HIDE_EXTERNAL_FRAMES = True


class Config:
    def __init__(
        self,
        model=DEFAULT_MODEL,
        max_iters=DEFAULT_MAX_ITERS,
        hide_external_frames=DEFAULT_HIDE_EXTERNAL_FRAMES,
    ):
        self.model = model
        self.max_iters = max_iters
        self.hide_external_frames = hide_external_frames

    @classmethod
    def from_args(cls):
        parser = argparse.ArgumentParser(
            description="An AI-powered debugger for Python."
        )
        parser.add_argument(
            "--model",
            type=str,
            required=False,
            default=DEFAULT_MODEL,
            help="LLM to use for AI interactions.",
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
            model=args.model,
            max_iters=args.max_iters,
            hide_external_frames=args.hide_external_frames,
        )

    @classmethod
    def from_env(cls):
        return cls(
            model=os.getenv("REDSHIFT_MODEL", DEFAULT_MODEL),
            max_iters=int(os.getenv("REDSHIFT_MAX_ITERS", DEFAULT_MAX_ITERS)),
            hide_external_frames=os.getenv(
                "REDSHIFT_HIDE_EXTERNAL_FRAMES", DEFAULT_HIDE_EXTERNAL_FRAMES
            )
            .strip()
            .lower()
            == "true",
        )
