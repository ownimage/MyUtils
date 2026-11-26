"""Shared native extension validation/building for tests and Build.cmd."""
import os
from pathlib import Path
import subprocess
import tomllib
import bpy


def extension_cli(command,stream):
    result=subprocess.run([bpy.app.binary_path,'--background','--factory-startup','--command','extension']+command,
                          capture_output=True,text=True,env=os.environ)
    stream.write(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError(f'Extension {command[0]} failed with exit code {result.returncode}')


def validate_source(root,stream):
    extension_cli(['validate',str(Path(root)/'snake_tape')],stream)


def build_extension(root,output,stream):
    root=Path(root)
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    manifest=tomllib.loads((root/'snake_tape/blender_manifest.toml').read_text(encoding='utf8'))
    archive=output/f"{manifest['id']}-{manifest['version']}.zip"
    validate_source(root,stream)
    extension_cli(['build','--source-dir',str(root/'snake_tape'),'--output-dir',str(output)],stream)
    extension_cli(['validate',str(archive)],stream)
    return archive
