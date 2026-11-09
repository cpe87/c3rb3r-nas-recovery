"""Collect the exact source and build materials for the bundled FFmpeg.

Usage: python collect_ffmpeg_source.py BUILD_DIRECTORY
No network access. Does not read NAS data or user credentials.
"""
import hashlib,io,json,pathlib,re,shutil,subprocess,sys,tarfile,zipfile
root=pathlib.Path(__file__).resolve().parents[1]
build=pathlib.Path(sys.argv[1]).resolve()
source=build/'FFmpeg-n9.0.2'
binary=source/'ffmpeg.exe'
flags={'creationflags':0x08000000} if sys.platform=='win32' else {}
def run(*args):
 return subprocess.run([str(binary),*args],check=True,capture_output=True,**flags).stdout.decode('utf-8',errors='replace')
version=run('-version');license_text=run('-L');protocols=run('-protocols')
decoders=run('-decoders');demuxers=run('-demuxers')
assert '--disable-gpl' in version and '--disable-version3' in version and '--disable-nonfree' in version
assert '--disable-autodetect' in version and '--disable-network' in version
assert 'Lesser General Public License' in license_text
config=(source/'config.h').read_text()
assert '#define CONFIG_GPL 0' in config and '#define CONFIG_NONFREE 0' in config
assert not re.findall(r'^#define CONFIG_LIB\w+ 1$',config,re.M),'External multimedia library enabled'
for component in ('NETWORK','ZLIB','BZLIB','ICONV','SCHANNEL','GNUTLS','OPENSSL','LZMA'):
 assert not re.search(r'^#define CONFIG_'+component+r' 1$',config,re.M),component
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
toolchain=build/'w64devkit-2.11.0-source.tar'
assert sha(toolchain)=='50ee43ca02b9ca49e0e16da7eaf9701c9a396a019ebb2416a93d16769d53e5ff'
compiler=build/'w64devkit-x64-2.11.0.7z.exe'
assert sha(compiler)=='54c2bb9962e8a30c8270e34c5efc3d5fee579f53087fa7d435b95fbba2af7b2b'
ffmpeg_archive=root/'packaging/downloads/ffmpeg-n9.0.2-source.tar.gz'
inputs={
 'FFmpeg-n9.0.2-source.tar.gz':ffmpeg_archive,
 'w64devkit-2.11.0-source.tar':toolchain,
 'w64devkit-v2.11.0-build-scripts.tar.gz':build/'w64devkit-v2.11.0-build-scripts.tar.gz',
 'build-ffmpeg.sh':build/'build-ffmpeg.sh',
 'config.h':source/'config.h',
 'config_components.h':source/'config_components.h',
}
readme='''Corresponding source for the FFmpeg executable bundled in NAS Recovery Public 0.1.2.

FFmpeg source is the unmodified n9.0.2 tag. Build configuration differs from
general-purpose distributions: no external multimedia libraries, no network,
no GPL/nonfree components; native decoders/demuxers, file/pipe protocols and
null output for local full-stream validation. Assembly optimizations requiring
NASM are disabled. This may decode slower than a general-purpose optimized build.

Rebuild on Windows x64:
1. Obtain w64devkit-x64-2.11.0.7z.exe from the exact URL in MANIFEST.json,
   verify its SHA-256, and extract it to a fresh directory.
2. Extract FFmpeg-n9.0.2-source.tar.gz. Put build-ffmpeg.sh next to that directory.
3. Prepend w64devkit/bin to PATH for this shell only. Set TMPDIR to a writable
   temporary directory if necessary. Enter FFmpeg-n9.0.2 and run:
       sh ../build-ffmpeg.sh
4. The output is ffmpeg.exe. Generated config headers and binary version,
   license, protocol and DLL import reports are included for comparison.
   Byte-identical builds are not promised; timestamps/toolchain environments
   may differ. Rebuilds can replace the separate _internal/tools/ffmpeg.exe.

FFmpeg is LGPL-2.1-or-later for this configuration. See FFmpeg-LICENSE.md and
COPYING.LGPLv2.1. No FFmpeg source files were edited. This software is based in
part on the work of the Independent JPEG Group; its referenced source files
are unchanged. Other notices remain in the original source archive.

The matching complete w64devkit source archive and build scripts are included,
including MinGW-w64 runtime and GCC sources. GNU runtime exceptions and MinGW
licenses apply to compiler runtime components, not FFmpeg's LGPL license.
General-purpose build tools need not be installed by application users.

Upstream locations:
https://github.com/FFmpeg/FFmpeg/tree/n9.0.2
https://github.com/skeeto/w64devkit/releases/tag/v2.11.0

This source archive is embedded in the installer under _internal/source.
Publish it separately alongside the installer as an additional convenience.
No warranty is provided. The program does not limit replacement, modification
or debugging of this independently invoked FFmpeg executable.
'''
objdump=build/'toolchain/w64devkit/bin/objdump.exe'
imports=subprocess.run([str(objdump),'-p',str(binary)],check=True,capture_output=True,**flags).stdout.decode(errors='replace')
dlls=[line.split(':',1)[1].strip() for line in imports.splitlines() if 'DLL Name:' in line]
assert all(x.lower() in {'kernel32.dll','msvcrt.dll','advapi32.dll','bcrypt.dll','user32.dll','shell32.dll','ws2_32.dll','ole32.dll','secur32.dll'} or x.lower().startswith('api-ms-win-') for x in dlls),dlls
manifest={'ffmpeg_version':'9.0.2','configuration_license':'LGPL-2.1-or-later','external_multimedia_libraries':[],
 'binary_sha256':sha(binary),'dll_imports':dlls,
 'source_files':{n:sha(p) for n,p in inputs.items()},
 'upstream_ffmpeg_source':'https://github.com/FFmpeg/FFmpeg/archive/refs/tags/n9.0.2.tar.gz',
 'compiler_binary_url':'https://github.com/skeeto/w64devkit/releases/download/v2.11.0/w64devkit-x64-2.11.0.7z.exe',
 'compiler_binary_sha256':sha(compiler),
 'compiler_source_url':'https://github.com/skeeto/w64devkit/releases/download/v2.11.0/source.tar',
 'compiler_build_scripts_url':'https://github.com/skeeto/w64devkit/archive/refs/tags/v2.11.0.tar.gz'}
