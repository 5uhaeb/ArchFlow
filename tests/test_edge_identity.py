import workspace_graph as wg

def test_manual_and_detected_merge():
    graph=wg.normalize({'edges':[{'source':'./requirements.txt','target':'app.py','type':'python','origin':'manual'}, {'source':'requirements.txt','target':'app.py','type':'python','origin':'auto'}]})
    assert len(graph['edges'])==1
    assert graph['edges'][0]['origin']=='both'
    assert graph['edges'][0]['id']

def test_manual_duplicate_ports_are_not_new_identity():
    graph=wg.normalize({'edges':[{'source':'requirements.txt','target':'app.py','source_port':p} for p in ['top','right']]})
    assert len(graph['edges'])==1

def test_suppression_survives_refresh(tmp_path):
    (tmp_path/'a.py').write_text('import b\n');(tmp_path/'b.py').write_text('')
    graph=wg.refresh(tmp_path);graph['edges'][0]['suppressed']=True;wg.write(tmp_path,graph)
    assert wg.refresh(tmp_path,force=True)['edges'][0]['suppressed']

def test_duplicate_migration_creates_original_backup(tmp_path):
    import json
    original={'version':2,'edges':[{'source':'requirements.txt','target':'app.py'},{'source':'requirements.txt','target':'app.py'}]}
    path=tmp_path/'.archflow_graph.json';path.write_text(json.dumps(original))
    assert len(wg.read(tmp_path)['edges'])==1
    assert json.loads((tmp_path/'.archflow_graph.v2-before-merge.json').read_text())==original
