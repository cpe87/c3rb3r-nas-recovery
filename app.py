"""Public experimental desktop client. No credentials or case data are bundled."""
import base64,hashlib,json,os,pathlib,queue,re,shlex,shutil,subprocess,sys,threading,time,uuid
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
BASE=pathlib.Path(__file__).resolve().parent
VERSION='0.1.3'
def developer_information(language='中文'):
 profile=json.loads((BASE/'developer.json').read_text(encoding='utf-8'))
 chinese=language=='中文'
 lines=['NAS Recovery Public '+VERSION]
 for key,zh,en in [('name','作者 / 维护者','Author / Maintainer'),('homepage','开发者主页','Developer homepage'),('email','联系邮箱','Contact email'),('project_url','项目地址','Project URL')]:
  value=profile.get(key,'').strip()
  if value:lines.append((zh if chinese else en)+': '+value)
 if not profile.get('name','').strip():lines.append('开发者署名待设置' if chinese else 'Developer attribution pending')
 lines.extend(['','上游代码与组件：' if chinese else 'Upstream code and components:',
  'crt106/c3rb3r-btrfs-recovery — MIT',
  'https://github.com/crt106/c3rb3r-btrfs-recovery',
  'FFmpeg — LGPL-2.1-or-later (bundled configuration)',
  'Python / Tcl-Tk / Paramiko / Pillow',
  '',
  '各上游项目保留原版权。许可证和 FFmpeg 对应源码随安装包提供。' if chinese else 'Upstream copyrights are retained. Licenses and corresponding FFmpeg source are included.'])
 return '\n'.join(lines)
def default_ffmpeg():
 bundled=BASE/'tools'/'ffmpeg.exe'
 return str(bundled) if bundled.is_file() else (shutil.which('ffmpeg') or '')
TEXT={
'about':('关于 / 开发者','About / Developer'),
'title':('NAS 只读恢复 · 公用试用版','NAS Read-only Recovery · Experimental'),
'host':('NAS 地址','NAS host'),'port':('SSH 端口','SSH port'),'user':('用户名','Username'),'password':('密码（仅存内存）','Password (memory only)'),
'connect':('连接并核对指纹','Connect / verify fingerprint'),'browse':('读取目录','Read directory'),'add':('添加选中目录','Add selected directories'),
'count':('统计所选目录文件数量','Count files in selected directories'),
'dest':('选择独立输出盘文件夹','Choose independent destination'),'ffmpeg':('选择 FFmpeg 程序','Choose FFmpeg executable'),
'video':('视频','Videos'),'photo':('图片','Photos'),'other':('其他','Other'),
'start':('开始恢复','Start recovery'),'pause':('当前文件完成后暂停','Pause after current file'),
'independent':('我确认输出目录位于独立存储，不与受害存储池共用底层磁盘','I confirm the output storage is independent of the affected pool'),
'scope':('试用范围：兼容的 .L0CK3D 结构、单设备 Btrfs DATA single、4 KiB 扇区和 CRC32C。单文件上限 4 GiB；缺旧块或不支持的格式保留失败记录。目录统计排除隐藏系统目录和勒索说明。','Scope: compatible .L0CK3D structure, single-device Btrfs DATA single, 4 KiB sectors, CRC32C. 4 GiB file limit. Missing blocks/unsupported formats are recorded. Hidden system directories and ransom notes are excluded.'),
'ready':('就绪；恢复前先选少量样本验证','Ready; select a small sample before batch recovery'),
'pilot':('启用样本模式（最多处理 10 个文件）','Pilot mode (process at most 10 files)'),
'fingerprint':('首次连接，请与 NAS 管理员核对以下 SSH 指纹后确认','First connection: verify this SSH fingerprint with the NAS administrator'),
'complete':('本批处理完成','Batch processed'),'failed':('失败或待核验','Failed or needs review'),'validated':('格式校验通过','Format validated'),
'working':('正在处理','Processing'),'inventory':('清点目录中','Inventory in progress'),'error':('错误','Error'),
'review':('待核验','Review'),'paused':('已暂停','Paused'),'seconds':('视频秒数','Video seconds'),
'select':('每行一个 NAS 目录，需以 /volume 开头','One NAS directory per line, starting with /volume'),
'auth':('SSH 登录密码同时用于 sudo。账户必须具有管理员权限；不保存密码。','SSH password is also used for sudo. Administrator permissions are required; passwords are not saved.'),
}
def sha_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(4<<20),b''):h.update(b)
 return h.hexdigest()
