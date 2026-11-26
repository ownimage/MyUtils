import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest
import zipfile
import bpy


class BuildTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','Windows build launcher')
    def test_build_cmd_builds_valid_archive_without_running_tests(self):
        root=Path(__file__).resolve().parents[1]
        env=os.environ.copy()
        env['SNAKETAPE_BLENDER']=bpy.app.binary_path
        manifest=tomllib.loads((root/'snake_tape/blender_manifest.toml').read_text(encoding='utf8'))
        with tempfile.TemporaryDirectory(prefix='SnakeTape build cwd ') as cwd:
            output=Path(cwd)/'built packages'
            result=subprocess.run(['cmd.exe','/d','/c',str(root/'Build.cmd'),'--no-pause','--output',str(output)],
                cwd=cwd,env=env,capture_output=True,text=True,timeout=90)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            package=output/f"{manifest['id']}-{manifest['version']}.zip"
            with zipfile.ZipFile(package) as archive:
                self.assertEqual(tomllib.loads(archive.read('blender_manifest.toml').decode())['version'],manifest['version'])
                self.assertIn('support.py',archive.namelist())
                self.assertFalse(any('tests/' in name or '__pycache__/' in name for name in archive.namelist()))
        self.assertNotIn('Ran ',result.stdout)
        reports=sorted((root/'generated/builds').iterdir())
        data=json.loads((reports[-1]/'results.json').read_text())
        self.assertTrue(data['packaging_passed'])
        self.assertFalse(data['tests_ran'])
