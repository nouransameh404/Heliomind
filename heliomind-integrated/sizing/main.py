from typing import Any
from fastapi import FastAPI, HTTPException, Body
from .rules import size_system, inputs
app = FastAPI(title='Solar Sizing Service')
@app.get('/health')
def health(): return {'status':'ok'}
@app.get('/example')
def example(): return inputs
@app.post('/predict')
def predict(data: dict[str, Any] = Body(...)):
    try: return size_system(data)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, detail=str(exc)) from exc
