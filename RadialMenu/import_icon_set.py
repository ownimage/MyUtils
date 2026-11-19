"""Import/update an offline SVG set from a pinned package archive.

Manifests are the runtime interface; new sets require no picker code changes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
import xml.etree.ElementTree as ET

def install(archive, slug, label, source, prefix='package/assets/', *, assets_root=None):
    if not re.fullmatch(r'[a-z][a-z0-9-]*', slug):
        raise ValueError('Set ID must be a lowercase slug.')
    root = Path(assets_root or Path(__file__).resolve().parent/'assets')/slug
    with tarfile.open(archive) as package:
        metadata = json.load(package.extractfile('package/package.json'))
        license_data = package.extractfile('package/LICENSE').read()
        candidates = []
        for member in package.getmembers():
            if not member.isfile() or not member.name.startswith(prefix) or not member.name.endswith('.svg'):
                continue
            relative = PurePosixPath(member.name[len(prefix):])
            if len(relative.parts) != 2:
                continue
            style, filename = relative.parts
            name = filename[:-4]
            if name.endswith('-'+style):
                name = name[:-(len(style)+1)]
            if not all(re.fullmatch(r'[a-z0-9][a-z0-9-]*', part) for part in (style, name)):
                raise ValueError('Unexpected SVG path: '+member.name)
            data = package.extractfile(member).read()
            if ET.fromstring(data).tag.split('}')[-1] != 'svg':
                raise ValueError('Invalid SVG: '+member.name)
            candidates.append((dict(name=name,style=style,path=f'{style}/{name}.svg',tags=name.split('-')),data))
        if not candidates:
            raise ValueError('No SVGs found in the requested archive prefix.')
        identities = [item['path'] for item,_ in candidates]
        if len(identities) != len(set(identities)):
            raise ValueError('Duplicate set/style/name IDs in archive.')
        entries = [item for item,_ in candidates]
        manifest_path = root/'manifest.json'
        old = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
        current = set(identities)
        # Removed upstream icons remain resolvable for existing assignments.
        for entry in old.get('icons',[]):
            if entry['path'] not in current:
                entries.append(dict(entry, retired=True))
        manifest = dict(schema_version=1,id=slug,label=label,version=metadata['version'],
            source=source,sha256=hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
            icons=sorted(entries,key=lambda e:(e['name'],e['style'])))
        root.mkdir(parents=True,exist_ok=True)
        for item,data in candidates:
            path=root/item['path']
            path.parent.mkdir(parents=True,exist_ok=True)
            temporary=path.with_suffix('.svg.tmp')
            temporary.write_bytes(data)
            os.replace(temporary,path)
        (root/'LICENSE').write_bytes(license_data)
        (root/'SOURCE.md').write_text(f'# {label}\n\nVersion: {metadata["version"]}\nSource: {source}\nArchive SHA-256: {manifest["sha256"]}\n\nSVG contents are unmodified. Filenames normalise style suffixes.\nSee LICENSE for upstream copyright and licensing.\n',encoding='utf-8')
        temporary = root/'manifest.json.tmp'
        temporary.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        os.replace(temporary,manifest_path)
        return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',required=True)
    parser.add_argument('--set',dest='slug',required=True)
    parser.add_argument('--label',required=True)
    parser.add_argument('--source',required=True)
    parser.add_argument('--prefix',default='package/assets/')
    args=parser.parse_args()
    result=install(args.archive,args.slug,args.label,args.source,args.prefix)
    active=[e for e in result['icons'] if not e.get('retired')]
    print(f'{result["label"]} {result["version"]}: {len(active)} variants, {len(set(e["name"] for e in active))} names')
