import asyncio
import os
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, Body, HTTPException
from fastapi.responses import JSONResponse
from typing import Any
from .examples import EXAMPLES
URLS = {key:os.getenv(key.upper()+'_URL', 'http://'+key+':8000') for key in ['forecast','sizing','anomaly']}
@asynccontextmanager
async def lifespan(app):
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0), trust_env=False) as client:
        app.state.client = client
        yield
app = FastAPI(title='Solar AI Platform Gateway', lifespan=lifespan)
async def forward(service, path, payload=None):
    try:
        response = await app.state.client.request('GET' if payload is None else 'POST', URLS[service]+path, json=payload)
    except httpx.TimeoutException as exc:
        raise HTTPException(504, detail=service+' timed out') from exc
    except httpx.RequestError as exc:
        raise HTTPException(503, detail=service+' is unavailable') from exc
    try: content = response.json()
    except ValueError:
        raise HTTPException(502, detail=service+' returned an invalid response')
    return JSONResponse(status_code=response.status_code, content=content)
@app.get('/health')
def health(): return {'status':'ok'}
@app.get('/services')
async def services():
    async def check(name):
        try:
            result = await app.state.client.get(URLS[name]+'/health', timeout=3.0)
            return name, 'ok' if result.status_code == 200 else 'unhealthy'
        except httpx.RequestError: return name, 'unavailable'
    return dict(await asyncio.gather(*(check(name) for name in URLS)))
@app.post('/forecast', response_model=dict, summary='Forecast — real service')
async def forecast(data: dict[str, Any] = Body(..., examples=[EXAMPLES['forecast']])): return await forward('forecast','/predict',data)
@app.post('/sizing', response_model=dict, summary='Sizing — real service')
async def sizing(data: dict[str, Any] = Body(..., examples=[EXAMPLES['sizing']])): return await forward('sizing','/predict',data)
@app.post('/anomaly', response_model=dict, summary='Anomaly — real service')
async def anomaly(data: dict[str, Any] = Body(..., examples=[EXAMPLES['anomaly']])): return await forward('anomaly','/predict',data)
@app.get('/forecast/features')
async def forecast_features(): return await forward('forecast','/features')
@app.get('/anomaly/features')
async def anomaly_features(): return await forward('anomaly','/features')
@app.get('/sizing/example')
async def sizing_example(): return await forward('sizing','/example')

# Insert media-type examples after schema generation so explicit null history
# values survive FastAPI's OpenAPI serialization and can be pasted into Swagger.
def openapi_with_examples():
    if app.openapi_schema is None:
        from fastapi.openapi.utils import get_openapi
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        for name, payload in EXAMPLES.items():
            media = schema['paths']['/' + name]['post']['requestBody']['content']['application/json']
            media['schema'].pop('examples', None)
            media['examples'] = {'model_input': {'summary': name.title() + ' model inputs', 'value': payload}}
        app.openapi_schema = schema
    return app.openapi_schema

app.openapi = openapi_with_examples

@app.post('/forecast/forward',response_model=dict)
async def forward_forecast(data:dict[str,Any]=Body(...)):
    return await forward('forecast','/forward',data)

@app.get('/forecast/forward/example')
async def forward_forecast_example():return await forward('forecast','/forward/example')

@app.get('/forecast/forward/report')
async def forward_forecast_report():return await forward('forecast','/forward/report')
