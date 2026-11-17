import json,re,subprocess,tempfile,unittest
from pathlib import Path
from src.analysis.knowledge_display_projection import apply_knowledge_display_projection
from src.analysis.system_qa_decisions import apply_system_qa_decisions,set_system_override
from src.analysis.page_renderer import build_page_v3

class SystemQaTests(unittest.TestCase):
 def setUp(self):
  self.projection={'schema_version':1,'status':'reviewed_knowledge_display_projection','items':[{'knowledge_id':'K','qas':[{'qa_id':'K::q01','question':'问题','answer':'结论','confidence':'medium','lifecycle':'durable','time_context':'','evidence_refs':['T1']}]}]}
  self.units=apply_knowledge_display_projection([{'knowledge_id':'K','initial_state':'queue'}],self.projection)
  self.fp=self.units[0]['display_qas'][0]['qa_fingerprint']
  self.doc={'schema_version':1,'status':'reviewed_system_qa_decisions','items':[{'qa_id':'K::q01','qa_fingerprint':self.fp,'decision':'knowledge','reason':'具体机制可用'}]}
 def test_overlay_stale_and_no_mutation(self):
  self.assertEqual(apply_system_qa_decisions(self.units,self.doc)[0]['display_qas'][0]['system_decision'],'knowledge')
  self.assertNotIn('system_decision',self.units[0]['display_qas'][0])
  self.doc['items'][0]['qa_fingerprint']='old'
  self.assertNotIn('system_decision',apply_system_qa_decisions(self.units,self.doc)[0]['display_qas'][0])
 def test_duplicate_and_timebound_rejected(self):
  self.doc['items']*=2
  with self.assertRaises(ValueError):apply_system_qa_decisions(self.units,self.doc)
  self.doc['items']=self.doc['items'][:1];self.units[0]['display_qas'][0]['lifecycle']='time_bound'
  with self.assertRaises(ValueError):apply_system_qa_decisions(self.units,self.doc)
 def test_override_reload_keeps_user_state_separate(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'knowledge-display-projection-v1.json').write_text(json.dumps(self.projection));(p/'system-qa-decisions-v1.json').write_text(json.dumps(self.doc))
   original=(p/'system-qa-decisions-v1.json').read_bytes();set_system_override(p,'K::q01',True,self.fp)
   overrides=json.loads((p/'system-qa-overrides-v1.json').read_text())
   self.assertTrue(apply_system_qa_decisions(self.units,self.doc,overrides)[0]['display_qas'][0]['system_suppressed'])
   self.assertFalse((p/'display-review-decisions-v1.json').exists());self.assertEqual(original,(p/'system-qa-decisions-v1.json').read_bytes())
   set_system_override(p,'K::q01',False,self.fp)
   self.assertFalse(json.loads((p/'system-qa-overrides-v1.json').read_text())['items'][0]['suppressed'])
   with self.assertRaises(ValueError):set_system_override(p,'K::other',True,self.fp)
   with self.assertRaises(ValueError):set_system_override(p,'K::q01',True,'old')
 def test_renderer_real_js_human_priority_retract(self):
  units=apply_system_qa_decisions(self.units,self.doc);html=build_page_v3([],[],{},units)
  script=re.findall(r'<script(?: [^>]*)?>(.*?)</script>',html,re.S)[-1].split("document.addEventListener('keydown'")[0]
  data={'cardData':'[]','blackwordData':'[]','dossierData':'{}','knowledgeData':json.dumps(units)}
  js='const data='+json.dumps(data)+'; const storage=new Map(); const localStorage={getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)}; const document={addEventListener:()=>{},getElementById:id=>({textContent:data[id]||"",addEventListener:()=>{}})};\n'+script
  js+='''\nconst assert=require('assert'),r=qaById['K::q01'];assert.equal(inheritedQaDecision(r.unit,r.qa),'knowledge');r.qa.system_suppressed=true;assert.equal(inheritedQaDecision(r.unit,r.qa),'');r.qa.human_decision='discard';assert.equal(inheritedQaDecision(r.unit,r.qa),'discard');r.qa.system_suppressed=false;assert.equal(inheritedQaDecision(r.unit,r.qa),'discard');r.qa.human_decision='';r.unit.v3_reviewed_decision='discard';assert.equal(inheritedQaDecision(r.unit,r.qa),'discard');assert.equal(humanQaDecision(r.unit,r.qa),'discard');'''
  result=subprocess.run(['node','-e',js],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
