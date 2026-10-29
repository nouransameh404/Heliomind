import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import xgboost as xgb
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, create_model
from .forward_engine import ForwardRequest,ForwardResponse,load_bundle,predict_forward

MODEL_PATH = Path(os.getenv('MODEL_PATH', str(Path(__file__).resolve().parent / 'models' / 'forecast_best_model.json')))
metadata = json.loads(MODEL_PATH.read_text())
FEATURES = metadata['learner']['feature_names']
FeatureRow = create_model(
    'FeatureRow', __config__=ConfigDict(extra='forbid', allow_inf_nan=False),
    **{name: (float, ...) for name in FEATURES},
)

class PredictRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    rows: list[FeatureRow] = Field(min_length=1, max_length=1000)

@asynccontextmanager
async def lifespan(app: FastAPI):
    model = xgb.Booster()
    model.load_model(MODEL_PATH)
    model.set_param({'nthread': 1})
    app.state.model = model
    app.state.forward_bundle = load_bundle()
    yield

app = FastAPI(title='Solar Forecast API', version='1.0.0', lifespan=lifespan)

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.get('/features')
def features():
    return {'features': FEATURES}

@app.post('/predict')
def predict(request: PredictRequest):
    values = np.asarray([[getattr(row, key) for key in FEATURES] for row in request.rows], dtype=np.float32)
    matrix = xgb.DMatrix(values, feature_names=FEATURES)
    predictions = app.state.model.predict(matrix)
    return {'predictions_kw': predictions.tolist(), 'count': len(predictions)}

@app.post('/forward',response_model=ForwardResponse)
def forward(request:ForwardRequest):
    return predict_forward(app.state.forward_bundle,request)

@app.get('/forward/example')
def forward_example():
    return json.loads((Path(__file__).resolve().parent/'models/forward48/forward_example.json').read_text())

@app.get('/forward/report')
def forward_report():
    return json.loads((Path(__file__).resolve().parent/'models/forward48/training_report.json').read_text())
