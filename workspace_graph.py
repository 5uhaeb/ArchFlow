"""Versioned graph storage, static local references, and safe workspace moves."""
import ast
import copy
import json
import logging
import os
import posixpath
import re
import shutil
import tempfile
import threading
from pathlib import Path

import pathspec
from fastapi import HTTPException

from workspace_safety import MAX_ENTRIES, text

LOCK = threading.RLock()
IGNORED = {'.git', '.pytest_cache', '__pycache__', 'node_modules', '.venv', 'venv', 'dist', 'build', '.idea', '.vscode', '.DS_Store', '.archflow_graph.json', '.archflow_backups'}
PORTS = {'top', 'bottom', 'left', 'right'}
TYPES = {'python','javascript','html','css','backend','database','config','ai','broken','other'}

def safe(folder, name, root=False):
    if not isinstance(name, str) or Path(name).is_absolute() or '..' in Path(name).parts:
        raise HTTPException(400, 'Use a relative workspace path without traversal.')
    result = (folder / name).resolve()
    if not result.is_relative_to(folder) or (result == folder and not root) or any(p in IGNORED or p.startswith('.archflow-') for p in Path(name).parts):
        raise HTTPException(400, 'Protected or outside-workspace path.')
    return result

def kind(name):
    return {'.py':'python','.js':'javascript','.mjs':'javascript','.ts':'javascript','.html':'html','.css':'css','.json':'config','.yaml':'config','.toml':'config','.sql':'database','.db':'database'}.get(Path(name).suffix.lower(),'other')

def normalize(data):
    result = {'version':2, 'revision':int(data.get('revision',0)), 'detected':bool(data.get('detected',False)), 'edges':[], 'collapsed':data.get('collapsed',[]), 'selected':data.get('selected'), 'view':data.get('view',{})}
    seen={}
    for e in data.get('edges',[]):
        if not isinstance(e,dict) or not isinstance(e.get('source'),str) or not isinstance(e.get('target'),str) or e['source']==e['target']: continue
        edge={k:e[k] for k in ('source','target','reference') if k in e}
        edge['source']=posixpath.normpath(edge['source'].replace('\\','/'))
        edge['target']=posixpath.normpath(edge['target'].replace('\\','/'))
        edge.update(source_port=e.get('source_port') if e.get('source_port') in PORTS else 'right', target_port=e.get('target_port') if e.get('target_port') in PORTS else 'left', type=e.get('type') if e.get('type') in TYPES else kind(e['source']), origin=e.get('origin') if e.get('origin') in {'auto','both'} else 'manual', suppressed=bool(e.get('suppressed',False)))
        key=json.dumps([edge['source'],edge['target'],edge['type']],ensure_ascii=False,separators=(',',':'))
        edge['id']=key
        if key in seen:
            previous=seen[key]
            if previous['origin']!=edge['origin']: previous['origin']='both'
            previous['suppressed']=previous['suppressed'] or edge['suppressed']
        else: seen[key]=edge
    result['edges']=list(seen.values())
    return result

def read(folder):
    try:
        path=folder/'.archflow_graph.json';raw=json.loads(path.read_text(encoding='utf-8'));normalized=normalize(raw)
        if len(normalized['edges'])<len(raw.get('edges',[])):
            backup=folder/'.archflow_graph.v2-before-merge.json'
            if not backup.exists():
                shutil.copy2(path,backup)
                logging.getLogger(__name__).info('Merged %d duplicate graph records; original metadata backed up.',len(raw.get('edges',[]))-len(normalized['edges']))
        return normalized
    except (OSError, ValueError, TypeError): return normalize({})

def write(folder, data):
    data=normalize(data);data['revision']+=1
    fd,name=tempfile.mkstemp(prefix='.archflow-',dir=folder)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as out: json.dump(data,out,indent=2);out.flush();os.fsync(out.fileno())
        os.replace(name,folder/'.archflow_graph.json')
    finally:
        if os.path.exists(name): os.unlink(name)
    return data

def scan(folder):
    count = 0
    ignore_file = folder / '.gitignore'
    try: rules = pathspec.GitIgnoreSpec.from_lines(ignore_file.read_text(encoding='utf-8').splitlines())
    except (OSError, UnicodeError): rules = pathspec.GitIgnoreSpec.from_lines([])
    # Prune ignored directories before descending (unlike rglob filtering).
    for base,dirs,files in os.walk(folder,followlinks=False):
        dirs[:]=sorted(d for d in dirs if d not in IGNORED and not (Path(base)/d).is_symlink() and not rules.match_file((Path(base)/d).relative_to(folder).as_posix()+'/'))
        for name in dirs+sorted(files):
            p=Path(base)/name
            if rules.match_file(p.relative_to(folder).as_posix()): continue
            if name in IGNORED or name.startswith(('.archflow-','.archflow_graph')) or p.is_symlink(): continue
            if p.suffix.lower() in {'.pyc','.exe','.dll','.png','.jpg','.zip','.pdf'}: continue
            count += 1
            if count > MAX_ENTRIES: return
            yield p

