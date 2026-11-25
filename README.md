# ArchFlow

Local Python desktop workspace wiring utility. Uses FastAPI, pywebview and vanilla HTML/CSS/JavaScript.

## Run

```sh
python -m pip install -r requirements.txt
python main.py
```

Open a project, create files/folders, connect output to input ports and run wiring. API keys stay in the current browser session. Custom providers accept a base URL including `/v1`. Review generated changes before using them. Preview Diff Only avoids writes. Preserve Existing Code retains every meaningful existing line, ignoring trailing whitespace.

The local server binds to 127.0.0.1:8765. Native window failures fall back to your browser. Workspace graph data is stored in `.archflow_graph.json`.
