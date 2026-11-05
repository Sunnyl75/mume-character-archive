"""Local service, source preparation and user-decision regressions."""
import base64
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest
from urllib import request, error
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from deck_workbench import Workbench, Handler, ThreadingHTTPServer, input_hash, unpack_research, working_stamp
from workbench_sources import extract, prepare_source

SOURCE = '''A small path
Shrew is dead! R.I.P.
*Aarvorn the Half-Elf* is dead! R.I.P.
*an Elf* is dead! R.I.P.
A hungry warg is dead! R.I.P.
#Ok. not a trophy
*** TROPHY *** (Number Killed, Knowledge, Mobile)
  1, 1%, The Balrog | 3, 2%, #Victim |
  2, 0%, #Other | 1, 1%, #Unknown Player |
*** Return: continue, b: back one page, r: redisplay, q:quit (10%) ***
  1, 0%, #Last |
'''


class SourceTests(unittest.TestCase):
    def test_conservative_deaths_and_confirmed_trophy_blocks(self):
        entries = extract(SOURCE, 'Observer')
        self.assertEqual([(e['kind'], e['character'], e['count']) for e in entries],
                         [('death','Shrew',1),('death','Aarvorn',1),('trophy','Victim',3),('trophy','Other',2),('trophy','Last',1)])
        self.assertEqual(extract('1, 0%, #Victim\n#Ok. anything'), [])
        self.assertEqual(extract('You are dead! Sorry...'), [])
        self.assertEqual(extract('You are dead! Sorry...', 'Observer')[0]['character'], 'Observer')

    def test_preparation_never_adds_unselected_entries_or_infers_player(self):
        payload = {'title':'Source', 'text':SOURCE, 'observer':'Observer', 'selected':[0,2],
                   'groups':'pOwner: Observer, Other'}
        docs = prepare_source(payload)
        rec = docs['log.json']['records'][0]
        self.assertEqual([d['character'] for d in rec['deaths']], ['Shrew'])
        self.assertEqual(rec['trophy_list']['derived_kill_evidence'][0]['minimum_kill_count'], 3)
        self.assertEqual(docs['players.json']['players'][0]['characters_as_written'], ['Observer','Other'])
        with self.assertRaises(ValueError):
            prepare_source({**payload, 'observer':''})
        with self.assertRaises(ValueError):
            prepare_source({**payload, 'selected':[999]})

    def test_html_script_content_is_not_game_output(self):
        text = '<html><script>Fake is dead! R.I.P.</script><pre>Shrew is dead! R.I.P.</pre></html>'
        self.assertEqual([e['character'] for e in extract(text)], ['Shrew'])

    def test_zip_path_traversal_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as z:
                z.writestr('okay.json', '{}')
                z.writestr('../escape', 'bad')
            with self.assertRaises(ValueError):
                unpack_research(stream.getvalue(), Path(temp))
            self.assertEqual(list(Path(temp).iterdir()), [])


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.root = self.folder / 'archive'
        shutil.copytree(ROOT / 'data/working', self.root / 'data/working')
        (self.root / 'scripts').mkdir()
        for name in ('import_historical_evidence.py','publish_deck.py','build_whois_queue.py'):
            (self.root / 'scripts' / name).touch()
        self.app = Workbench(self.root, self.folder / 'session')

    def tearDown(self):
        self.temp.cleanup()

    def test_selection_clears_old_import_and_preview(self):
        self.app.data.update(whois_imported=True, whois_preview={'old':True})
        self.app.uploaded({'kind':'whois','filename':'archive.json','data':base64.b64encode(b'{"records":{},"captures":[]}').decode()})
        self.assertNotIn('whois_imported', self.app.data)
        self.assertNotIn('whois_preview', self.app.data)

    def test_preview_is_bound_to_input_and_archive_revision(self):
        source = self.folder / 'data.json'
        source.write_text('{}')
        self.app.data['research_path'] = str(source)
        self.app.data['research_preview'] = {'hash':input_hash(source),'stamp':working_stamp(self.root)}
        self.app.check_preview('research')
        source.write_text('{"changed":true}')
        with self.assertRaises(ValueError):
            self.app.check_preview('research')

    def test_conflicting_review_is_rejected_without_writing(self):
        self.app.prepare({'title':'Example','text':'Player of Shared', 'groups':'pOne: Shared'})
        # Use a small explicit table to test choosing an existing player.
        (self.root / 'data/working/player_character_links.csv').write_text(
            'link_id,player_id,character_id,character_name,main_handle,link_type,status,confidence,primary_evidence_id,notes\n'
            'old,player_0001,char_shared,Shared,Rogon,listed_same_player,accepted,high,,\n'
            'link_hist_test,player_0002,char_shared,Shared,Ajax,listed_same_player,needs_review,high,,\n')
        path = self.root / 'data/working/player_character_links.csv'
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            self.app.review([{'link_id':'link_hist_test','status':'accepted'}])
        self.assertEqual(before,path.read_bytes())
        self.app.review([{'link_id':'link_hist_test','status':'accepted','player_id':'player_0001'}])
        self.assertIn('link_hist_test,player_0001',path.read_text())

    def test_background_jobs_are_serial_and_publish_needs_confirmation(self):
        started, release = threading.Event(), threading.Event()
        def run(*args):
            started.set(); release.wait(3)
        with patch.object(self.app,'run',run):
            self.app.start('validate',{})
            self.assertTrue(started.wait(2))
            with self.assertRaises(ValueError):
                self.app.start('queue',{})
            release.set()
            for _ in range(100):
                if self.app.job['status']!='running':break
                time.sleep(.01)
        self.app.worker('publish',{})
        self.assertEqual(self.app.job['status'],'error')
        self.assertIn('Confirm publication',self.app.job['error'])

    def test_connection_key_is_never_in_ui_state_or_operation_log(self):
        token='A'*48
        with patch('deck_workbench.deck_wordpress_api.call',return_value={'ready':True}):
            self.app.job={'status':'running','log':[]}
            self.app.worker('connect',{'site':'https://example.org','key':token})
        self.assertEqual(self.app.job['status'],'done')
        self.assertNotIn(token,json.dumps(self.app.public_state()))
        self.assertEqual((self.root/'.deck-publish-token').stat().st_mode & 0o077,0)
        self.assertNotIn(token,(self.app.directory/'state.json').read_text())

    def test_preview_records_are_searchable_paginated_and_separate_from_polling(self):
        report = {'session':'test', 'changes':{'characters: added':2}, 'records':[
            {'key':'characters:one','table':'characters','id':'one','action':'added','before':None,
             'after':{'name':'Rogrog'},'changed_fields':['name'],'evidence_ids':['evidence_one'],'source_ids':['source_one']},
            {'key':'characters:two','table':'characters','id':'two','action':'added','before':None,
             'after':{'name':'Dorien'},'changed_fields':['name'],'evidence_ids':[],'source_ids':[]}],
            'evidence_context':{'evidence_one':{'raw_text':'EXACT_SOURCE_SENTINEL'}},
            'source_context':{'source_one':{'title':'Original page'}}}
        path = self.app.directory/'research-preview.json'
        path.write_text(json.dumps(report))
        self.app.remember_report(path)
        first = self.app.preview_records({'limit':['1']})
        second = self.app.preview_records({'offset':['1'],'limit':['1']})
        self.assertEqual(first['total'],2)
        self.assertEqual(first['records'][0]['after']['name'],'Rogrog')
        self.assertEqual(second['records'][0]['after']['name'],'Dorien')
        found = self.app.preview_records({'q':['dOrIeN'],'table':['characters']})
        self.assertEqual(found['total'],1)
        detail = self.app.preview_record('characters:one')
        self.assertEqual(detail['evidence'][0]['raw_text'],'EXACT_SOURCE_SENTINEL')
        self.assertEqual(detail['sources'][0]['title'],'Original page')
        self.assertNotIn('EXACT_SOURCE_SENTINEL',json.dumps(self.app.public_state()))
        with self.assertRaises(ValueError):self.app.preview_record('no-such-record')
        with self.assertRaises(ValueError):self.app.preview_records({'offset':['invalid']})

    def test_old_preview_reports_request_a_new_preview(self):
        path = self.app.directory/'research-preview.json'
        path.write_text(json.dumps({'session':'old','changes':{}}))
        self.app.remember_report(path)
        self.assertFalse(self.app.preview_records({})['available'])

    def test_http_requires_local_host_token_and_same_origin(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.app=self.app
        self.app.origin=f'http://127.0.0.1:{server.server_port}'
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            def call(path,body=None,headers=None):
                return request.urlopen(request.Request(self.app.origin+path,
                    data=json.dumps(body).encode() if body is not None else None,headers=headers or {}))
            with self.assertRaises(error.HTTPError) as failed:call('/api/state')
            self.assertEqual(failed.exception.code,403)
            with self.assertRaises(error.HTTPError):call('/api/preview')
            headers={'X-Workbench-Token':self.app.token,'Content-Type':'application/json','Origin':'https://outside.example'}
            with self.assertRaises(error.HTTPError):call('/api/step',{'step':3},headers)
            headers['Origin']=self.app.origin
            with call('/api/step',{'step':3},headers) as response:self.assertEqual(response.status,200)
            with call('/api/state',headers={'X-Workbench-Token':self.app.token}) as response:
                self.assertEqual(json.load(response)['step'],3)
            with self.assertRaises(error.HTTPError):call('/api/state',headers={'Host':'outside.example','X-Workbench-Token':self.app.token})
        finally:
            server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
