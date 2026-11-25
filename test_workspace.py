"""Run: python -m unittest test_workspace -v (temporary workspaces only)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import main
import workspace_graph as wg

def fixture(root):
    for name,text in {'pkg/__init__.py':'','pkg/a.py':'from . import b\n','pkg/b.py':'x = 1\n','web/app.js':"import './helper.js';\n",'web/helper.js':'export const x = 1;','web/index.html':'<script src="app.js"></script><link href="style.css" rel="stylesheet">','web/style.css':'@import "base.css";','web/base.css':'body {}','config.json':'{}','target/keep.txt':'unchanged'}.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);fixture(self.root);self.client=TestClient(main.app)
    def tearDown(self): self.client.close();self.temp.cleanup()
    def post(self,route,**data): return self.client.post('/api/'+route,json={'folder':str(self.root),**data})
    def test_detection_and_diagnostics(self):
        graph=self.post('files',path=str(self.root)).json()['graph'];pairs={(e['source'],e['target']) for e in graph['edges']}
        for pair in [('pkg/a.py','pkg/b.py'),('web/app.js','web/helper.js'),('web/index.html','web/app.js'),('web/style.css','web/base.css')]: self.assertIn(pair,pairs)
        self.assertEqual(self.post('save',name='pkg/b.py',content='def x(:').json()['status'],'error')
        self.assertEqual(self.post('save',name='pkg/b.py',content='def x(): pass').json()['status'],'warning')
    def test_move_metadata_and_conflicts(self):
        self.post('edge',source='pkg/a.py',target='pkg/b.py')
        graph=wg.read(self.root);graph['collapsed']=['pkg'];graph['selected']='pkg/a.py';wg.write(self.root,graph)
        before=(self.root/'pkg/a.py').read_bytes();r=self.post('move',source='pkg',destination='target');self.assertEqual(r.status_code,200,r.text)
        self.assertEqual((self.root/'target/pkg/a.py').read_bytes(),before)
        graph=r.json()['graph'];self.assertIn('target/pkg',graph['collapsed']);self.assertEqual(graph['selected'],'target/pkg/a.py')
        self.assertTrue(any(e['source']=='target/pkg/a.py' and e['target']=='target/pkg/b.py' for e in graph['edges']))
        self.assertEqual(self.post('move',source='target/pkg',destination='target').status_code,409)
        self.assertEqual(self.post('move',source='target',destination='target/pkg').status_code,400)
        self.assertEqual(self.post('move',source='../outside',destination='').status_code,400)
        self.assertEqual(self.post('move',source='.archflow_graph.json',destination='target').status_code,400)
        self.assertEqual(self.post('move',source='target/keep.txt',destination='').status_code,200)
    def test_revision_and_rollback(self):
        old=wg.read(self.root);self.post('edge',source='pkg/a.py',target='pkg/b.py')
        self.assertEqual(self.post('graph',name='',content=json.dumps(old)).status_code,409)
        with patch('workspace_graph.write',side_effect=OSError('simulated disk failure')):
            self.assertEqual(self.post('move',source='pkg',destination='target').status_code,500)
        self.assertTrue((self.root/'pkg/a.py').exists());self.assertFalse((self.root/'target/pkg').exists())
    def test_create_edit_ai_and_migration(self):
        self.assertEqual(self.post('mkdir',name='new/deep').status_code,200)
        self.assertEqual(self.post('new',name='new/deep/a.txt',content='hello').status_code,200)
        with patch('main.ask_ai',return_value=('x = 1\ny = 2\n','mocked')):
            r=self.post('ai',source='pkg/a.py',target='pkg/b.py',api_key='test',model='test',constraint='APPEND_ONLY')
            self.assertTrue(r.json()['written'])
        self.assertEqual(self.post('ai',source='pkg',target='pkg/b.py',api_key='test',model='test',constraint='SUGGEST_ONLY').status_code,400)
        (self.root/'.archflow_graph.json').write_text(json.dumps({'edges':[{'source':'pkg/a.py','target':'pkg/b.py'}]}))
        graph=wg.read(self.root);self.assertEqual(graph['version'],2);self.assertEqual(graph['edges'][0]['source_port'],'right')

if __name__=='__main__': unittest.main()
