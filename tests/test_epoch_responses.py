"""Regression checks for independent dating and lossless response extraction."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from parse_epoch_responses import compile_rules, date_selection, extract, database, match_line, epoch_for

CATALOGUE = json.loads((ROOT/'research/date_indicators.json').read_text())
RULES = json.loads((ROOT/'research/epoch-responses/rules.json').read_text())
COMPILED = compile_rules(RULES)


def source(identity):
    return {'id': identity, 'calibration': 'independent', 'dependencies': [], 'url': ''}


def record(identity, filename, start, end, day='1995-01-01'):
    return {'record_id': identity, 'source_file': filename, 'title': identity,
            'source_line_range': [start,end], 'posted_date': '2026-01-01',
            'event_date': {'earliest': day, 'latest': day, 'display': day,
                           'confidence': 'high', 'basis': 'Internal dated header.'}}


class EpochResponseTests(unittest.TestCase):
    def test_dates_require_independent_bounded_evidence(self):
        r = record('a','a.txt',1,1); s = source('a')
        self.assertEqual(date_selection(r,s,CATALOGUE['epochs'])[0],'v')
        r['event_date']['alternative']='1997-01-01'
        self.assertIsNone(date_selection(r,s,CATALOGUE['epochs'])[0]); del r['event_date']['alternative']
        s['dependencies']=['shadows']; self.assertIsNone(date_selection(r,s,CATALOGUE['epochs'])[0]);s['dependencies']=[]
        s['calibration']='other-indicators';self.assertIsNone(date_selection(r,s,CATALOGUE['epochs'])[0]);s['calibration']='independent'
        r['event_date']['confidence']='medium-high';self.assertIsNone(date_selection(r,s,CATALOGUE['epochs'])[0])
        r['event_date']['confidence']='high';r['event_date']['earliest']=None
        self.assertIsNone(date_selection(r,s,CATALOGUE['epochs'])[0])
        self.assertIsNone(epoch_for('1996-02-01','1996-04-01',CATALOGUE['epochs']))

    def test_chat_does_not_create_fake_game_output(self):
        hits=match_line("Bob narrates 'You are dead! Sorry...'",COMPILED)
        self.assertEqual(len(hits),1);self.assertEqual(hits[0]['rule']['category'],'Communication')
        self.assertFalse(match_line('#Ok. {tt} aliases {t Bob}.',COMPILED))
        self.assertFalse(match_line("Bob says 'Alice tells you hi'",COMPILED)[0]['rule']['id']=='speech-tell')

    def test_punctuation_spelling_and_adverbs_survive(self):
        old=match_line('Congratulations!! This is the first time you\'ve killed it !',COMPILED)[0]
        new=match_line('Congratulations! This is the first time you\'ve killed it!',COMPILED)[0]
        self.assertNotEqual(old['template'],new['template'])
        a=match_line('You are dead!  Sorry...',COMPILED)[0]
        b=match_line('You are dead! Sorry...',COMPILED)[0]
        self.assertNotEqual(a['template'],b['template'])
        a=match_line("You strongly slash *Bob*'s left arm hard.",COMPILED)[0]
        self.assertEqual(a['viewpoint'],'actor');self.assertIn('strongly slash',a['template'])
        b=match_line("You slash *Fred*'s right arm hard.",COMPILED)[0]
        self.assertNotEqual(a['template'],b['template'])
        c=match_line("You slash *Bob*'s left leg hard.",COMPILED)[0]
        self.assertEqual(b['template'],c['template'])
        a=match_line('The present Tan Istar, Lord of the Istari Council is not defined.',COMPILED)[0]
        self.assertIn('not defined',a['template'])

    def test_raw_context_boundaries_and_repeated_lines(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'corpus').mkdir();(root/'sources/raw_logs').mkdir(parents=True)
            lines=['* HP:Fine>You nod solemnly.','You nod solemnly.',
                   "Bob narrates 'You are dead! Sorry...'",'You are dead! Sorry...',
                   'You nod solemnly.','2002/06/12 05:21, Author:',
                   'You are hungry.']
            (root/'sources/raw_logs/joined.txt').write_text('\n'.join(lines)+'\n')
            records=[record('early','joined.txt',1,3),record('late','joined.txt',4,7,'1997-01-01')]
            (root/'corpus/mume_historical_logs_corpus_v1.0_consolidated.json').write_text(json.dumps({'records':records}))
            cat={'epochs':CATALOGUE['epochs'],'sources':[source('early'),source('late')]}
            snap=extract(root,cat,RULES)
            nod=next(f for f in snap['forms'] if f['template']=='You nod solemnly.')
            obs=[o for o in snap['observations'] if o['form_id']==nod['form_id']]
            self.assertEqual(len(obs),2);self.assertEqual(obs[0]['occurrences'],2)
            self.assertEqual(obs[0]['raw_line'],lines[0]);self.assertEqual(obs[0]['prompt'],'* HP:Fine>')
            self.assertEqual(obs[0]['last_line'],2)
            self.assertFalse(any(f['template']=='You are hungry.' for f in snap['forms']))
            dead=next(f for f in snap['forms'] if f['template']=='You are dead! Sorry...')
            self.assertEqual([o['source_id'] for o in snap['observations'] if o['form_id']==dead['form_id']],['late'])
            self.assertEqual([s['epoch'] for s in snap['selected_sources']],['v','vi'])
            self.assertEqual(snap,extract(root,cat,RULES))
            dbpath=root/'snapshot.sqlite3';database(snap,RULES,dbpath)
            with sqlite3.connect(dbpath) as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertEqual(db.execute('SELECT DISTINCT status FROM observations').fetchall(),[('needs_review',)])
                self.assertEqual(db.execute('SELECT COUNT(*) FROM epoch_forms WHERE response="Nod"').fetchone()[0],2)
            records[1].pop('source_line_range')
            (root/'corpus/mume_historical_logs_corpus_v1.0_consolidated.json').write_text(json.dumps({'records':records}))
            with self.assertRaisesRegex(ValueError,'logical-log boundaries'):
                extract(root,cat,RULES)

    def test_duplicate_segments_do_not_add_support(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'corpus').mkdir();(root/'sources/raw_logs').mkdir(parents=True)
            (root/'sources/raw_logs/joined.txt').write_text('You nod solemnly.\nYou nod solemnly.\n')
            records=[record('one','joined.txt',1,1),record('copy','joined.txt',2,2)]
            (root/'corpus/mume_historical_logs_corpus_v1.0_consolidated.json').write_text(json.dumps({'records':records}))
            snap=extract(root,{'epochs':CATALOGUE['epochs'],'sources':[source('one'),source('copy')]},RULES)
            self.assertEqual(len(snap['selected_sources']),1)
            self.assertIn('Duplicate',snap['deferred_sources'][0]['reason'])


if __name__=='__main__':
    unittest.main()
