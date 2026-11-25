"""Optional real interactions: python test_browser.py (Playwright + Edge)."""
import json
import tempfile
import threading
import time
from pathlib import Path
import uvicorn
from playwright.sync_api import sync_playwright
from test_workspace import fixture
import main

with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);fixture(root)
    server=uvicorn.Server(uvicorn.Config(main.app,host='127.0.0.1',port=8876,log_level='error'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    while not server.started: time.sleep(.02)
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page(viewport={'width':1500,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1:8876');page.evaluate('theme(false)');page.locator('#folder').fill(temp);page.locator('#folder').press('Enter');page.wait_for_selector('.node[data-name="pkg/a.py"]')
            assert page.locator('#run').is_disabled()
            page.locator('#key').fill('example-key');page.locator('#enableAi').click();assert not page.locator('#run').is_disabled()
            page.locator('#provider').select_option('Claude');assert page.locator('#model').input_value().startswith('claude-')
            page.locator('#provider').select_option('Custom');assert page.locator('#customBase').is_visible()
            page.locator('#fit').click();page.wait_for_timeout(350)
            assert page.evaluate("Object.values(positions).every((a,i,all)=>all.every((b,j)=>i===j||Math.abs(a.x-b.x)>=W||Math.abs(a.y-b.y)>=H))")
            assert page.locator('.node .port').count()==page.locator('.node').count()*4
            assert page.locator('.branch').count()==page.locator('.node').count()-1
            assert page.evaluate("positions.pkg.y===positions.web.y && positions['pkg/a.py'].x===positions['pkg/b.py'].x && positions['pkg/a.py'].y<positions['pkg/b.py'].y")
            # Four source sides to four destination sides, using real pointer movement.
            for side in ['top','bottom','left','right']:
                start=page.locator(f'.node[data-name="pkg/b.py"] .port.{side}');end=page.locator(f'.node[data-name="config.json"] .port.{side}')
                a=start.bounding_box();b=end.bounding_box();page.mouse.move(a['x']+a['width']/2,a['y']+a['height']/2);page.mouse.down();page.mouse.move(b['x']+b['width']/2,b['y']+b['height']/2,steps=8);page.mouse.up();page.wait_for_timeout(80)
            assert page.evaluate("graph.edges.filter(e=>e.origin==='manual').length")==4
            page.locator('.node[data-name="pkg/b.py"] .port.right').hover();assert page.locator('#inspector').is_visible();assert 'Outgoing' in page.locator('#inspector').inner_text()
            page.locator('#inspector button').first.click()
            # Filesystem move via a real drag onto a folder.
            page.locator('.node[data-name="pkg/b.py"] .label').drag_to(page.locator('.node[data-name="target"] .label'))
            page.wait_for_selector('.node[data-name="target/b.py"]');assert (root/'target/b.py').read_text()=='x = 1\n'
            # Collapse and bounds clamp; editor independence and theme.
            page.locator('.node[data-name="web"] .toggle').click();assert page.locator('.node[data-name="web/app.js"]').count()==0
            # Hover inspection must not persistently expand a collapsed neighbor.
            page.evaluate("graph.edges.push({source:'config.json',target:'web/app.js',source_port:'top',target_port:'bottom',origin:'manual',type:'config'});render()")
            page.locator('.node[data-name="config.json"] .port.top').hover();assert 'hidden' in page.locator('#inspector').inner_text()
            assert page.evaluate("collapsed.has('web')")
            page.locator('#inspector .relationship').filter(has_text='web/app.js').click();page.wait_for_selector('.node[data-name="web/app.js"]')
            page.locator('#inspector button').first.click()
            for value in [.35,1,2]:
                page.evaluate('(z)=>{zoom=z;panX=-1e8;panY=1e8;schedule()}',value);page.wait_for_timeout(80)
                assert page.evaluate('Math.abs(panX)<bounds.w*zoom+canvas.clientWidth && Math.abs(panY)<bounds.h*zoom+canvas.clientHeight')
            page.evaluate('panX=-1e8;panY=1e8;schedule()');page.wait_for_timeout(100)
            assert page.evaluate('Math.abs(panX)<1e7 && Math.abs(panY)<1e7')
            page.locator('#fit').click();page.locator('.node[data-name="config.json"] .label').click();page.locator('#code').fill('{"test": 1}');page.locator('#save').click();page.wait_for_timeout(300);assert json.loads((root/'config.json').read_text())=={'test':1}
            assert page.locator('#editorModal').is_visible();page.locator('#closeEditor').click();assert page.locator('#editorModal').is_hidden()
            assert page.evaluate("document.querySelector('#code').getBoundingClientRect().left>=document.querySelector('#nums').getBoundingClientRect().right")
            page.evaluate("$('code').value='import os\\n# <span> \\\"string\\\"';color()")
            assert page.locator('#highlight').inner_text().startswith('import os')
            page.evaluate("$('code').value=baseline;color()")
            page.locator('#theme').click();assert page.locator('html').get_attribute('data-theme')=='dark'
            # Inline creation opens the editor and creates nested files.
            page.evaluate("activeFolder='target'");page.locator('#new').click();page.locator('.inline-create input').fill('fresh.py');page.locator('.inline-create input').press('Enter');page.wait_for_selector('.node[data-name="target/fresh.py"]');assert (root/'target/fresh.py').exists()
            page.wait_for_timeout(600);page.reload();page.locator('#folder').fill(temp);page.locator('#folder').press('Enter');page.wait_for_selector('.node[data-name="target/b.py"]');assert page.evaluate("graph.edges.some(e=>e.origin==='manual'&&e.source==='target/b.py')")
            assert not errors,errors
            # Reference composition: workspace above folder columns, stacked leaf files.
            page.evaluate("""()=>{files=[...['Backend','Config','Frontend'].map(name=>({name,folder:true,status:'ok'})),...['Backend/main.py','Backend/ai_engine.py','Backend/utils.py','Config/config.json','Config/.env','Frontend/index.html','Frontend/style.css','Frontend/app.js'].map(name=>({name,status:'ok'}))];graph.edges=[{source:'Backend/main.py',target:'Frontend/app.js',source_port:'right',target_port:'bottom',origin:'manual',type:'python'},{source:'Backend/ai_engine.py',target:'Config/.env',source_port:'right',target_port:'left',origin:'manual',type:'backend'},{source:'Frontend/index.html',target:'Frontend/style.css',source_port:'bottom',target_port:'top',origin:'manual',type:'css'}];hovered=null;pinned=false;$('inspector').hidden=true;collapsed.clear();theme(true);render();fit()}""")
            page.wait_for_timeout(150)
            preview=Path(tempfile.gettempdir())/'archflow-reference-preview.png'
            page.locator('#canvas').screenshot(path=str(preview))
            print('Reference preview:',preview)
            # Stress layout without filesystem fixtures; preserves the temporary project.
            elapsed=page.evaluate("""()=>{files=Array.from({length:1000},(_,i)=>({name:'file'+i+'.py',status:'ok',diag:''}));graph.edges=[];collapsed.clear();const start=performance.now();render();return performance.now()-start}""")
            assert page.locator('.node').count()==1001
            assert page.evaluate("Object.values(positions).every((a,i,all)=>all.every((b,j)=>i===j||Math.abs(a.x-b.x)>=W||Math.abs(a.y-b.y)>=H))")
            print(f'1000-file layout: {elapsed:.0f} ms (single local measurement)')
            print('PASS: graphical layout, four-sided wiring, inspector, drag move, collapse, bounded pan, editor save, dark theme, inline creation, restart persistence; zero browser errors')
            browser.close()
    finally:
        server.should_exit=True;thread.join(timeout=5)
