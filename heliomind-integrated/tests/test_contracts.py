"""Regression tests for model schemas, Swagger examples and proxy handling."""
import asyncio
import json
from pathlib import Path
import sys
import unittest
import httpx
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from forecast.main import app as forecast
from anomaly.main import app as anomaly
from sizing.main import app as sizing
from gateway.main import app as gateway

class Contracts(unittest.TestCase):
    def test_swagger_samples_include_nulls(self):
        schema=TestClient(gateway).get('/openapi.json').json()
        for name in ['forecast','anomaly','sizing']:
            media=schema['paths']['/'+name]['post']['requestBody']['content']['application/json']
            self.assertEqual(media['examples']['model_input']['value'],json.loads((ROOT/f'examples/{name}.json').read_text()))

    def test_models_reject_wrong_feature_sets_and_preserve_order(self):
        f=json.loads((ROOT/'examples/forecast.json').read_text())
        a=json.loads((ROOT/'examples/anomaly.json').read_text())
        with TestClient(forecast) as fc,TestClient(anomaly) as ac:
            self.assertEqual(fc.post('/predict',json=a).status_code,422)
            self.assertEqual(ac.post('/predict',json=f).status_code,422)
            expected=fc.post('/predict',json=f).json()
            reordered={'rows':[dict(reversed(list(row.items()))) for row in f['rows']]}
            self.assertEqual(fc.post('/predict',json=reordered).json(),expected)
            self.assertEqual(ac.post('/predict',json=a).status_code,200)
            self.assertEqual(fc.post('/predict',json={'rows':f['rows'][:1]*1001}).status_code,422)
            self.assertEqual(ac.post('/predict',json={'rows':[]}).status_code,422)

    def test_anomaly_explanations_reconstruct_unchanged_score(self):
        import math
        payload=json.loads((ROOT/'examples/anomaly.json').read_text())
        with TestClient(anomaly) as client:
            data=client.post('/predict',json=payload).json()
            self.assertAlmostEqual(data['predictions'][0]['anomaly_probability'],0.016250232234597206,places=6)
            for row in data['predictions']:
                self.assertEqual(len(row['explanation']),18)
                margin=row['base_log_odds']+sum(x['shap_log_odds'] for x in row['explanation'])
                self.assertAlmostEqual(1/(1+math.exp(-margin)),row['anomaly_probability'],places=5)

    def test_sizing_handles_no_panels_and_invalid_json(self):
        payload=json.loads((ROOT/'examples/sizing.json').read_text())
        with TestClient(sizing) as client:
            self.assertEqual(client.post('/predict',content='{bad',headers={'content-type':'application/json'}).status_code,422)
            payload['usable_roof_m2']=1
            response=client.post('/predict',json=payload)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['status'],'no_panels_fit')
            self.assertIsNone(response.json()['finance'])

    def test_sizing_currency_contract_is_aud(self):
        payload=json.loads((ROOT/'examples/sizing.json').read_text())
        with TestClient(sizing) as client:
            response=client.post('/predict',json=payload)
            self.assertEqual(response.status_code,200)
            result=response.json()
            self.assertAlmostEqual(result['finance']['total_cost_aud'],5550.0)
            self.assertNotIn('_egp',json.dumps(result))
            payload['panel_price_egp']=payload.pop('panel_price_aud')
            self.assertEqual(client.post('/predict',json=payload).status_code,422)

    def test_gateway_timeout_and_bad_response(self):
        async def run():
            async with gateway.router.lifespan_context(gateway):
                original=gateway.state.client
                for failure,code in [('timeout',504),('bad_json',502)]:
                    async def route(request):
                        if failure=='timeout':raise httpx.ReadTimeout('timeout',request=request)
                        return httpx.Response(200,text='not json')
                    async with httpx.AsyncClient(transport=httpx.MockTransport(route)) as upstream:
                        gateway.state.client=upstream
                        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='http://test') as client:
                            response=await client.post('/forecast',json={'rows':[]})
                            self.assertEqual(response.status_code,code)
                gateway.state.client=original
        asyncio.run(run())

if __name__=='__main__':unittest.main(verbosity=2)
