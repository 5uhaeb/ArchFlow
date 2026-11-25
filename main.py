from __future__ import annotations

import json
import threading
import webbrowser
import ast
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ai_engine import ask_ai, guard_update
import workspace_graph as wg

ROOT = Path(__file__).resolve().parent
app = FastAPI()

class Folder(BaseModel): path: str
class FileEdit(BaseModel): folder: str; name: str; content: str = ""
class Edge(BaseModel): folder: str; source: str; target: str
class AIJob(Edge): api_key: str; model: str; constraint: str; provider: str = "OpenAI"; base_url: str = ""

def project(path: str) -> Path:
    folder = Path(path).expanduser().resolve()
    if not folder.is_dir(): raise HTTPException(400, "Choose an existing folder.")
    return folder

def safe_name(folder: Path, name: str) -> Path:
    return wg.safe(folder, name)

def diagnose(path: Path, content: str | None = None) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace") if content is None else content
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
def home(): return FileResponse(ROOT / "index.html")
@app.get("/style.css")
def css(): return FileResponse(ROOT / "style.css", media_type="text/css")
@app.get("/workspace.js")
def workspace_script(): return FileResponse(ROOT / "workspace.js", media_type="text/javascript")
@app.post("/api/files")
def files(body: Folder):
    folder = project(body.path)
    ignored = {".git", ".pytest_cache", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".archflow_graph.json"}
    entries = []
    for path in wg.scan(folder):
        relative = path.relative_to(folder)
        if any(part in ignored for part in relative.parts) or not path.resolve().is_relative_to(folder): continue
        if path.is_file(): entries.append({"name": relative.as_posix(), **diagnose(path)})
        elif path.is_dir(): entries.append({"name": relative.as_posix(), "folder": True, "status": "ok", "diag": "Folder"})
    with wg.LOCK: graph = wg.refresh(folder)
    return {"files": sorted(entries, key=lambda x: (not x.get("folder", False), x["name"].lower())), "graph": graph}
@app.post("/api/read")
def read(body: FileEdit): return {"content": safe_name(project(body.folder), body.name).read_text(encoding="utf-8")}
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
        proposed, rationale = ask_ai(source, (folder/source).read_text(encoding="utf-8"), target, (folder/target).read_text(encoding="utf-8"), body.constraint, body.api_key, body.model, body.provider, body.base_url)
        return {**guard_update(folder / target, proposed, body.constraint), "rationale": rationale}
    except ValueError as exc: raise HTTPException(400, str(exc))

def run(): uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
@app.post("/api/pick-folder")
def pick_folder():
    try:
        import webview
        chosen = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
        return {"path": chosen[0] if chosen else ""}
    except Exception:
        import tkinter as tk
        from tkinter.filedialog import askdirectory
        root = tk.Tk(); root.withdraw()
        try: return {"path": askdirectory()}
        finally: root.destroy()

@app.post("/api/graph")
def save_graph(body: FileEdit):
    folder = project(body.folder)
    try:
        graph = json.loads(body.content)
        if not isinstance(graph, dict) or not isinstance(graph.get('edges', []), list): raise ValueError('Invalid graph structure.')
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

@app.post('/api/move')
def move(body: Move): return wg.move(project(body.folder), body.source, body.destination)
if __name__ == "__main__":
    threading.Thread(target=run, daemon=True).start()
    try:
        import webview
        webview.create_window("ArchFlow", "http://127.0.0.1:8765", width=1600, height=1000, min_size=(1100, 720))
        webview.start()
    except Exception:
        webbrowser.open("http://127.0.0.1:8765")
        threading.Event().wait()
