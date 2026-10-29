import sys,json,asyncio,math
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import httpx
from fastapi.testclient import TestClient
from forecast.main import app as forecast
from sizing.main import app as sizing
from anomaly.main import app as anomaly
from gateway.main import app as gateway
root=ROOT
clients={}
for name,app in [('forecast',forecast),('sizing',sizing),('anomaly',anomaly)]:
 c=TestClient(app);c.__enter__();clients[name]=c
 payload=json.loads((root/f'examples/{name}.json').read_text())
 response=c.post('/predict',json=payload)
 assert response.status_code==200,(name,response.text)
 result=response.json()
 (root/f'examples/{name}_response.json').write_text(json.dumps(result,indent=2))
 if name=='sizing':
  assert result['panels']['selected_count']==9
  assert math.isclose(result['annual_generation_kwh'],7593.3)
  payload['monthly_consumption_kwh']=-1
 else:payload={'rows':[]}
 assert c.post('/predict',json=payload).status_code==422
 print(name,'PASS',str(result)[:180])
async def run():
 async with gateway.router.lifespan_context(gateway):
  original=gateway.state.client
  async def dispatch(request):
   name=request.url.host
   if name not in clients:raise httpx.ConnectError('offline',request=request)
   response=clients[name].request(request.method,request.url.path,content=request.content,headers={'content-type':'application/json'})
   return httpx.Response(response.status_code,json=response.json())
  async with httpx.AsyncClient(transport=httpx.MockTransport(dispatch)) as routed:
   gateway.state.client=routed
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='http://test') as client:
    assert (await client.get('/services')).json()=={n:'ok' for n in clients}
    for name in clients:
     payload=json.loads((root/f'examples/{name}.json').read_text())
     assert (await client.post('/'+name,json=payload)).status_code==200
    assert (await client.post('/forecast',json={'rows':[]})).status_code==422
    saved=clients.pop('anomaly')
    assert (await client.post('/anomaly',json={'rows':[]})).status_code==503
    clients['anomaly']=saved
    assert (await client.post('/forecast',json=json.loads((root/'examples/forecast.json').read_text()))).status_code==200
  gateway.state.client=original
 print('Gateway routing, validation propagation and unavailable-service isolation PASS')
asyncio.run(run())
for c in clients.values():c.__exit__(None,None,None)
