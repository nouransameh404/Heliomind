import json
from pathlib import Path
from contextlib import asynccontextmanager
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, create_model
ROOT = Path(__file__).resolve().parent / 'models'
FEATURES = json.loads((ROOT/'metadata.json').read_text())['features']
Row = create_model('AnomalyRow', __config__=ConfigDict(extra='forbid', allow_inf_nan=False), **{key:(float | None, ...) for key in FEATURES})
class Request(BaseModel):
    model_config = ConfigDict(extra='forbid')
    rows: list[Row] = Field(min_length=1, max_length=1000)
@asynccontextmanager
async def lifespan(app):
    imputer = joblib.load(ROOT/'imputer.joblib')
    if list(imputer.feature_names_in_) != FEATURES:
        raise ValueError('Imputer feature order differs from metadata')
    model = xgb.Booster()
    model.load_model(ROOT/'anomaly_model.json')
    if model.num_features() != len(FEATURES):
        raise ValueError('Model feature count differs from metadata')
    model.set_param({'nthread':1})
    app.state.imputer, app.state.model = imputer, model
    yield
app = FastAPI(title='Anomaly Detection Service', lifespan=lifespan)
@app.get('/health')
def health(): return {'status':'ok'}
@app.get('/features')
def features(): return {'features':FEATURES}
@app.post('/predict')
def predict(data: Request):
    frame = pd.DataFrame([row.model_dump() for row in data.rows], columns=FEATURES)
    values = app.state.imputer.transform(frame)
    matrix = xgb.DMatrix(values)
    probability = app.state.model.predict(matrix)
    contributions = app.state.model.predict(matrix, pred_contribs=True)
    predictions=[]
    for i,p in enumerate(probability):
        explanation=[{'feature':name,'shap_log_odds':float(contributions[i,j]),'imputed':bool(pd.isna(frame.iloc[i,j]))} for j,name in enumerate(FEATURES)]
        predictions.append({'is_anomaly':int(p>0.5),'anomaly_probability':float(p),'base_log_odds':float(contributions[i,-1]),'explanation':sorted(explanation,key=lambda x:abs(x['shap_log_odds']),reverse=True)})
    return {'predictions':predictions,'count':len(probability),'threshold':0.5,'scope':'Synthetic injected-fault benchmark; random-split evaluation; not verified real fault labels','score_note':'Uncalibrated model score. SHAP contributions explain the model, not a physical fault cause.'}
