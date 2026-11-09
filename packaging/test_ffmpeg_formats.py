"""Generate synthetic fixtures with a reference FFmpeg, validate with our build.
Usage: python test_ffmpeg_formats.py REFERENCE_FFMPEG CANDIDATE_FFMPEG
Only synthetic files under packaging/media-compatibility are written.
"""
import json,pathlib,subprocess,sys
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import app
reference,candidate=sys.argv[1:3]
out=root/'packaging/media-compatibility';out.mkdir(exist_ok=True)
cases=[
 ('h264-aac.mp4',['-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-c:a','aac']),
 ('hevc10-aac.mp4',['-c:v','libx265','-preset','ultrafast','-pix_fmt','yuv420p10le','-x265-params','pools=2:frame-threads=2:log-level=error','-c:a','aac']),
 ('mjpeg-pcm.mov',['-c:v','mjpeg','-pix_fmt','yuvj420p','-c:a','pcm_s16le']),
 ('mpeg4-mp3.avi',['-c:v','mpeg4','-c:a','libmp3lame']),
 ('vp9-opus.mkv',['-c:v','libvpx-vp9','-deadline','realtime','-cpu-used','8','-c:a','libopus']),
 ('h264-aac.ts',['-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-c:a','aac']),
]
results=[]
for name,options in cases:
 path=out/name
 if not path.exists():
  r=subprocess.run([reference,'-nostdin','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=10','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','2','-threads','2',*options,str(path)],capture_output=True,timeout=120,creationflags=0x08000000)
  assert r.returncode==0,r.stderr.decode(errors='replace')
 v=app.validate(path,'video',candidate);assert 1.8<=v['seconds']<=2.3,v
 results.append({'file':name,**v})
bad=out/'invalid.mp4';bad.write_bytes(b'not a video')
try:app.validate(bad,'video',candidate)
except ValueError:pass
else:raise AssertionError('Invalid media accepted')
report={'synthetic_only':True,'cases':results,'invalid_media_rejected':True,'nas_accessed':False}
(out/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
