"""Build and validate the installable ZIP without running the test suite."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import bpy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.dont_write_bytecode=True
from tools.packaging import build_extension


class Tee:
    def __init__(self,log):self.log=log
    def write(self,text):
        sys.stdout.write(text);sys.stdout.flush()
        self.log.write(text);self.log.flush()


def main():
    if bpy.app.version!=(4,4,3):
        raise RuntimeError(f'Blender 4.4.3 is required; found {bpy.app.version_string}')
    parser=argparse.ArgumentParser()
    parser.add_argument('--no-pause',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'generated/packages')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    report=ROOT/'generated/builds'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    report.mkdir(parents=True)
    status={'blender':bpy.app.version_string,'tests_ran':False,'packaging_passed':False}
    try:
        with (report/'build.log').open('w',encoding='utf8') as log:
            stream=Tee(log)
            stream.write('SnakeTape build only: validate source, build ZIP, validate ZIP.\n')
            archive=build_extension(ROOT,args.output,stream)
            status.update(packaging_passed=True,extension_zip=str(archive))
            stream.write(f'\nPackage: {archive}\nBuild report: {report}\n')
    except Exception as error:
        status['error']=str(error)
        raise
    finally:
        (report/'results.json').write_text(json.dumps(status,indent=2),encoding='utf8')


if __name__=='__main__':main()
