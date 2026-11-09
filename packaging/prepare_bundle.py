"""Prepare explicit public build inputs; never copies credentials or recovery outputs."""
import hashlib,importlib.metadata as md,json,pathlib,shutil,sys,zipfile
root=pathlib.Path(__file__).resolve().parents[1]
licenses=root/'THIRD_PARTY_LICENSES'
packages=['paramiko','Pillow','bcrypt','cryptography','invoke','PyNaCl','cffi','pycparser','pyinstaller']
versions={}
for name in packages:
 d=md.distribution(name);versions[name]=d.version
 for f in d.files or []:
  if '.dist-info/' in str(f).replace('\\','/') and any(w in f.name.lower() for w in ('license','copying','notice')):
   target=licenses/name/f.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(d.locate_file(f),target)
shutil.copyfile(pathlib.Path(sys.base_prefix)/'LICENSE.txt',licenses/'Python-LICENSE.txt')
for name in ('tcl8.6','tk8.6'):
 for p in (pathlib.Path(sys.base_prefix)/'tcl'/name).glob('*license*'):
  shutil.copyfile(p,licenses/(name+'-'+p.name))
(root/'packaging'/'BUILD-VERSIONS.json').write_text(json.dumps({'python':sys.version.split()[0],**versions},indent=2),encoding='utf-8')
names=['app.py','developer.json','requirements.txt','setup.cmd','setup.ps1','start.cmd','README.md','LICENSE','test_local.py']
names += [str(p.relative_to(root)).replace('\\','/') for p in (root/'engine').glob('*.py')]
names += [str(p.relative_to(root)).replace('\\','/') for p in (root/'packaging').iterdir() if p.is_file() and (p.suffix in ('.py','.ps1','.iss','.txt') or p.name in ('BUILD-VERSIONS.json','FFmpeg-BUILD.json'))]
names += [str(p.relative_to(root)).replace('\\','/') for p in licenses.rglob('*') if p.is_file()]
manifest={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in sorted(names)}
(root/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(root/'release').mkdir(exist_ok=True)
with zipfile.ZipFile(root/'release'/'NAS-Recovery-Public-0.1.3-source.zip','w',zipfile.ZIP_DEFLATED) as z:
 for n in names+['SOURCE_MANIFEST.json']:z.write(root/n,'NAS-Recovery-Public/'+n)
print('Public source and license bundle prepared')
