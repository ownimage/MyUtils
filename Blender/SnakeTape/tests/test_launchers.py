import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import bpy


class LauncherTests(unittest.TestCase):
    def test_explicit_profile_paths_exist_and_are_used(self):
        for kind in ('CONFIG','EXTENSIONS','SCRIPTS','DATAFILES'):
            requested=os.environ.get('BLENDER_USER_'+kind)
            if requested:
                self.assertTrue(Path(requested).is_dir(),requested)
                self.assertEqual(Path(bpy.utils.user_resource(kind)).resolve(),Path(requested).resolve())

    @unittest.skipUnless(os.name=='nt','Windows batch launchers')
    def test_missing_override_reports_failure_without_hanging(self):
        root=Path(__file__).resolve().parents[1]
        for name in ('Run_Tests.cmd','Gen_Previews.cmd','Build.cmd'):
            env=os.environ.copy()
            env['SNAKETAPE_BLENDER']=str(root/'does not exist'/'blender.exe')
            with tempfile.TemporaryDirectory(prefix='SnakeTape working directory ') as cwd:
                result=subprocess.run(['cmd.exe','/d','/c',str(root/name),'--no-pause'],
                    cwd=cwd,env=env,capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,2,result.stdout+result.stderr)
            self.assertIn('SNAKETAPE_BLENDER',result.stdout)
