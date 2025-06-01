# Standard library
import pdb
import sys

# Local
try:
    from redshift.agent import Agent
    from redshift.config import Config
except ImportError:
    from agent import Agent
    from config import Config


#########
# HELPERS
#########


def build_query_prompt() -> str:
    pass


def build_exception_prompt() -> str:
    pass


class PdbWrapper(pdb.Pdb):
    def __init__(self, config: Config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prompt = "(redshift) "
        self.config = config
        self.agent = Agent(self, config.model, config.max_iters)

    ## Helpers ##

    def _restore_state(self):
        self.curindex = self._original_curindex
        self.curframe = self.stack[self.curindex][0]
        self.curframe_locals = self.curframe.f_locals
        self.set_convenience_variable(self.curframe, "_frame", self.curframe)
        self.lineno = self._original_lineno

    ## Overloads ##

    def interaction(self, frame, traceback):
        super().interaction(frame, traceback)

        # Used to restore state after running agent
        self._original_curindex = self.curindex
        self._original_lineno = self.lineno

    ## New commands ##

    def do_ask(self, arg: str):
        query = arg.strip()

        # Build the prompt for the agent:
        # - Breakpoint (file, code, etc.)
        # - Previous debugger commands

        prompt = build_query_prompt(query)
        output = self.agent.run(prompt)

        self._restore_state()

    def do_why(self):
        prompt = build_exception_prompt()  # Error message, enriched stack trace, etc.
        output = self.agent.run(prompt)

        self._restore_state()

    def do_run(self, arg: str):
        # Generates and executes code within the program context
        pass


######
# MAIN
######


def set_trace():
    pass


def post_mortem():
    pass


async def main(file_path: str, args: list[str], is_module: bool = False):
    custom_pdb = CustomPdb()

    while 1:
        try:
            if hasattr(pdb.Pdb, "_run"):
                # User is on Python >=3.11
                if is_module:
                    custom_pdb._run(pdb._ModuleTarget(file_path))
                else:
                    custom_pdb._run(pdb._ScriptTarget(file_path))
            else:
                if is_module:
                    custom_pdb._runmodule(file_path)
                else:
                    custom_pdb._runscript(file_path)

            if custom_pdb._user_requested_quit:
                break
        except Restart:
            print(f"Restarting {file_path} with arguments:\n\t" + " ".join(args))
        except SystemExit:
            pass
        except:
            traceback.print_exc()
            print("Uncaught exception. Entering post mortem debugging")
            print("Running 'cont' or 'step' will restart the program")
            t = sys.exc_info()[2]
            pdb.interaction(None, t)
            print(
                "Post mortem debugger finished. The "
                + mainpyfile
                + " will be restarted"
            )
