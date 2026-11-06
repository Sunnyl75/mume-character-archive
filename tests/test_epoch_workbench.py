"""Exercise extraction, persistent review and the actual comparison handoff."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from deck_workbench import Workbench, atomic_json, table
from import_historical_evidence import Importer
import source_review
import epoch_workbench


class EpochWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.root = self.folder / 'archive'
        shutil.copytree(ROOT / 'data/working', self.root / 'data/working')
        shutil.copytree(ROOT / 'research', self.root / 'research')
        (self.root / 'scripts').mkdir()
        for name in ('import_historical_evidence.py', 'publish_deck.py', 'build_whois_queue.py'):
            (self.root / 'scripts' / name).touch()
        self.app = Workbench(self.root, self.folder / 'session')
        self.input = self.folder / 'input'; self.input.mkdir()
        corpus = {'schema_version':'mume_historical_logs_corpus/1.0', 'records':[
            {'record_id':'review_log', 'title':'Independent fixture', 'source_file':'original.txt',
             'source_url':'https://example.org/original-log', 'credited_observer':'Observer',
             'event_date':{'earliest':'1995-01-12', 'latest':'1995-01-12', 'display':'12 Jan 1995',
                           'confidence':'high', 'basis':'Contemporaneous dated game transcript'},
             'source_line_range':[1,4]}]}
        self.path = self.input / 'corpus.json'; self.path.write_text(json.dumps(corpus))
        (self.input / 'original.txt').write_text("You nod solemnly.\nOther nods solemnly.\nOther smiles at you.\nYou nod solemnly.\n")
        imp = Importer(self.root); imp.ingest(self.path, Path('corpus.json')); imp.finish()
        self.sid = imp.inputs[0]['source_id']; self.log = 'review_log'
        with contextlib.redirect_stdout(io.StringIO()): imp.apply(self.input, 'epoch_fixture')

    def tearDown(self): self.temp.cleanup()

    def response(self):
        return next(f for f in self.app.source_facts('archive', self.sid, self.log)['facts']
                    if f['kind'] == 'response' and f['response']['viewpoint'] == 'Actor')

    def decide(self, fact, action, **kw):
        source_review.save(self.app, [{'source_id': self.sid, 'log_id': self.log, 'id': fact['id'],
                                     'version': fact['version'], 'action': action, **kw}])

    def scan(self): return epoch_workbench.scan(self.app, self.sid, self.log)

    def accept(self):
        self.scan(); fact = self.response()
        meta = {**fact['response'], 'calibration':'independent', 'date_confidence':'high',
                'date_basis':'Explicit date in original transcript, independent of wording'}
        self.decide(fact, 'revise', status='accepted', changes={
            'response':meta, 'confidence':'high', 'basis':'Game output and perspective checked',
            'notes':'PRIVATE_EPOCH_NOTE'})
        return self.response()

    def export(self, base=None):
        with contextlib.redirect_stdout(io.StringIO()):
            report = epoch_workbench.export(self.app, base or self.root/'research/date_indicators.json')
        output = self.app.directory/'epoch-export/epoch-comparison-catalogue.json'
        return report, json.loads(output.read_text())

    def test_scan_deduplicates_repetition_separates_pov_and_preserves_rejection(self):
        added, found = self.scan()
        facts = [f for f in source_review.saved_facts(self.root).values() if f['kind']=='response']
        self.assertGreaterEqual(found,3)
        self.assertEqual(added,found)
        self.assertEqual({f['response']['viewpoint'] for f in facts}, {'Actor','Target','Room'})
        self.assertEqual(sum(f['value']=='You nod solemnly.' for f in facts),1)
        self.assertTrue(all(f['status']=='needs_review' for f in facts))
        fact=self.response(); self.decide(fact,'reject')
        self.assertEqual(self.scan(),(0,found))
        self.assertEqual(self.response()['status'],'rejected')
        original=self.app.original_for_source('archive',self.sid,self.log,self.response()['id'])
        read=self.app.source_text(original['documents'][0]['ref'],{})
        self.assertEqual(read['citation'],[1,1])
        self.assertEqual([l['number'] for l in read['lines'] if l['highlight']],[1])
        self.assertEqual(len(self.response()['history']),2)  # extraction and review

    def test_unrated_date_is_not_upgraded_by_a_matching_response(self):
        self.scan(); fact=self.response()
        self.assertEqual(fact['response']['calibration'],'unresolved')
        self.decide(fact,'accept')
        report, data=self.export()
        self.assertEqual(report['exported'],0)
        self.assertEqual(len(report['deferred']),1)
        self.assertFalse(any(a.get('fact_id')==fact['id'] for i in data['indicators'] for a in i['attestations']))

    def test_export_is_accepted_only_preserves_raw_citation_and_excludes_private_notes(self):
        fact=self.accept()
        before={p.name:p.read_bytes() for p in (self.root/'data/working').glob('*.csv')}
        report,data=self.export()
        self.assertEqual(report['exported'],1)
        observations=[a for i in data['indicators'] for a in i['attestations'] if a.get('fact_id')]
        self.assertEqual(len(observations),1)
        obs=observations[0]
        self.assertEqual(obs['quote'],'You nod solemnly.')
        self.assertEqual(obs['display_template'],'You nod solemnly.')
        self.assertEqual((obs['line_start'],obs['viewpoint']),(1,'Actor'))
        source=next(s for s in data['sources'] if s['id']==obs['source_id'])
        self.assertEqual(source['url'],'https://example.org/original-log')
        self.assertEqual(source['date_start'],'1995-01-12')
        self.assertNotIn('PRIVATE_EPOCH_NOTE',json.dumps(data))
        self.assertEqual(before,{p.name:p.read_bytes() for p in (self.root/'data/working').glob('*.csv')})
        self.assertTrue((self.app.directory/'epoch-export/MUME_Date_Indicators.html').exists())

    def test_loading_previous_export_updates_revisions_and_removes_rejected_observations(self):
        fact=self.accept(); _,data=self.export()
        data['title']='User-edited comparison title'
        base=self.folder/'website-catalogue.json'; atomic_json(base,data)
        self.decide(fact,'revise',status='accepted',changes={'value':'You nod solemnly!', 'basis':'Checked punctuation against retained source'})
        _,next_data=self.export(base)
        observations=[a for i in next_data['indicators'] for a in i['attestations'] if a.get('fact_id')]
        self.assertEqual(len(observations),1)
        self.assertEqual(observations[0]['display_template'],'You nod solemnly!')
        self.assertEqual(next_data['title'],'User-edited comparison title')
        atomic_json(base,next_data); self.decide(self.response(),'reject')
        _,last=self.export(base)
        self.assertFalse(any(a.get('fact_id')==fact['id'] for i in last['indicators'] for a in i['attestations']))
        self.assertEqual(last['title'],'User-edited comparison title')

    def test_reversed_dates_and_circular_independent_claim_are_atomic(self):
        self.scan();fact=self.response()
        before=(self.root/'data/working/research_facts.csv').read_bytes()
        for meta in ({**fact['response'],'date_start':'1998-01-01','date_end':'1995-01-01'},
                     {**fact['response'],'calibration':'independent','date_basis':'Uses shadow clue','dependencies':['shadows']}):
            with self.assertRaises(ValueError):
                self.decide(fact,'revise',status='accepted',changes={'response':meta,'basis':'Checked'})
        self.assertEqual(before,(self.root/'data/working/research_facts.csv').read_bytes())

    def test_reimport_keeps_response_decisions_and_sources_without_groups_are_accessible(self):
        self.assertTrue(any(s['id']==self.sid for s in self.app.review_rows()['sources']))
        fact=self.accept()
        imp=Importer(self.root); imp.ingest(self.path,Path('corpus.json')); imp.finish()
        with contextlib.redirect_stdout(io.StringIO()):imp.apply(self.input,'again')
        self.assertEqual(self.response()['status'],'accepted')
        self.assertEqual(self.response()['id'],fact['id'])
        self.assertEqual(len([g for g in self.app.review_rows()['groups'] if g['kind']=='response']),2)

    def test_existing_step_migrates_to_combined_whois_and_build_summary_is_named(self):
        folder=self.folder/'old-session';folder.mkdir()
        atomic_json(folder/'state.json',{'step':4})
        app=Workbench(self.root,folder)
        self.assertEqual(app.data['step'],2)
        atomic_json(app.directory/'build-baseline.json',{'characters':[{'id':'a','name':'Old','level':1}]})
        app.summarize_build({'characters':[{'id':'a','name':'Old','level':2},{'id':'b','name':'New'}]})
        changes=app.build_changes({'q':['Old']})
        self.assertEqual(changes['summary'],{'added':1,'updated':1})
        self.assertEqual(changes['records'][0]['fields'],['level'])


if __name__=='__main__':unittest.main()
