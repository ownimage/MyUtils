"""All automated suites, packaging, and lightweight preview-pipeline validation."""
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tomllib
import unittest
import bpy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.dont_write_bytecode=True


class Tee:
    def __init__(self,*streams):
        self.streams=streams
    def write(self,text):
        for stream in self.streams:
            stream.write(text)
            stream.flush()
    def flush(self):
        for stream in self.streams:
            stream.flush()


def main():
    if bpy.app.version!=(4,4,3):
        raise RuntimeError(f'Blender 4.4.3 is required; found {bpy.app.version_string}')
    report=ROOT/'generated'/'tests'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    report.mkdir(parents=True)
    start=time.monotonic()
    with (report/'tests.log').open('w',encoding='utf8') as log:
        stream=Tee(sys.stdout,log)
        suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),top_level_dir=str(ROOT))
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        status={'blender':bpy.app.version_string,'tests':result.testsRun,'failures':len(result.failures),
                'errors':len(result.errors),'skipped':len(result.skipped),'elapsed_seconds':time.monotonic()-start,
                'manual_checks':'Installation, panel layout, selection workflow, undo/redo and artistic acceptance require real-window review.'}
        package=ROOT/'generated'/'packages'
        package.mkdir(parents=True,exist_ok=True)
        manifest=tomllib.loads((ROOT/'snake_tape'/'blender_manifest.toml').read_text(encoding='utf8'))
        extension_zip=package/f"{manifest['id']}-{manifest['version']}.zip"
        commands=[['validate',str(ROOT/'snake_tape')]]
        if result.wasSuccessful():
            commands += [['build','--source-dir',str(ROOT/'snake_tape'),'--output-dir',str(package)],
                         ['validate',str(extension_zip)]]
        for command in commands:
            output=subprocess.run([bpy.app.binary_path,'--background','--factory-startup','--command','extension']+command,capture_output=True,text=True,env=os.environ)
            stream.write(output.stdout+output.stderr)
            if output.returncode:
                status['packaging_error']=output.returncode
                break
        status['packaging_passed']=result.wasSuccessful() and not status.get('packaging_error')
        status['extension_zip']=str(extension_zip) if status['packaging_passed'] else None
        (report/'results.json').write_text(json.dumps(status,indent=2),encoding='utf8')
        stream.write(f'\nReports: {report}\nManual UI checks are not counted as automated passes.\n')
    if not result.wasSuccessful() or status.get('packaging_error'):
        raise RuntimeError('SnakeTape automated checks failed; see the report')


if __name__=='__main__':
    main()
