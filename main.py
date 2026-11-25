from __future__ import annotations

import ast
import hmac
import json
import secrets
import socket
import subprocess
import threading
import time
import webbrowser
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

import workspace_graph as wg
from ai_engine import ask_ai, available_models, guard_update
from workspace_safety import text

ROOT = Path(__file__).resolve().parent
app = FastAPI()
SESSION_TOKEN = secrets.token_urlsafe(32)
ACTIVE_ROOT = None

@app.middleware('http')
async def session_security(request, call_next):
    host = request.headers.get('host', '').split(':')[0]
    if host not in {'localhost','127.0.0.1','testserver'}:
        return JSONResponse({'detail':'Invalid host.'},status_code=403)
    if request.url.path.startswith('/api/'):
        origin = request.headers.get('origin')
        if origin and (urlsplit(origin).hostname not in {'localhost','127.0.0.1'} or urlsplit(origin).netloc != request.headers.get('host')):
            return JSONResponse({'detail':'Invalid origin.'},status_code=403)
        if not hmac.compare_digest(request.headers.get('x-archflow-token',''),SESSION_TOKEN):
            return JSONResponse({'detail':'Invalid session token.'},status_code=401)
    return await call_next(request)

class Folder(BaseModel): path: str
class FileEdit(BaseModel): folder: str; name: str; content: str = ""
class Edge(BaseModel): folder: str; source: str; target: str
class AIJob(Edge): api_key: str; model: str; constraint: str; provider: str = "OpenAI"; base_url: str = ""; instructions: str = ''
PROPOSALS: dict[str, tuple[Path, str, str, str]] = {}
UNDO: dict[str, tuple[str, str]] = {}

class Approval(BaseModel):
    proposal: str

@app.post('/api/ai/apply')
def apply_ai(body: Approval):
    data = PROPOSALS.pop(body.proposal, None)
    if data is None: raise HTTPException(409,'Proposal expired. Generate another preview.')
    path, original, proposed, constraint = data
    if ACTIVE_ROOT is None or not path.is_relative_to(ACTIVE_ROOT):
        raise HTTPException(409, 'The workspace changed. Generate a preview in the active workspace.')
    if text(path) != original: raise HTTPException(409,'Target changed after preview. Generate another preview.')
    result = guard_update(path, proposed, constraint)
    if result['written']: UNDO[str(path)] = (original, proposed)
    return result

@app.post('/api/ai/undo')
def undo_ai(body: FileEdit):
    path = safe_name(project(body.folder),body.name)
    item = UNDO.get(str(path))
    if not item: raise HTTPException(409,'No AI undo exists for this file in this session.')
    if text(path) != item[1]: raise HTTPException(409,'File changed since AI write. Undo refused to protect edits.')
    path.write_text(item[0],encoding='utf-8');del UNDO[str(path)]
    return {'ok':True}

def project(path: str, opening: bool = False) -> Path:
    global ACTIVE_ROOT
    if not path.strip(): raise HTTPException(400, "Open a folder or create a workspace first.")
    folder = Path(path).expanduser().resolve()
    if not folder.is_dir(): raise HTTPException(400, "Choose an existing folder.")
    if folder == ROOT or folder == Path(folder.anchor) or folder == Path.home():
        raise HTTPException(400, "Choose a dedicated project folder, not the app, home or filesystem root.")
    if opening: ACTIVE_ROOT = folder
    elif ACTIVE_ROOT != folder: raise HTTPException(409, 'Open this workspace before accessing its files.')
    return folder

class NewWorkspace(BaseModel):
    parent: str
    name: str

@app.post('/api/create-workspace')
def create_workspace(body: NewWorkspace):
    if not body.parent.strip() or not body.name.strip() or Path(body.name).name != body.name or body.name in {'.','..'} or any(c in body.name for c in '\\/:'):
        raise HTTPException(400, 'Choose a parent and a single folder name.')
    parent = Path(body.parent).expanduser().resolve()
    if not parent.is_dir(): raise HTTPException(400, 'Parent folder does not exist.')
    target = parent / body.name
    try: target.mkdir(exist_ok=False)
    except FileExistsError: raise HTTPException(409, 'Workspace already exists. Open it instead.')
    return {'path': str(target)}

def safe_name(folder: Path, name: str) -> Path:
    return wg.safe(folder, name)

