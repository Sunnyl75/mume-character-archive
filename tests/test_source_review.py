"""Source-wide coverage, human revisions, provenance and public projections."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from deck_workbench import Workbench, table
from import_historical_evidence import Importer
from historical_views import build_history
import source_review


class SourceReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.root = self.folder / 'archive'
        shutil.copytree(ROOT / 'data/working', self.root / 'data/working')
        (self.root/'scripts').mkdir()
        for name in ('import_historical_evidence.py','publish_deck.py','build_whois_queue.py'):
            (self.root/'scripts'/name).touch()
        self.app = Workbench(self.root, self.folder/'state')
        self.input = self.folder/'input';self.input.mkdir()
        self.path = self.input/'corpus.json'
        self.path.write_text(json.dumps({'schema_version':'mume_historical_logs_corpus/1.0','records':[
            {'record_id':'log_review','title':'Eazy at the Ford','source_file':'original.txt',
             'credited_observer':'Eazy','source_line_range':[1,4],
             'principal_characters':['Eazy','Archie','Iqpi'],
             'event_date':{'display':'1997; uncertain'},
             'deaths':[{'character':'Eazy','evidence':'index title and observer context'},
                       {'character':'Maybe','evidence':'outcome uncertain'}],
             'key_findings':['stored call lightning'], 'map_context':{'rooms':['Ford']},
             'extraction_status':'summary; exact death line pending'}]}))
        (self.input/'original.txt').write_text('Logged by Eazy\nArchie attacks\nAn elf casts\nYou are dead! Sorry...\n')
        imp=Importer(self.root);imp.ingest(self.path,Path('corpus.json'));imp.finish()
        self.sid=imp.inputs[0]['source_id']
        self.app.data['research_path']=str(self.input)
        p=self.app.directory/'research-preview.json';p.write_text(json.dumps(imp.preview_details()));self.app.remember_report(p)
        with contextlib.redirect_stdout(io.StringIO()):imp.apply(self.input,'review_fixture')
        self.log='log_review'

    def tearDown(self):
        self.temp.cleanup()

    def source(self,scope='archive'):
        return self.app.source_facts(scope,self.sid,self.log)

    def death(self):
        return next(f for f in self.source()['facts'] if f['kind']=='death')

    def decision(self,fact,**other):
        return {'source_id':self.sid,'log_id':self.log,'id':fact['id'],'version':fact['version'],**other}

    def revise(self):
        fact=self.death()
        source_review.save(self.app,[self.decision(fact,action='revise',status='accepted',changes={
            'confidence':'high','basis':'Observer identified in heading; exact death line verified.',
            'citation':{'file':'original.txt','start':4,'end':4,'quote':'You are dead! Sorry...'},
            'notes':'PRIVATE_REVIEW_NOTE'})])
        return fact

    def test_source_view_includes_all_context_not_only_review_queue(self):
        for scope in ('preview','archive'):
            facts=self.source(scope)['facts']
            text=json.dumps(facts)
            for expected in ('Eazy','Archie','Iqpi','stored call lightning','Ford','credited observer',
                             'event date','outcome uncertain','extraction status'):
                self.assertIn(expected,text)
            self.assertEqual(sum(f['kind']=='death' for f in facts),1)
            self.assertGreater(len(facts),10)
        self.assertNotIn('stored call lightning',json.dumps(self.app.public_state()))
        original=self.app.original_for_source('archive',self.sid,self.log)
        self.assertEqual(original['documents'][0]['name'],'original.txt')

    def test_revision_updates_confidence_keeps_raw_evidence_and_survives_reimport(self):
        original=(self.root/'data/working/evidence.csv').read_bytes()
        fact=self.revise()
        revised=self.death()
        self.assertEqual((revised['confidence'],revised['status']),('high','accepted'))
        self.assertEqual(revised['citation']['start'],4)
        self.assertEqual(len(revised['history']),1)
        self.assertEqual(revised['history'][0]['before']['confidence'],'low')
        self.assertEqual((self.root/'data/working/evidence.csv').read_bytes(),original)
        group=next(g for g in self.app.claim_groups('archive')['groups'] if g['kind']=='death')
        self.assertEqual(group['confidence'],'high')
        self.assertIn('Human review',group['reasons'][0])
        again=Importer(self.root);again.ingest(self.path,Path('corpus.json'));again.finish()
        self.assertFalse(again.changes,dict(again.changes))
        self.assertEqual(again.tables['historical_events'][0]['review_status'],'accepted')
        self.assertEqual(again.tables['historical_events'][0]['confidence'],'high')
        with self.assertRaisesRegex(ValueError,'changed since'):
            source_review.save(self.app,[self.decision(fact,action='reject')])

    def test_attackers_have_separate_confidence_and_public_filtering(self):
        original=self.revise()
        for who,rating,status in [('Archie','high','accepted'),('Iqpi','medium','accepted'),('Uncertain','low','needs_review')]:
            source_review.save(self.app,[{'source_id':self.sid,'log_id':self.log,'action':'add','status':status,
                'changes':{'kind':'attacker','subject':'Eazy','value':who,'about':original['id'],
                           'confidence':rating,'basis':'Named attack in source context.',
                           'notes':'PRIVATE_CONTEXT_NOTE','citation':{'quote':'Archie attacks','start':2,'end':2}}}])
        public=build_history(self.root)
        event=next(h['deaths'][0] for h in public.values() if h['deaths'])
        self.assertEqual([(f['value'],f['confidence']) for f in event['details']],[('Archie','high'),('Iqpi','medium')])
        self.assertFalse(any(f['kind']=='killer' for f in event['details']))
        self.assertNotIn('PRIVATE_',json.dumps(public))
        self.assertIn('Uncertain',[f['value'] for f in self.source()['facts']])
        self.assertIn('Uncertain',[r['character_name'] for r in table(self.root,'whois_queue')])

    def test_simple_accept_keeps_content_and_rating_and_records_history(self):
        fact=self.death()
        source_review.save(self.app,[self.decision(fact,action='accept')])
        accepted=self.death()
        self.assertEqual((accepted['confidence'],accepted['value']),('low','1'))
        self.assertEqual(accepted['history'][0]['action'],'accept')
        source_review.save(self.app,[self.decision(accepted,action='reject')])
        self.assertEqual(self.death()['status'],'rejected')
        self.assertTrue(all(not h['deaths'] for h in build_history(self.root).values()))

    def test_cross_source_edits_and_bad_citations_are_atomic(self):
        fact=self.death()
        before={p.name:p.read_bytes() for p in (self.root/'data/working').glob('*.csv')}
        invalid=self.decision(fact,action='revise',changes={'basis':'Reviewed','citation':{'start':4,'end':2}})
        with self.assertRaisesRegex(ValueError,'reversed'):source_review.save(self.app,[invalid])
        with self.assertRaises(ValueError):source_review.save(self.app,[{**self.decision(fact,action='accept'),'source_id':'wrong'}])
        self.assertEqual(before,{p.name:p.read_bytes() for p in (self.root/'data/working').glob('*.csv')})

    def test_missing_death_can_be_added_without_rewriting_the_import(self):
        source_review.save(self.app,[{'source_id':self.sid,'log_id':self.log,'action':'add','status':'accepted',
            'changes':{'kind':'death','subject':'Missed','value':'1','confidence':'high',
                       'basis':'Explicit named death output found during completeness review.',
                       'citation':{'quote':'Missed is dead! R.I.P.','start':8,'end':8}}}])
        fact=next(f for f in self.source()['facts'] if f['subject']=='Missed')
        self.assertTrue(fact['id'].startswith('historical_events:'))
        self.assertEqual(fact['status'],'accepted')
        self.assertEqual(len(fact['history']),1)
        again=Importer(self.root);again.ingest(self.path,Path('corpus.json'));again.finish()
        self.assertFalse(again.changes,dict(again.changes))
        self.assertEqual(len(again.tables['historical_events']),2)
        self.assertEqual(sum(len(h['deaths']) for h in build_history(self.root).values()),1)

    def test_conflicting_acceptance_leaves_all_tables_untouched(self):
        path=self.input/'players.json'
        path.write_text(json.dumps({'schema_version':'mume_player_character_evidence/0.1','players':[
            {'pName':'pReviewOne','characters_as_written':['SharedReview'],'confidence':'high'},
            {'pName':'pReviewTwo','characters_as_written':['SharedReview'],'confidence':'high'}]}))
        imp=Importer(self.root);imp.ingest(path,Path('players.json'));imp.finish();imp.write_tables(self.root)
        sid=imp.inputs[0]['source_id']
        facts=[f for f in self.app.source_facts('archive',sid)['facts'] if f['kind']=='link']
        def decision(f):return {'source_id':sid,'log_id':'','id':f['id'],'action':'accept'}
        source_review.save(self.app,[decision(facts[0])])
        before={p.name:p.read_bytes() for p in (self.root/'data/working').glob('*.csv')}
        with self.assertRaisesRegex(ValueError,'conflicting accepted owner'):
            source_review.save(self.app,[decision(facts[1])])
        self.assertEqual(before,{p.name:p.read_bytes() for p in (self.root/'data/working').glob('*.csv')})

    def test_missing_trophy_and_player_association_create_distinct_facts(self):
        player=table(self.root,'players')[0]['player_id']
        for changes in ({'kind':'trophy','subject':'Eazy','object':'TrophyVictim','value':'2'},
                        {'kind':'link','subject':'ReviewAlt','object':player,'value':''}):
            source_review.save(self.app,[{'source_id':self.sid,'log_id':self.log,'action':'add','status':'needs_review',
                'changes':{**changes,'confidence':'medium','basis':'Explicit finding entered during source review.',
                           'citation':{}}}])
        facts=self.source()['facts']
        self.assertTrue(any(f['kind']=='link' and f['subject']=='ReviewAlt' for f in facts))
        self.assertTrue(any(f['kind']=='trophy' and f['object']=='TrophyVictim' and f['value']=='2' for f in facts))
        self.assertTrue(all(not h['trophies'] for h in build_history(self.root).values()))

    def test_failed_replacement_rolls_back_facts_projections_and_history(self):
        before={p.name:p.read_bytes() for p in (self.root/'data/working').glob('*.csv')}
        replace=Path.replace;calls=0
        def fail_second(path,dest):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('simulated write failure')
            return replace(path,dest)
        with patch.object(Path,'replace',fail_second),self.assertRaises(OSError):self.revise()
        self.assertEqual(before,{p.name:p.read_bytes() for p in (self.root/'data/working').glob('*.csv')})


if __name__=='__main__':unittest.main()