def roots_checked(lines):
 out=[]
 for s in lines:
  s=s.strip().rstrip('/')
  if not s:continue
  if not re.match(r'^/volume\d+(?:/[^/]+)*$',s) or any(x in ('.','..') for x in s.split('/')) or '\\' in s or '\x00' in s:raise ValueError('Invalid NAS directory: '+s)
  if not any(s==r or s.startswith(r+'/') for r in out):out=[r for r in out if not r.startswith(s+'/')]+[s]
 if not out:raise ValueError('No directories selected')
 return out
def destination(root,source):
 parts=pathlib.PurePosixPath(source).parts[1:]
 if not parts or not re.fullmatch(r'volume\d+',parts[0]) or any(x in ('.','..') for x in parts):raise ValueError('Invalid source path')
 def safe(x):
  x=''.join('%%%02X'%ord(c) if c in '%<>:"/\\|?*' or ord(c)<32 else c for c in x)
  while x.endswith((' ','.')):x=x[:-1]+'%%%02X'%ord(x[-1])
  if re.match(r'^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\.|$)',x,re.I):x='%5F'+x
  return x if len(x)<=180 else x[:120]+'__'+hashlib.sha256(x.encode()).hexdigest()[:16]+pathlib.Path(x).suffix
 target=root.joinpath(*(safe(x) for x in parts));assert target.resolve().is_relative_to(root.resolve())
 for p in [target,*target.parents]:
  if p==root.parent:break
  if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):raise ValueError('Destination link is prohibited')
 return target
def validate(path,kind,ffmpeg):
 if kind=='photo':
  from PIL import Image
  with Image.open(path) as im:im.verify()
  with Image.open(path) as im:
   for n in range(getattr(im,'n_frames',1)):im.seek(n);im.load()
  return {'validation':'full_image_decode'}
 if kind=='video':
  if not pathlib.Path(ffmpeg).is_file():raise ValueError('FFmpeg executable required for video validation')
  flags={'creationflags':0x08000000} if os.name=='nt' else {}
  common=[ffmpeg,'-nostdin','-protocol_whitelist','file','-format_whitelist','mov,avi,matroska,webm,mpegts,mpeg,asf']
  meta=subprocess.run(common+['-i',str(path)],capture_output=True,timeout=60,**flags).stderr.decode(errors='replace')
  duration=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',meta);expected=sum(float(a)*b for a,b in zip(duration.groups(),[3600,60,1])) if duration else None
  r=subprocess.run([ffmpeg,'-nostdin','-v','error','-xerror','-err_detect','explode','-protocol_whitelist','file','-format_whitelist','mov,avi,matroska,webm,mpegts,mpeg,asf','-threads','2','-i',str(path),'-map','0:v?','-map','0:a?','-enc_time_base:v','demux','-fps_mode:v','passthrough','-progress','pipe:1','-f','null',os.devnull],capture_output=True,timeout=7200,**flags)
  data=dict(x.split('=',1) for x in r.stdout.decode(errors='replace').splitlines() if '=' in x);seconds=int(data.get('out_time_us',0))/1e6
  if r.returncode or r.stderr.strip() or int(data.get('frame',0))<=0 or expected is None or abs(seconds-expected)>max(1,expected*.01):raise ValueError('Full decode failed: '+r.stderr.decode(errors='replace')[:2000])
  return {'validation':'full_video_decode','seconds':seconds,'container_seconds':expected,'independent_original_verified':False}
 raise ValueError('No complete format validator for this file type')