def diagnose(path: Path, content: str | None = None) -> dict:
    try: text = globals()['text'](path) if content is None else content
    except HTTPException as exc: return {'status':'warning','diag':str(exc.detail)}
    suffix = path.suffix.lower()
    try:
        if suffix == ".py": ast.parse(text)
        elif suffix == ".json": json.loads(text)
    except (SyntaxError, json.JSONDecodeError) as exc:
        return {"status": "error", "diag": str(exc)}
    warning = ("TODO", "FIXME", "NotImplementedError")
    stubs = False
    if suffix == ".py":
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = node.body
                if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                    body = body[1:]
                stubs = stubs or bool(body and all(isinstance(item, ast.Pass) for item in body))
    if any(item in text for item in warning) or stubs:
        return {"status": "warning", "diag": "Contains unfinished work or a pass-only function stub."}
    return {"status": "ok", "diag": "No lightweight diagnostics."}

@app.get("/")
def home(): return HTMLResponse((ROOT / 'index.html').read_text(encoding='utf-8').replace('__SESSION_TOKEN__',SESSION_TOKEN), headers={'Cache-Control':'no-store'})
@app.get("/style.css")
def css(): return FileResponse(ROOT / "style.css", media_type="text/css")
@app.get("/workspace.js")
def workspace_script(): return FileResponse(ROOT / "workspace.js", media_type="text/javascript")
@app.get('/ui.js')
def ui_script(): return FileResponse(ROOT/'ui.js',media_type='text/javascript')
@app.post('/api/about')
def about():
    try: commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,timeout=2,check=True).stdout.strip()
    except (OSError,subprocess.SubprocessError): commit='unavailable'
    return {'version':'0.3.0-dev','commit':commit}

class AIAssist(BaseModel):
    action: Literal['validate','explain','suggest']
    folder: str = ''
    name: str = ''
    api_key: str
    model: str
    provider: str = 'OpenAI'
    base_url: str = ''

@app.post('/api/ai/assist')
def assist(body: AIAssist):
    content='';names=[]
    instruction='Reply with the single word OK. This is a credential connectivity check.'
    if body.action!='validate':
        folder=project(body.folder)
        if body.action=='explain':
            content=text(safe_name(folder,body.name));instruction='Explain this file in plain language. Do not output replacement code.'
        else:
            names=[p.relative_to(folder).as_posix() for p in wg.scan(folder) if p.is_file()][:200]
            content=json.dumps(names);instruction='Suggest up to five plausible architectural relationships to review, based only on these paths. These are hypotheses, not detected dependencies. Return only a JSON array of objects with source, target, rationale. Only use listed paths.'
    try:
        answer,_=ask_ai('input.txt',content,'answer.txt','','SUGGEST_ONLY',body.api_key,body.model,body.provider,body.base_url,instruction=instruction)
        if body.action=='suggest':
            proposals=json.loads(answer)
            if not isinstance(proposals,list): raise ValueError('Provider did not return a suggestion list.')
            return {'suggestions':[e for e in proposals[:5] if isinstance(e,dict) and e.get('source') in names and e.get('target') in names and e.get('source')!=e.get('target')]}
        return {'text':answer}
    except ValueError as exc: raise HTTPException(400,str(exc)) from None
    except TypeError: raise HTTPException(400,'Provider returned malformed data.') from None

