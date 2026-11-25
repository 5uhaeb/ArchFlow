"""Real graph interactions. PYTHONPATH=. python tests/browser_ui.py"""
import os
import tempfile
import threading
import time
from pathlib import Path
import uvicorn
from playwright.sync_api import sync_playwright
import main

with tempfile.TemporaryDirectory() as temp:
    root=Path(temp)
    (root/'requirements.txt').write_text('fastapi\n');(root/'a.py').write_text('import b\n');(root/'b.py').write_text('x=1\n')
    server=uvicorn.Server(uvicorn.Config(main.app,host='127.0.0.1',port=8878,log_level='error'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    while not server.started: time.sleep(.01)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel=os.environ.get('ARCHFLOW_BROWSER_CHANNEL') or None)
            page=browser.new_page(viewport={'width':1500,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1:8878');page.locator('#folder').fill(temp);page.locator('#folder').press('Enter');page.wait_for_selector('.node[data-name="a.py"]')
            page.locator('#fit').click();page.wait_for_timeout(100)
            # Duplicate port gestures must select one canonical edge.
            for side in ['right','top']:
                start=page.locator(f'.node[data-name="requirements.txt"] .port.{side}').bounding_box();end=page.locator('.node[data-name="a.py"] .port.left').bounding_box()
                page.mouse.move(start['x']+start['width']/2,start['y']+start['height']/2);page.mouse.down();page.mouse.move(end['x']+end['width']/2,end['y']+end['height']/2,steps=5);page.mouse.up()
            assert page.evaluate("graph.edges.filter(e=>e.source==='requirements.txt'&&e.target==='a.py').length")==1
            page.evaluate("selectWire(graph.edges.find(e=>e.source==='requirements.txt').id)")
            page.keyboard.press('Delete');assert page.evaluate("graph.edges.every(e=>e.source!=='requirements.txt')")
            page.keyboard.press('Control+z');assert page.evaluate("graph.edges.some(e=>e.source==='requirements.txt')")
            page.keyboard.press('Control+Shift+z');assert page.evaluate("graph.edges.every(e=>e.source!=='requirements.txt')")
            page.locator('.node[data-name="a.py"] .label').click();assert page.locator('#editorModal').is_hidden()
            page.locator('.node[data-name="a.py"] .label').dblclick();assert page.locator('.details-panel').first.is_visible();assert 'a.py' in page.locator('.details-panel').first.inner_text()
            page.locator('.details-panel').first.get_by_role('button',name='Open in editor',exact=True).click();assert page.locator('#editorModal').is_visible();page.locator('#closeEditor').click()
            page.keyboard.press('Escape');page.locator('.node[data-name="a.py"]').focus();page.keyboard.press('Enter');assert page.locator('.details-panel').first.is_visible()
            page.keyboard.press('Escape');page.keyboard.press('Control+k');assert page.locator('.command-palette').is_visible();page.keyboard.press('Escape')
            # Validate discovery flows with mocked HTTP: no live provider calls.
            def assist_mock(route):
                action=route.request.post_data_json['action']
                payload={'text':'OK' if action=='validate' else 'This file imports its helper.'} if action!='suggest' else {'suggestions':[{'source':'requirements.txt','target':'a.py','rationale':'Review this dependency'}]}
                route.fulfill(json=payload)
            page.route('**/api/ai/assist',assist_mock)
            page.locator('#toolbar details').evaluate('(el)=>el.open=true')
            assert page.locator('#editorModal').is_hidden()
            page.locator('#key').fill('mock-key');page.locator('#enableAi').click();page.wait_for_function('aiEnabled')
            page.locator('#toolbar').get_by_role('button',name='AI',exact=True).click()
            page.locator('.ai-panel').get_by_role('button',name='Explain selected file').click();page.wait_for_selector('.ai-result')
            assert 'imports its helper' in page.locator('.ai-result').inner_text()
            page.locator('.ai-panel').get_by_role('button',name='Suggest connections',exact=True).click();page.wait_for_selector('.ai-panel .details-connection')
            page.locator('.ai-panel').get_by_role('button',name='Dismiss',exact=True).click();page.keyboard.press('Escape')
            page.evaluate("wireSelected=graph.edges.find(e=>e.origin==='auto').id;removeWire()")
            assert page.evaluate("graph.edges.some(e=>e.suppressed)")
            assert not errors,errors
            elapsed=page.evaluate("""()=>{files=Array.from({length:1000},(_,i)=>({name:'file'+i+'.py',status:'ok'}));graph.edges=[];collapsed.clear();let t=performance.now();render();return performance.now()-t}""")
            assert page.locator('.node').count()==1001
            assert elapsed<2000,elapsed
            print(f'1000-node render: {elapsed:.0f} ms (single local measurement)')
            browser.close();print('PASS: duplicate gestures, delete/undo/redo, selection, double-click details, editor, keyboard commands, suppression; no JS errors')
    finally:server.should_exit=True;thread.join(timeout=5)