lic=root/'THIRD_PARTY_LICENSES'
shutil.copyfile(source/'COPYING.LGPLv2.1',lic/'FFmpeg-LGPLv2.1.txt')
shutil.copyfile(source/'LICENSE.md',lic/'FFmpeg-LICENSE.md')
shutil.copyfile(build/'toolchain/w64devkit/COPYING.MinGW-w64-runtime.txt',lic/'MinGW-w64-runtime.txt')
with tarfile.open(toolchain) as outer:
 data=outer.extractfile('source/gcc-16.2.0.tar.xz').read()
 with tarfile.open(fileobj=io.BytesIO(data),mode='r:xz') as inner:
  for name in ('COPYING3','COPYING.RUNTIME'):
   member=next(x for x in inner.getmembers() if x.name.endswith('/'+name) and x.name.count('/')==1)
   (lic/('GCC-'+name+'.txt')).write_bytes(inner.extractfile(member).read())
archive=root/'packaging/FFmpeg-9.0.2-corresponding-source.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
 for n,p in inputs.items():z.write(p,n)
 for n,data in [('README.txt',readme),('MANIFEST.json',json.dumps(manifest,indent=2)),('VERSION.txt',version),('LICENSE.txt',license_text),('PROTOCOLS.txt',protocols),('DECODERS.txt',decoders),('DEMUXERS.txt',demuxers),('DLL-IMPORTS.txt','\n'.join(dlls))]:z.writestr(n,data)
 for n in ('FFmpeg-LGPLv2.1.txt','FFmpeg-LICENSE.md','MinGW-w64-runtime.txt','GCC-COPYING3.txt','GCC-COPYING.RUNTIME.txt'):z.write(lic/n,n)
(root/'packaging/FFmpeg-BUILD.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(lic/'FFmpeg-SOURCE.txt').write_text(readme,encoding='utf-8')
shutil.copyfile(binary,root/'tools/ffmpeg.exe')
(root/'release').mkdir(exist_ok=True)
shutil.copyfile(archive,root/'release'/archive.name)
print(json.dumps({'source_archive_bytes':archive.stat().st_size,'ffmpeg_sha256':sha(binary),'dlls':dlls},indent=2))