def detect(folder):
    paths={p.relative_to(folder).as_posix():p for p in scan(folder) if p.is_file()}
    edges=[]
    for name,p in paths.items():
        if p.suffix.lower() not in {'.py','.js','.mjs','.ts','.html','.htm','.css'}: continue
        try: content=text(p)
        except HTTPException: continue
        refs=[]
        if p.suffix=='.py':
            try: tree=ast.parse(content)
            except SyntaxError: continue
            for node in ast.walk(tree):
                if isinstance(node,ast.Import): refs.extend((a.name.replace('.','/'),False) for a in node.names)
                if isinstance(node,ast.ImportFrom):
                    prefix=('/'.join(name.split('/')[:-node.level])+'/' if node.level else '')
                    module=(node.module or '').replace('.','/')
                    refs.extend((prefix+('/'.join(filter(None,[module,a.name]))),bool(node.level)) for a in node.names)
                    if module: refs.append((prefix+module,bool(node.level)))
        else:
            patterns=[r'''(?:from\s*|import\s*|require\s*\(\s*)["']([^"']+)["']'''] if p.suffix in {'.js','.mjs','.ts'} else ([r'''(?:src|href)\s*=\s*["']([^"']+)["']'''] if p.suffix in {'.html','.htm'} else [r'''@import\s+(?:url\(\s*)?["']([^"']+)["']''',r'''url\(\s*["']?([^"')\s]+)'''])
            refs.extend((r,True) for pattern in patterns for r in re.findall(pattern,content))
        for ref,local in refs:
            if re.match(r'^(?:[a-z]+:|//|#)',ref,re.IGNORECASE): continue
            ref=ref.split('?')[0].split('#')[0]
            base=(folder/ref.lstrip('/') if p.suffix=='.py' or ref.startswith('/') else p.parent/ref).resolve()
            if not base.is_relative_to(folder): continue
            candidates=[base,base.with_suffix('.py'),base/'__init__.py'] if p.suffix=='.py' else [base,*[Path(str(base)+s) for s in ('.js','.ts','.mjs','/index.js')]]
            target=next((c.relative_to(folder).as_posix() for c in candidates if c.relative_to(folder).as_posix() in paths),None)
            if not target:
                # Bare packages are external, not fabricated local edges.
                if not local or (p.suffix in {'.js','.mjs','.ts'} and not ref.startswith(('.', '/'))): continue
                target=base.relative_to(folder).as_posix()
            if target==name: continue
            edges.append({'source':name,'target':target,'origin':'auto','type':kind(target) if target in paths else 'broken','reference':ref})
    return normalize({'edges':edges})['edges']

def refresh(folder, force=False):
    graph=read(folder)
    if force or not graph['detected']:
        manual=[{**e,'origin':'manual'} for e in graph['edges'] if e['origin'] in {'manual','both'}]
        suppressed={e['id'] for e in graph['edges'] if e.get('suppressed')}
        new=normalize({'edges':manual+[{**e,'suppressed':e['id'] in suppressed} for e in detect(folder)]})['edges']
        changed = new != graph['edges'] or not graph['detected']
        graph['detected']=True
        if changed: graph['edges']=new;return write(folder,graph)
    return graph

def move(folder,source,destination):
    with LOCK:
        src=safe(folder,source);dest=safe(folder,destination,root=True)
        if not src.exists() or not dest.is_dir(): raise HTTPException(400,'Source or destination does not exist.')
        if src.is_dir() and dest.is_relative_to(src): raise HTTPException(400,'Cannot move a folder into itself or its descendants.')
        target=dest/src.name
        if target.exists(): raise HTTPException(409,'Destination exists; nothing was overwritten.')
        old=src.relative_to(folder).as_posix();new=target.relative_to(folder).as_posix();before=read(folder)
        def remap(value):
            if isinstance(value,str): return new+value[len(old):] if value==old or value.startswith(old+'/') else value
            if isinstance(value,list): return [remap(v) for v in value]
            if isinstance(value,dict): return {remap(k):remap(v) for k,v in value.items()}
            return value
        updated=remap(copy.deepcopy(before))
        try:
            src.rename(target)
            write(folder,updated)
        except OSError as exc:
            if target.exists() and not src.exists(): target.rename(src)
            raise HTTPException(500,'Move failed; original location restored: '+str(exc)) from exc
        # Preserve remapped auto edges until the client reloads; detection also exposes broken old imports.
        warnings=['Imports and relative references may require updates. Source code was not rewritten.']
        return {'ok':True,'source':old,'target':new,'graph':read(folder),'warnings':warnings}

def delete(folder, source, subtree=False):
    """Remove one workspace item and its graph references, without ever touching the root."""
    with LOCK:
        path = safe(folder, source)
        if not path.exists():
            raise HTTPException(404, 'The item no longer exists.')
        is_folder = path.is_dir()
        if is_folder and any(path.iterdir()) and not subtree:
            raise HTTPException(409, 'This folder is not empty. Choose the subtree option to continue.')
        before = read(folder)
        prefix = source.rstrip('/') + '/'
        updated = copy.deepcopy(before)
        updated['edges'] = [edge for edge in before['edges'] if edge['source'] != source and edge['target'] != source and not edge['source'].startswith(prefix) and not edge['target'].startswith(prefix)]
        updated['collapsed'] = [name for name in before.get('collapsed', []) if name != source and not name.startswith(prefix)]
        if updated.get('selected') == source or str(updated.get('selected', '')).startswith(prefix):
            updated['selected'] = None
        try:
            if is_folder:
                shutil.rmtree(path)
            else:
                path.unlink()
            graph = write(folder, updated)
        except OSError as exc:
            raise HTTPException(500, 'Delete failed: ' + str(exc)) from exc
        return {'ok': True, 'source': source, 'subtree': bool(subtree), 'graph': graph}
