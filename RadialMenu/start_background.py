"""Start standalone RadialMenu without retaining the calling console."""
from pathlib import Path
import subprocess
import sys


def main():
    script = Path(__file__).resolve().with_name('radial_gui.py')
    pythonw = script.parent.parent / 'venv' / 'Scripts' / 'pythonw.exe'
    try:
        subprocess.Popen(
            [str(pythonw), '-X', 'utf8', str(script), *sys.argv[1:]],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, close_fds=True,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    except OSError as error:
        print(f'Could not start RadialMenu: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
