"""Publish a new instrumented build as a regular public Latest release."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
REPO='The-Blustone-Revival-Project/Blustone-Instrumented'
def run(*args,capture=False):
 return subprocess.check_output(args,cwd=ROOT,text=True).strip() if capture else subprocess.run(args,cwd=ROOT,check=True)
def sha(file):
 h=hashlib.sha256()
 with file.open('rb') as f:
  while b:=f.read(8*1024*1024):h.update(b)
 return h.hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['summary','notes-file','apk','metadata','checksums']:p.add_argument('--'+name,required=True,type=Path if name!='summary' else str)
 p.add_argument('--validate-only',action='store_true');args=p.parse_args()
 tag=(ROOT/'VERSION').read_text().strip()
 if not re.fullmatch(r'2\.8\.0\.1\+[1-9]\d*',tag):raise ValueError('Expected 2.8.0.1+N build version')
 if '\n' in args.summary or not args.summary.strip():raise ValueError('One-line descriptive summary required')
 for file in [args.notes_file,args.apk,args.metadata,args.checksums]:
  if not file.is_file():raise ValueError('Missing release artifact: '+str(file))
 if args.apk.name!='BLUSTONE-Instrumented.apk':raise ValueError('Keep the established APK asset name')
 metadata=json.loads(args.metadata.read_text(encoding='utf-8-sig'))
 if metadata.get('package')!='com.vshower.prd_sr.instrumented':raise ValueError('Original package must never be published as the instrumented build')
 hashes={line.split()[1].lstrip('*'):line.split()[0].lower() for line in args.checksums.read_text(encoding='utf-8-sig').splitlines() if line.strip()}
 for file in [args.apk,args.metadata]:
  if hashes.get(file.name)!=sha(file):raise ValueError('Checksum mismatch: '+file.name)
 title=tag+': '+args.summary.strip()
 if args.validate_only:print(json.dumps({'tag':tag,'title':title,'published':False}));return
 if run('git','status','--porcelain',capture=True):raise ValueError('Commit reviewed source first')
 head=run('git','rev-parse','HEAD',capture=True)
 if run('git','ls-remote','origin','refs/heads/main',capture=True).split()[0]!=head:raise ValueError('Push reviewed source before publishing')
 if run('git','ls-remote','origin','refs/tags/'+tag,capture=True):raise ValueError('Build tag already exists; never replace an old build')
 run('git','tag','-a',tag,'-m',title);run('git','push','origin',tag)
 run('gh','release','create',tag,str(args.apk),str(args.metadata),str(args.checksums),'--repo',REPO,'--verify-tag',
     '--title',title,'--notes-file',str(args.notes_file),'--draft=false','--prerelease=false','--latest')
if __name__=='__main__':main()
