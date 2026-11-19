"""Run every app suite in a separate process to isolate Qt and test module names."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SUITES = ('Launch', 'Import', 'Yearbook', 'Slideshow', 'RadialMenu')


def main():
    failed = []
    for name in SUITES:
        folder = ROOT / name
        environment = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        environment['PYTHONPATH'] = os.pathsep.join((str(ROOT / 'Launch'), str(folder)))
        print(f'\nRunning {name} tests', flush=True)
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover',
                                 '-s', 'tests', '-v'], cwd=folder, env=environment)
        if result.returncode:
            failed.append(name)
    if failed:
        print('\nFailed suites: ' + ', '.join(failed), flush=True)
        return 1
    print('\nAll test suites passed.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
