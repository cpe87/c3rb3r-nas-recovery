"""Experimental single-device Btrfs retained-extent reader. Source opens are read-only."""
import os,sys,json,stat,hashlib,time,struct
from functools import lru_cache
import btrfs_source as m
import retained_extents as p
VIDEO={'.mp4','.mov','.m4v','.mkv','.avi','.ts','.mts','.m2ts','.3gp','.wmv','.mpg','.mpeg','.lrf'}
PHOTO={'.jpg','.jpeg','.png','.gif','.webp','.bmp','.tif','.tiff','.heic','.heif','.dng','.nef','.cr2','.cr3','.arw'}
def emit(x):sys.stdout.buffer.write(json.dumps(x).encode()+b'\n');sys.stdout.buffer.flush()
def identity(fd):
 s=os.fstat(fd);return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
class Sink:
 def __init__(self,send=False):self.send=send
 def write(self,data):
  if self.send:sys.stdout.buffer.write(data)
  time.sleep(len(data)/(4<<20));return len(data)
def main():
 assert os.geteuid()==0,'administrator_required'
 base=os.path.dirname(os.path.realpath(__file__));assert base.startswith('/dev/shm/')
 cfg=json.load(open(base+'/job.json'))
 for name,digest in cfg['hashes'].items():assert hashlib.sha256(open(base+'/'+name,'rb').read()).hexdigest()==digest
 roots=cfg['roots'];assert roots and all(x.startswith('/volume') and os.path.normpath(x)==x and os.path.realpath(x)==x for x in roots)
 todo=list(roots);queue=[];seen=set();errors=[]
 while todo:
  directory=todo.pop()
  if directory in seen:continue
  seen.add(directory)
  try:
   assert os.path.realpath(directory)==directory
   fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_NOATIME)
   try:
    with os.scandir(fd) as entries:
     for e in entries:
      path=directory+'/'+e.name;s=e.stat(follow_symlinks=False)
      if stat.S_ISDIR(s.st_mode):
       if not e.name.startswith(('@','#','.')):todo.append(path)
      elif stat.S_ISREG(s.st_mode):
       encrypted=path.endswith('.L0CK3D');plain=path[:-7] if encrypted else path;ext=os.path.splitext(plain)[1].lower();kind='video' if ext in VIDEO else 'photo' if ext in PHOTO else 'other'
       if e.name.lower().startswith('read-me') and ext=='.txt':continue
       if kind in cfg['types']:queue.append(dict(path=path,size=s.st_size,inode=s.st_ino,mtime_ns=s.st_mtime_ns,kind=kind,encrypted=encrypted))
   finally:os.close(fd)
  except Exception as e:errors.append(dict(path=directory,error=str(e)))
 queue.sort(key=lambda x:({'video':0,'photo':1,'other':2}[x['kind']],x['size'],x['path']))
 discovered=len(queue)
 if cfg.get('pilot',True):queue=queue[:10]
 emit(dict(event='inventory',total=len(queue),discovered=discovered,pilot=cfg.get('pilot',True),errors=errors,files=queue))
 for index,r in enumerate(queue):
  if os.path.exists(base+'/STOP'):emit(dict(event='paused',processed=index));return
  emit(dict(event='working',path=r['path'],index=index));fd=None;vol=None;transmitting=False
  try:
   assert os.path.realpath(r['path'])==r['path']
   fd=os.open(r['path'],os.O_RDONLY|os.O_NOFOLLOW|os.O_NOATIME);ident=identity(fd)
   assert ident[1:4]==(r['inode'],r['size'],r['mtime_ns']),'source_identity_changed'
   assert 0<r['size']<=cfg.get('max_bytes',4<<30),'size_limit'
   def current(a,n):return os.pread(fd,n,a)
   if r['encrypted']:
    footer=current(r['size']-588,588);layout=p.parse_footer(footer,r['size'],footer[568:572].hex())
    dev=m.device_for(r['path']);assert dev,'not_btrfs';m.BLK,m.CSUM_TYPE=m.read_superblock(dev)
    assert m.BLK==4096 and m.CSUM_TYPE==0,'unsupported_sector_or_checksum'
    vol=m.Volume(dev);assert all(c[3]=='DATA' for c in vol.chunks) and len({c[4] for c in vol.chunks})==1,'only_single_device_DATA_profile_supported'
    items=m.extent_items(fd,ident[1]);plan=p.build_plan(layout['size'],layout['encrypted'],items);assert plan['status']=='candidate_complete','old_mapping_'+plan['status']
    for item in items:
     assert item['type']==1 and item.get('comp',0)==0,'unsupported_extent'
     for offset in {item['pos'],m.down(min(r['size'],item['pos']+item['num'])-1)}:
      count=min(4096,r['size']-offset)
      if count>0:assert vol.read(item['bytenr']+item['eoff']+offset-item['pos'],4096)[:count]==current(offset,count),'current_mapping_mismatch'
    @lru_cache(maxsize=65536)
    def checksum(a):
     raw=m.csum_of(fd,a);return int.from_bytes(raw,'little') if raw is not None else None
    def reconstruct(sink):return p.reconstruct(plan,current,vol.read,checksum,sink)
    proof={'device':dev,'layout':layout,'extents':items,'plan':plan}
   else:
    layout={'size':r['size']};proof={'plaintext_copy':True}
    def reconstruct(sink):
     h=hashlib.sha256()
     for a in range(0,r['size'],1<<20):
      data=current(a,min(1<<20,r['size']-a));assert len(data)==min(1<<20,r['size']-a);h.update(data);sink.write(data)
     return {'sha256':h.hexdigest()}
   before=reconstruct(Sink());assert identity(fd)==ident,'source_changed'
   if r['encrypted']:assert m.extent_items(fd,ident[1])==items
   emit(dict(event='file',file=r,bytes=layout['size'],sha256=before['sha256'],proof=proof));transmitting=True
   after=reconstruct(Sink(True));assert identity(fd)==ident and after['sha256']==before['sha256'],'source_changed'
   if r['encrypted']:assert m.extent_items(fd,ident[1])==items
   emit(dict(event='file_end',sha256=after['sha256']));transmitting=False
  except Exception as e:
   if transmitting:raise
   emit(dict(event='failed',file=r,error=str(e)))
  finally:
   if fd is not None:os.close(fd)
   if vol is not None:os.close(vol.fd)
 emit(dict(event='complete',processed=len(queue)))
if __name__=='__main__':main()