@app.post('/api/models')
def models(body: AIAssist):
    if body.provider != 'Gemini':
        raise HTTPException(400, 'Live model discovery currently supports Gemini.')
    try:
        return {'models': available_models(body.api_key)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
@app.post("/api/files")
def files(body: Folder):
    folder = project(body.path, opening=True)
    ignored = {".git", ".pytest_cache", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".archflow_graph.json"}
    entries = []
    for path in wg.scan(folder):
        relative = path.relative_to(folder)
        if any(part in ignored for part in relative.parts) or not path.resolve().is_relative_to(folder): continue
        if path.is_file(): entries.append({"name": relative.as_posix(), **diagnose(path)})
        elif path.is_dir(): entries.append({"name": relative.as_posix(), "folder": True, "status": "ok", "diag": "Folder"})
    for entry in entries:
        try:
            stat=(folder/entry['name']).stat();entry['size']=stat.st_size;entry['modified']=stat.st_mtime
        except OSError: pass
    with wg.LOCK: graph = wg.refresh(folder)
    return {"files": sorted(entries, key=lambda x: (not x.get("folder", False), x["name"].lower())), "graph": graph}
@app.post("/api/read")
def read(body: FileEdit): return {"content": text(safe_name(project(body.folder), body.name))}
@app.post("/api/save")
def save(body: FileEdit):
    path = safe_name(project(body.folder), body.name); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(body.content, encoding="utf-8")
    wg.refresh(project(body.folder), force=True)
    return {"ok": True, **diagnose(path, body.content)}
@app.post("/api/new")
def new_file(body: FileEdit):
    path = safe_name(project(body.folder), body.name)
    if path.exists(): raise HTTPException(409, "That file already exists.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.content, encoding="utf-8")
    wg.refresh(project(body.folder), force=True)
    return {"ok": True, "name": path.name}
@app.post("/api/mkdir")
def mkdir(body: FileEdit):
    path = safe_name(project(body.folder), body.name); path.mkdir(parents=True, exist_ok=True)
    return {"ok": True}
def load_graph(folder: Path):
    return wg.read(folder)
@app.post("/api/edge")
def edge(body: Edge):
    folder = project(body.folder); safe_name(folder, body.source); safe_name(folder, body.target)
    if body.source == body.target: raise HTTPException(400, 'Self connections are not supported.')
    with wg.LOCK:
        graph = load_graph(folder)
        if not any(e['source']==body.source and e['target']==body.target and e['origin']=='manual' for e in graph['edges']):
            graph['edges'].append({'source':body.source,'target':body.target})
        return wg.write(folder, graph)
@app.post("/api/ai")
def ai(body: AIJob):
    folder = project(body.folder); source = body.source; target = body.target; safe_name(folder, source); safe_name(folder, target)
    if not (folder/source).is_file() or not (folder/target).is_file(): raise HTTPException(400, "AI wiring requires two files, not folders.")
    try:
        proposed, rationale = ask_ai(source, text(folder/source), target, text(folder/target), body.constraint, body.api_key, body.model, body.provider, body.base_url, request_notes=body.instructions)
        result = guard_update(folder / target, proposed, body.constraint, write=False)
        token = secrets.token_urlsafe(24)
        if body.constraint != 'SUGGEST_ONLY' and result['ok']:
            if len(PROPOSALS)>=20: PROPOSALS.clear()
            PROPOSALS[token] = (folder/target,text(folder/target),proposed,body.constraint)
        return {**result, 'proposal': token if body.constraint != 'SUGGEST_ONLY' and result['ok'] else None, "rationale": result.get('error', rationale)}
    except ValueError as exc: raise HTTPException(400, str(exc))

def run(): uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")

class CodexJob(Edge):
    constraint: str = 'ADD_AND_REWRITE_NO_DELETE'
    instructions: str = ''

@app.post('/api/codex')
def codex_generate(body: CodexJob):
    return ai(AIJob(**body.model_dump(), api_key='', model='gpt-6.1-terra', provider='CodexLocal'))

@app.post("/api/pick-folder")
def pick_folder():
    try:
        import webview
        chosen = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
        return {"path": chosen[0] if chosen else ""}
    except (ImportError, IndexError, AttributeError, RuntimeError):
        raise HTTPException(503, 'Native folder picker unavailable. Enter a folder path in the toolbar.') from None

@app.post("/api/graph")
def save_graph(body: FileEdit):
    folder = project(body.folder)
    try:
        graph = json.loads(body.content)
        if not isinstance(graph, dict) or not isinstance(graph.get('edges', []), list): raise TypeError('Invalid graph structure.')
        for edge in graph.get('edges', []):
            wg.safe(folder, edge['source'], root=True)
            wg.safe(folder, edge['target'], root=True)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(400, 'Invalid graph metadata.') from exc
    with wg.LOCK:
        if graph.get('revision', 0) != wg.read(folder)['revision']: raise HTTPException(409, 'Graph changed; reload before saving.')
        return wg.write(folder, graph)

class Move(BaseModel):
    folder: str
    source: str
    destination: str

class DeleteItem(BaseModel):
    folder: str
    source: str
    subtree: bool = False

@app.post('/api/move')
def move(body: Move): return wg.move(project(body.folder), body.source, body.destination)

@app.post('/api/delete')
def delete_item(body: DeleteItem):
    """Delete a file, or an empty folder unless its subtree was explicitly confirmed."""
    return wg.delete(project(body.folder), body.source, body.subtree)
if __name__ == "__main__":
    listener = socket.socket()
    try: listener.bind(('127.0.0.1',8765))
    except OSError: listener.bind(('127.0.0.1',0))
    port = listener.getsockname()[1]
    listener.listen(128)
    server = uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='warning'))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]),daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{port}'
    while not server.started and thread.is_alive(): time.sleep(.02)
    try:
        import webview
        webview.create_window("ArchFlow", url, width=1600, height=1000, min_size=(1100, 720))
        webview.start()
    except (ImportError, RuntimeError, OSError):
        webbrowser.open(url)
        try: thread.join()
        except KeyboardInterrupt: pass
    finally:
        server.should_exit=True;thread.join(timeout=5);listener.close()
