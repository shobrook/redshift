# Standard library
import os
import sys
import site
import sysconfig
from pathlib import Path


#########
# HELPERS
#########


def is_system_file(filename: str) -> bool:
    # Resolve symlinks
    real_sys_prefix = os.path.realpath(sys.prefix)
    real_python_path = os.path.realpath(sys.executable)
    real_stdlib_path = os.path.join(os.path.dirname(real_python_path), "..", "lib")

    # Should cover most cases
    for sys_path in sysconfig.get_paths().values():
        real_sys_path = os.path.realpath(sys_path)
        if filename.startswith(sys_path) or filename.startswith(real_sys_path):
            return True

    # Fallback: Python internal files (e.g. <frozen> or <string>)
    if Path(filename).name.startswith("<") or filename.startswith("<"):
        return True

    # Fallback: Python stdlib files
    if (
        filename.startswith(sys.prefix)
        or filename.startswith(real_sys_prefix)
        or filename.startswith(real_stdlib_path)
    ):
        return True

    # Fallback: Python executable
    if filename.startswith(sys.executable) or filename.startswith(real_python_path):
        return True

    return False


def is_third_party_file(filename: str) -> bool:
    for packages_dir in site.getsitepackages():
        if filename.startswith(packages_dir):
            return True

    return False


######
# MAIN
######


def is_project_file(filename: str) -> bool:
    # Resolve symlink
    real_filename = os.path.realpath(filename)

    # Skip Python system files
    if is_system_file(filename) or is_system_file(real_filename):
        return False

    # Skip third-party packages
    if is_third_party_file(filename) or is_third_party_file(real_filename):
        return False

    return True
