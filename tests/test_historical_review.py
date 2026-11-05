import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from historical_review import assess, groups_for


def evidence(raw):return {'evidence_id':'e','source_id':'s','raw_text':json.dumps(raw)}


class ConfidenceReviewTests(unittest.TestCase):
    def test_high_label_without_original_statement_is_not_bulk_approved(self):
        row={'character_name':'One','player_id':'pOwner','status':'needs_review'}
        result=assess('link',row,evidence({'same_player_as':'pOwner','evidence_confidence':'high'}))
        self.assertEqual(result['source_confidence'],'high')
        self.assertEqual(result['confidence'],'medium')
        self.assertFalse(result['safe_to_accept'])
        self.assertTrue(any('not quoted' in r for r in result['reasons']))

    def test_explicit_list_can_be_high_but_owner_conflict_is_low(self):
        row={'character_name':'One','player_id':'pOwner','status':'needs_review'}
        raw=evidence({'characters_as_written':['One'],'confidence':'high'})
        self.assertTrue(assess('link',row,raw)['safe_to_accept'])
        conflict=assess('link',row,raw,other_owners=['pAnother'])
        self.assertEqual(conflict['confidence'],'low')
        self.assertFalse(conflict['safe_to_accept'])
        self.assertIn('pAnother',conflict['concerns'][0])

    def test_quote_and_summary_have_distinct_reasons_and_ratings(self):
        row={'character_name':'One'}
        quote=assess('death',row,evidence({'raw_line':'One is dead! R.I.P.','source_line':12,'confidence':'high'}))
        summary=assess('death',row,evidence({'evidence':'directly observed/recovered summary','confidence':'high'}))
        low=assess('death',row,evidence({'evidence':'index title and observer context'}))
        self.assertEqual([quote['confidence'],summary['confidence'],low['confidence']],['high','medium','low'])
        self.assertTrue(quote['safe_to_accept']);self.assertFalse(summary['safe_to_accept'])
        self.assertTrue(summary['concerns'])
        unknown=assess('death',row,evidence({}))
        self.assertEqual(unknown['confidence'],'unknown')

    def test_dated_claim_confidence_does_not_invent_an_exact_date(self):
        result=assess('death',{},evidence({'raw_line':'One is dead! R.I.P.','confidence':'high'}),
                      log={'date_basis':json.dumps({'preferred':'1996','alternative':'1994'}),'display_date':'1996 or 1994'})
        self.assertIn('Conflicting',result['date_note'])

    def test_many_characters_form_one_source_decision_group(self):
        links=[{'link_id':'link_hist_'+str(i),'player_id':'p','character_id':'c'+str(i),'character_name':'Name'+str(i),
                'main_handle':'pOwner','status':'needs_review','primary_evidence_id':'e'} for i in range(17)]
        result=groups_for(links,[],[evidence({'characters_as_written':['NameOne'],'confidence':'high'})],[],[{'source_id':'s','title':'Original page'}])
        self.assertEqual(len(result['groups']),1)
        self.assertEqual(len(result['groups'][0]['members']),17)
        self.assertEqual(result['summary']['supported'],1)
        self.assertEqual(result['summary']['claims'],17)


if __name__=='__main__':unittest.main()
