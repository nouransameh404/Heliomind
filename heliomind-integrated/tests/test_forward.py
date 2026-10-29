import json,sys,unittest
from pathlib import Path
from datetime import datetime,timedelta
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from forecast.main import app
from forecast.forward_engine import vector
EXAMPLE=json.loads((ROOT/'forecast/models/forward48/forward_example.json').read_text())
class ForwardTests(unittest.TestCase):
 def test_horizons_periods_energy_and_references(self):
  with TestClient(app) as client:
   for horizon in [24,48]:
    payload={**EXAMPLE,'horizon_hours':horizon};r=client.post('/forward',json=payload)
    self.assertEqual(r.status_code,200,r.text);result=r.json();self.assertEqual(len(result['points']),horizon)
    origin=datetime.fromisoformat(EXAMPLE['history'][-1]['timestamp'])+timedelta(hours=1)
    self.assertEqual(result['origin'],origin.isoformat())
    self.assertAlmostEqual(result['total_energy_kwh'],sum(p['predicted_energy_kwh'] for p in result['points']),places=4)
    for i,p in enumerate(result['points']):
     self.assertEqual(datetime.fromisoformat(p['period_start']),origin+timedelta(hours=i))
     self.assertEqual(datetime.fromisoformat(p['period_end']),origin+timedelta(hours=i+1))
     self.assertLess(datetime.fromisoformat(p['reference_history_timestamp']),origin)
     self.assertGreaterEqual(p['predicted_power_kw'],0)
 def test_bad_history_rejected(self):
  with TestClient(app) as client:
   for mutate in ['short','gap','duplicate','bad_horizon','negative','timezone']:
    d=json.loads(json.dumps(EXAMPLE))
    if mutate=='short':d['history']=d['history'][:47]
    if mutate=='gap':d['history'].pop(5)
    if mutate=='duplicate':d['history'][5]['timestamp']=d['history'][4]['timestamp']
    if mutate=='bad_horizon':d['horizon_hours']=12
    if mutate=='negative':d['history'][0]['power_kw']=-1
    if mutate=='timezone':d['history'][0]['timestamp']+='Z'
    self.assertEqual(client.post('/forward',json=d).status_code,422,mutate)
 def test_first24_agree_and_legacy_retained(self):
  with TestClient(app) as client:
   a=client.post('/forward',json={**EXAMPLE,'horizon_hours':24}).json()['points']
   b=client.post('/forward',json=EXAMPLE).json()['points'][:24]
   self.assertEqual(a,b)
   old=json.loads((ROOT/'examples/forecast.json').read_text());self.assertEqual(client.post('/predict',json=old).status_code,200)
 def test_features_match_training(self):
  sys.path.insert(0,str(ROOT.parents[0]/'scripts'));from train_forward import features,FEATURES
  history=[r['power_kw'] for r in EXAMPLE['history']];origin=datetime.fromisoformat(EXAMPLE['history'][-1]['timestamp'])+timedelta(hours=1)
  for h in [1,24,25,48]:np.testing.assert_allclose(vector(history,origin,h),features(history,origin,h),rtol=1e-7)
  self.assertEqual(len(vector(history,origin,1)),len(FEATURES))
if __name__=='__main__':unittest.main(verbosity=2)