class App:
 def __init__(self):
  self.ui=tk.Tk();self.lang=tk.StringVar(value='中文');self.widgets=[];self.client=None;self.secret='';self.remote=None;self.active=False;self.events=queue.Queue();self.pinned={}
  self.ui.geometry('1050x820');self.ui.protocol('WM_DELETE_WINDOW',self.close)
  header=ttk.Frame(self.ui);header.pack(fill='x',padx=10,pady=2);self.button(header,'about',self.about).pack(side='right')
  top=ttk.Frame(self.ui);top.pack(fill='x',padx=10,pady=8)
  lang=ttk.Combobox(top,textvariable=self.lang,values=['中文','English'],state='readonly',width=12);lang.pack(side='right');lang.bind('<<ComboboxSelected>>',lambda e:self.translate())
  self.fields={}
  for key,default in [('host',''),('port','22'),('user',''),('password','')]:
   self.label(top,key).pack(side='left');v=tk.StringVar(value=default);self.fields[key]=v;ttk.Entry(top,textvariable=v,width=18 if key!='port' else 5,show='*' if key=='password' else '').pack(side='left')
  self.button(self.ui,'connect',self.connect).pack(anchor='w',padx=10);self.label(self.ui,'auth').pack(anchor='w',padx=10)
  row=ttk.Frame(self.ui);row.pack(fill='x',padx=10,pady=5);self.path=tk.StringVar(value='/volume1');ttk.Entry(row,textvariable=self.path).pack(side='left',fill='x',expand=True);self.button(row,'browse',self.browse).pack(side='left')
  area=ttk.Frame(self.ui);area.pack(fill='both',expand=True,padx=10);self.tree=ttk.Treeview(area,show='tree',selectmode='extended');self.tree.pack(side='left',fill='both',expand=True);self.tree.bind('<Double-1>',self.enter)
  self.selected=tk.Text(area,width=62,height=10);self.selected.pack(side='right',fill='both',expand=True)
  self.button(self.ui,'add',self.add).pack(anchor='w',padx=10);self.button(self.ui,'count',self.count).pack(anchor='w',padx=10);self.label(self.ui,'select').pack(anchor='w',padx=10)
  row=ttk.Frame(self.ui);row.pack(fill='x',padx=10);self.types={}
  for key in ('video','photo','other'):
   v=tk.BooleanVar(value=key!='other');self.types[key]=v;w=ttk.Checkbutton(row,variable=v);self.widgets.append((w,key));w.pack(side='left',padx=8)
  self.output=tk.StringVar();self.ffmpeg=tk.StringVar(value=default_ffmpeg())
  for key,v in [('dest',self.output),('ffmpeg',self.ffmpeg)]:
   row=ttk.Frame(self.ui);row.pack(fill='x',padx=10,pady=4);ttk.Entry(row,textvariable=v).pack(side='left',fill='x',expand=True);self.button(row,key,lambda k=key,x=v:self.pick(k,x)).pack(side='right')
  self.independent=tk.BooleanVar();w=ttk.Checkbutton(self.ui,variable=self.independent);self.widgets.append((w,'independent'));w.pack(anchor='w',padx=10)
  self.pilot=tk.BooleanVar(value=True);w=ttk.Checkbutton(self.ui,variable=self.pilot);self.widgets.append((w,'pilot'));w.pack(anchor='w',padx=10)
  row=ttk.Frame(self.ui);row.pack(fill='x',padx=10,pady=8);self.button(row,'start',self.start).pack(side='left');self.button(row,'pause',self.pause).pack(side='left')
  self.progress=ttk.Progressbar(self.ui);self.progress.pack(fill='x',padx=10);self.status=tk.StringVar();ttk.Label(self.ui,textvariable=self.status,wraplength=1000).pack(fill='x',padx=10,pady=8)
  self.label(self.ui,'scope',wraplength=1000).pack(fill='x',padx=10,pady=8);self.translate();self.status.set(self.tr('ready'));self.ui.after(200,self.poll)
 def tr(self,k):return TEXT[k][0 if self.lang.get()=='中文' else 1]
 def about(self):
  messagebox.showinfo(self.tr('about'),developer_information(self.lang.get()))
 def label(self,parent,key,**kw):
  w=ttk.Label(parent,**kw);self.widgets.append((w,key));return w
 def button(self,parent,key,command):
  w=ttk.Button(parent,command=command);self.widgets.append((w,key));return w
 def translate(self):
  self.ui.title(self.tr('title'))
  for w,k in self.widgets:w.configure(text=self.tr(k))
 def pick(self,key,var):
  p=filedialog.askdirectory() if key=='dest' else filedialog.askopenfilename()
  if p:var.set(p)
 def connect(self):
  if self.active:return
  try:
   import paramiko
   host=self.fields['host'].get().strip();port=int(self.fields['port'].get());user=self.fields['user'].get().strip();password=self.fields['password'].get()
   assert host and user and 0<port<65536
   app=self
   class Policy(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self,client,hostname,key):
     fp='SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=');known=app.pinned.get((host,port))
     if known and known!=fp:raise ValueError('SSH host key changed')
     if not known and not messagebox.askyesno(app.tr('connect'),app.tr('fingerprint')+'\n'+host+'\n'+fp):raise ValueError('Host key not approved')
     app.pinned[(host,port)]=fp
   c=paramiko.SSHClient();c.set_missing_host_key_policy(Policy());c.connect(host,port=port,username=user,password=password,look_for_keys=False,allow_agent=False,timeout=10,auth_timeout=20)
   if self.client:self.client.close()
   self.client=c;self.secret=password;self.fields['password'].set('');self.status.set('SSH OK');self.browse()
  except Exception as e:messagebox.showerror(self.tr('error'),str(e))
 def execute(self,command,admin=False):
  if not self.client:raise ValueError('Connect first')
  stdin,stdout,stderr=self.client.exec_command(('sudo -S -p "" ' if admin else '')+command,timeout=90)
  if admin:stdin.write(self.secret+'\n');stdin.flush()
  return stdin,stdout,stderr
 def browse(self):
  if self.active:return
  try:
   p=self.path.get().strip().rstrip('/');roots_checked([p])
   code="import os,json,stat; p="+repr(p)+"; assert os.path.realpath(p)==p; fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_NOATIME); rows=[]\nwith os.scandir(fd) as it:\n for e in it:\n  if e.is_dir(follow_symlinks=False) and not e.name.startswith(('@','#','.')):rows.append(p+'/'+e.name)\nos.close(fd);print(json.dumps(sorted(rows)))"
   command='python3 -I -B -c '+shlex.quote(code);_,out,err=self.execute(command,True);raw=out.read();error=err.read().decode(errors='replace')
   if out.channel.recv_exit_status()!=0:raise ValueError(error)
   self.tree.delete(*self.tree.get_children())
   for path in json.loads(raw):self.tree.insert('','end',iid=path,text=path)
  except Exception as e:messagebox.showerror(self.tr('error'),str(e))
 def enter(self,event):
  p=self.tree.focus()
  if p:self.path.set(p);self.browse()
 def add(self):
  paths=list(self.tree.selection()) or [self.path.get()]
  for p in paths:self.selected.insert('end',p+'\n')
 def count(self):
  if self.active:return
  try:
   roots=roots_checked(self.selected.get('1.0','end').splitlines());assert self.client,'Connect first'
  except Exception as e:messagebox.showerror(self.tr('error'),str(e));return
  self.status.set(self.tr('inventory'))
  def work():
   try:
    code="import os,json,stat;stack="+repr(roots)+";seen=set();counts={};errors=[]\nwhile stack:\n p=stack.pop()\n if p in seen:continue\n seen.add(p)\n try:\n  assert os.path.realpath(p)==p\n  fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_NOATIME)\n  try:\n   with os.scandir(fd) as it:\n    for e in it:\n     s=e.stat(follow_symlinks=False)\n     if stat.S_ISDIR(s.st_mode):\n      if not e.name.startswith(('@','#','.')):stack.append(p+'/'+e.name)\n     elif stat.S_ISREG(s.st_mode):\n      name=e.name[:-7] if e.name.endswith('.L0CK3D') else e.name\n      ext=os.path.splitext(name)[1].lower()\n      if name.lower().startswith('read-me') and ext=='.txt':continue\n      root=next(r for r in "+repr(roots)+" if p==r or p.startswith(r+'/'))\n      c=counts.setdefault(root,{'files':0,'bytes':0});c['files']+=1;c['bytes']+=s.st_size\n  finally:os.close(fd)\n except Exception as e:errors.append({'path':p,'error':str(e)})\nprint(json.dumps({'counts':counts,'errors':errors}))"
    _,out,err=self.execute('python3 -I -B -c '+shlex.quote(code),True);raw=out.read();error=err.read().decode(errors='replace')
    if out.channel.recv_exit_status()!=0:raise ValueError(error)
    r=json.loads(raw);text='\n'.join(p+' — '+str(c['files'])+' files · '+str(round(c['bytes']/1e9,2))+' GB' for p,c in r['counts'].items());self.events.put(('path',text+'\n'+json.dumps(r['errors'],ensure_ascii=False)))
   except Exception as e:self.events.put(('error',str(e)))
  threading.Thread(target=work,daemon=True).start()
 def start(self):
  if self.active:return
  try:
   if not self.client:raise ValueError('Connect first')
   roots=roots_checked(self.selected.get('1.0','end').splitlines());types=[k for k,v in self.types.items() if v.get()];assert types,'Select file types'
   root=pathlib.Path(self.output.get()).resolve();assert self.output.get() and root.is_dir() and self.independent.get(),'Confirm independent output storage'
   if str(root).startswith('\\\\'):raise ValueError('Network destinations not supported')
   for p in [root,*root.parents]:
    if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):raise ValueError('Destination link prohibited')
   assert shutil.disk_usage(root).free>20<<30,'20 GiB free reserve required'
   if 'video' in types and not pathlib.Path(self.ffmpeg.get()).is_file():raise ValueError('Select FFmpeg executable')
   job={'roots':roots,'types':types,'pilot':self.pilot.get(),'max_bytes':4<<30};ff=self.ffmpeg.get();self.active=True;self.status.set(self.tr('inventory'));threading.Thread(target=self.run,args=(root,job,ff),daemon=True).start()
  except Exception as e:messagebox.showerror(self.tr('error'),str(e))
 def pause(self):
  if self.active and self.remote:
   try:self.execute('touch '+shlex.quote(self.remote+'/STOP'))
   except Exception as e:messagebox.showerror(self.tr('error'),str(e))
 def run(self,root,job,ff):
  run='recovery-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8];logs=root/'_recovery_records'/run;logs.mkdir(parents=True,exist_ok=False)
  processed=good=review=failed=0;total=0;seconds=0;state='running';receipt=None
  try:
   self.remote='/dev/shm/'+run;sftp=self.client.open_sftp();sftp.mkdir(self.remote,0o700);job['hashes']={}
   for p in (BASE/'engine').glob('*.py'):
    raw=p.read_bytes();job['hashes'][p.name]=hashlib.sha256(raw).hexdigest()
    with sftp.open(self.remote+'/'+p.name,'wb') as f:f.write(raw)
    sftp.chmod(self.remote+'/'+p.name,0o600)
   with sftp.open(self.remote+'/job.json','w') as f:f.write(json.dumps(job))
   sftp.chmod(self.remote+'/job.json',0o600);sftp.close();(logs/'job.json').write_text(json.dumps(job,indent=2),encoding='utf-8')
   _,out,err=self.execute('python3 -B '+shlex.quote(self.remote+'/worker.py'),True);out.channel.settimeout(None)
   def stderr_reader():
    with (logs/'remote-errors.txt').open('wb') as f:
     while True:
      chunk=err.read(4096)
      if not chunk:break
      f.write(chunk);f.flush()
   threading.Thread(target=stderr_reader,daemon=True).start();receipt=(logs/'files.jsonl').open('a',encoding='utf-8')
   while True:
    line=out.readline(32<<20)
    if not line:raise EOFError('Remote stream ended before completion')
    event=json.loads(line);kind=event['event']
    if kind=='inventory':
     total=event['total'];(logs/'inventory.json').write_text(json.dumps(event,indent=2),encoding='utf-8')
    elif kind=='working':self.events.put(('path',event['path']))
    elif kind=='failed':
     failed+=1;processed+=1;receipt.write(json.dumps(event)+'\n');receipt.flush()
    elif kind=='file':
     r=event['file'];n=event['bytes'];assert 0<n<=4<<30
     assert any(r['path'].startswith(p+'/') for p in job['roots']),'Unexpected source path'
     if shutil.disk_usage(root).free<n+(20<<30):raise RuntimeError('Output space reserve reached')
     candidate=logs/(uuid.uuid4().hex+'.part');h=hashlib.sha256();remaining=n
     with candidate.open('xb') as f:
      while remaining:
       chunk=out.read(min(1<<20,remaining))
       if not chunk:raise EOFError('Interrupted payload; partial retained')
       f.write(chunk);h.update(chunk);remaining-=len(chunk)
     end=json.loads(out.readline(65536));assert end['event']=='file_end' and end['sha256']==event['sha256']==h.hexdigest();assert sha_file(candidate)==h.hexdigest()
     event['candidate']=str(candidate)
     try:event['validation']=validate(candidate,r['kind'],ff);state_file='format_validated';good+=1;seconds+=event['validation'].get('seconds',0)
     except Exception as e:event['validation_error']=str(e);state_file='needs_review';review+=1
     original=r['path'][:-7] if r['encrypted'] else r['path'];target=destination(root,original);suffix='__needs_review' if state_file=='needs_review' else '__duration_unverified' if r['kind']=='video' else '';target=target.with_name(target.stem+suffix+target.suffix);target.parent.mkdir(parents=True,exist_ok=True)
     if target.exists():
      if sha_file(target)!=h.hexdigest():target=target.with_name(target.stem+'__'+h.hexdigest()[:12]+target.suffix)
     if not target.exists():
      with candidate.open('rb') as src,target.open('xb') as dest:shutil.copyfileobj(src,dest,4<<20)
     assert sha_file(target)==h.hexdigest();event.update(status=state_file,destination=str(target));receipt.write(json.dumps(event)+'\n');receipt.flush();processed+=1
    elif kind in ('complete','paused'):state=kind;break
    summary=dict(state=state,processed=processed,total=total,validated=good,review=review,failed=failed,seconds=seconds,updated=time.time());(logs/'progress.json').write_text(json.dumps(summary),encoding='utf-8');self.events.put(('stats',summary))
  except Exception as e:state='error';self.events.put(('error',str(e)));(logs/'error.txt').write_text(str(e),encoding='utf-8')
  finally:
   if receipt:receipt.close()
   summary=dict(state=state,processed=processed,total=total,validated=good,review=review,failed=failed,seconds=seconds,updated=time.time());(logs/'progress.json').write_text(json.dumps(summary),encoding='utf-8');self.events.put(('stats',summary));self.active=False
 def poll(self):
  while not self.events.empty():
   kind,data=self.events.get()
   if kind in ('error','path'):self.status.set(str(data))
   else:
    n=data['processed'];total=data['total'];pct=n*100/total if total else 100 if data['state']=='complete' else 0;self.progress.configure(maximum=max(1,total),value=n);label=self.tr('complete') if data['state']=='complete' else self.tr('working') if data['state']=='running' else self.tr(data['state']);self.status.set(f'{label} · {pct:.1f}% · {n}/{total}\n{self.tr("validated")}: {data["validated"]} · {self.tr("review")}: {data["review"]} · {self.tr("failed")}: {data["failed"]} · {self.tr("seconds")}: {data["seconds"]:.1f}s')
  self.ui.after(300,self.poll)
 def close(self):
  if self.active:
   messagebox.showinfo(self.tr('pause'),self.tr('pause'));self.pause();return
  self.secret=''
  if self.client:self.client.close()
  self.ui.destroy()
