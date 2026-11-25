"""Local real-browser regression, run directly; no provider requests."""
import tempfile
import threading
import time
import uvicorn
from playwright.sync_api import sync_playwright
import main

with tempfile.TemporaryDirectory() as parent:
    server=uvicorn.Server(uvicorn.Config(main.app,host='127.0.0.1',port=8877,log_level='error'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    while not server.started: time.sleep(.01)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto('http://127.0.0.1:8877')
            assert page.locator('.node').count()==0
            assert page.locator('#emptyState').is_visible()
            page.evaluate('(parent)=>api("create-workspace",{parent,name:"TO-DO-APP"}).then(async d=>{$("folder").value=d.path;await load(true)})',parent)
            assert page.locator('.file-node').count()==0
            assert page.locator('.folder-node').count()==0
            assert page.locator('.workspace-node').count()==1
            page.evaluate('api("mkdir",{folder:folder(),name:"one"}).then(()=>load())')
            assert page.locator('.folder-node').count()==1
            assert not errors,errors
            browser.close()
            print('PASS: fresh launch zero nodes; dedicated empty workspace; creation adds exactly one folder; no JavaScript errors')
    finally: server.should_exit=True;thread.join(timeout=5)
