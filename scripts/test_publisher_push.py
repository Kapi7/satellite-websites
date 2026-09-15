import subprocess,tempfile,pathlib
helper=pathlib.Path(__file__).with_name('push-publisher.sh').resolve()
def run(args,cwd,ok=True):
 r=subprocess.run(args,cwd=cwd,capture_output=True,text=True)
 if ok and r.returncode:raise RuntimeError(r.stderr)
 return r
with tempfile.TemporaryDirectory() as d:
 p=pathlib.Path(d);run(['git','init','--bare','--initial-branch=main','remote'],p)
 for name in ['a','b']:
  run(['git','clone',str(p/'remote'),name],p)
  for key,value in [('user.name','Test'),('user.email','test@example.invalid')]:run(['git','config',key,value],p/name)
 a=p/'a';b=p/'b';(a/'base').write_text('base\n');run(['git','add','.'],a);run(['git','commit','-m','base'],a);run(['git','push','origin','main'],a);run(['git','pull'],b)
 (a/'remote-change').write_text('remote\n');run(['git','add','.'],a);run(['git','commit','-m','remote'],a);run(['git','push'],a)
 (b/'article').write_text('article\n');run(['git','add','.'],b);run(['git','commit','-m','article'],b);(b/'base').write_text('uncommitted build result\n')
 run(['bash',str(helper)],b)
 assert (b/'base').read_text()=='uncommitted build result\n' and (b/'remote-change').exists()
 run(['git','pull'],a);assert (a/'article').exists()
 # Conflicting committed edits must fail without force pushing either side.
 (a/'article').write_text('remote edit\n');run(['git','add','.'],a);run(['git','commit','-m','remote edit'],a);run(['git','push'],a)
 remote_head=run(['git','rev-parse','HEAD'],a).stdout
 (b/'article').write_text('local edit\n');run(['git','add','article'],b);run(['git','commit','-m','local edit'],b)
 assert run(['bash',str(helper)],b,False).returncode!=0
 assert run(['git','--git-dir',str(p/'remote'),'rev-parse','main'],p).stdout==remote_head
 print('PASS: concurrent remote commit integrated; dirty local file preserved; conflict stops without overwriting remote.')
