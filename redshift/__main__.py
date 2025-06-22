# Standard library
import sys
import pdb
import traceback

# Local
try:
    from redshift.config import Config
    from redshift.pdb import RedshiftPdb
except ImportError:
    from config import Config
    from .pdb import RedshiftPdb


_usage = """\
usage: redshift [-c command] ... [-m module | pyfile] [arg] ...

Debug the Python program given by pyfile. Alternatively,
an executable module or package to debug can be specified using
the -m switch.

Initial commands are read from .pdbrc files in your home directory
and in the current directory, if they exist.  Commands supplied with
-c are executed after commands from .pdbrc files.

To let the script run until an exception occurs, use "-c continue".
To let the script run up to a given line X in the debugged file, use
"-c 'until X'"."""


def main():
    import getopt

    opts, args = getopt.getopt(sys.argv[1:], "mhc:", ["help", "command="])

    if not args:
        print(_usage)
        sys.exit(2)

    if any(opt in ["-h", "--help"] for opt, optarg in opts):
        print(_usage)
        sys.exit()

    commands = [optarg for opt, optarg in opts if opt in ["-c", "--command"]]

    module_indicated = any(opt in ["-m"] for opt, optarg in opts)
    cls = pdb._ModuleTarget if module_indicated else pdb._ScriptTarget
    target = cls(args[0])

    target.check()

    sys.argv[:] = args  # Hide "redshift" and redshift options from argument list

    config = Config.from_args()
    pdb = RedshiftPdb(config=config)
    pdb.rcLines.extend(commands)
    while True:
        try:
            pdb._run(target)
            if pdb._user_requested_quit:
                break
            print("The program finished and will be restarted")
        except pdb.Restart:
            print("Restarting", target, "with arguments:")
            print("\t" + " ".join(sys.argv[1:]))
        except SystemExit as e:
            # In most cases SystemExit does not warrant a post-mortem session.
            print("The program exited via sys.exit(). Exit status:", end=" ")
            print(e)
        except SyntaxError:
            traceback.print_exc()
            sys.exit(1)
        except BaseException as e:
            traceback.print_exc()
            print("Uncaught exception. Entering post mortem debugging")
            print("Running 'cont' or 'step' will restart the program")
            t = e.__traceback__
            pdb.interaction(None, t)
            print("Post mortem debugger finished. The " + target + " will be restarted")


if __name__ == "__main__":
    main()