def packaging_self_test(output):
 import paramiko
 import zipfile
 from PIL import Image
 a=App();a.ui.update()
 assert not a.fields['host'].get() and not a.fields['user'].get() and not a.fields['password'].get()
 for language in ('English','中文'):
  a.lang.set(language);a.translate();a.ui.update();assert a.ui.title()==a.tr('title')
  profile=json.loads((BASE/'developer.json').read_text(encoding='utf-8'))
  assert profile['name'] and profile['name'] in developer_information(language)
 for name in ('worker.py','btrfs_source.py','retained_extents.py'):assert (BASE/'engine'/name).is_file()
 result=subprocess.run([default_ffmpeg(),'-version'],capture_output=True,timeout=30,creationflags=0x08000000)
 assert result.returncode==0
 source_bundle=BASE/'source'/'FFmpeg-9.0.2-corresponding-source.zip'
 with zipfile.ZipFile(source_bundle) as z:
  manifest=json.loads(z.read('MANIFEST.json'))
  assert manifest['binary_sha256']==sha_file(pathlib.Path(default_ffmpeg()))
  assert {'FFmpeg-n9.0.2-source.tar.gz','w64devkit-2.11.0-source.tar','build-ffmpeg.sh'}.issubset(z.namelist())
 report={'version':VERSION,'frozen':bool(getattr(sys,'frozen',False)),'gui_languages':['English','中文'],'credentials_blank':True,'engine_present':True,'ffmpeg':result.stdout.decode(errors='replace').splitlines()[0],'corresponding_source_embedded':True,'ffmpeg_matches_source_manifest':True,'nas_connected':False}
 report['author']=profile['name'];report['about_languages_verified']=True
 pathlib.Path(output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');a.ui.destroy()
if __name__=='__main__':
 if len(sys.argv)==3 and sys.argv[1]=='--self-test':packaging_self_test(sys.argv[2])
 else:App().ui.mainloop()
