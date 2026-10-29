"""Direct, horizon-conditioned future PV prediction from completed hourly history."""
from pathlib import Path
import json
import joblib
import numpy as np
from datetime import datetime,timedelta
from pydantic import BaseModel,ConfigDict,Field,model_validator
from typing import Literal
FEATURES=[f'power_lag_{i}h' for i in range(1,49)]+['mean_6h','mean_24h','std_24h','horizon','target_hour_sin','target_hour_cos','target_year_sin','target_year_cos']
class HourlyReading(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    timestamp:datetime
    power_kw:float=Field(ge=0)
class ForwardRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    horizon_hours:Literal[24,48]=48
    history:list[HourlyReading]=Field(min_length=48,max_length=2048)
    @model_validator(mode='after')
    def hourly_history(self):
        for row in self.history:
            if row.timestamp.tzinfo is not None:raise ValueError('Use source-clock timestamps without UTC offsets; timezone metadata is not confirmed')
            if row.timestamp.minute or row.timestamp.second or row.timestamp.microsecond:raise ValueError('Hourly timestamps must mark interval starts at exact hours')
        if any(b.timestamp-a.timestamp!=timedelta(hours=1) for a,b in zip(self.history,self.history[1:])):raise ValueError('History must be consecutive hourly intervals in increasing order, without gaps or duplicates')
        return self
class FuturePoint(BaseModel):
    period_start:datetime
    period_end:datetime
    predicted_power_kw:float
    predicted_energy_kwh:float
    seasonal_baseline_kw:float
    reference_history_timestamp:datetime
    explanation:str
class ForwardResponse(BaseModel):
    origin:datetime
    horizon_hours:int
    selected_model:str
    time_basis:str
    total_energy_kwh:float
    points:list[FuturePoint]
def vector(history,origin,h):
    a=np.asarray(history,dtype=float);target=origin+timedelta(hours=h-1)
    return [*a[::-1],a[-6:].mean(),a[-24:].mean(),a[-24:].std(),h,np.sin(2*np.pi*target.hour/24),np.cos(2*np.pi*target.hour/24),np.sin(2*np.pi*target.timetuple().tm_yday/365.25),np.cos(2*np.pi*target.timetuple().tm_yday/365.25)]
def load_bundle():
    path=Path(__file__).resolve().parent/'models/forward48/forward_model.joblib'
    bundle=joblib.load(path)
    if bundle['features']!=FEATURES:raise ValueError('Forward model feature contract mismatch')
    return bundle

def predict_forward(bundle,request):
    history=request.history[-48:];power=[row.power_kw for row in history];origin=history[-1].timestamp+timedelta(hours=1)
    x=np.asarray([vector(power,origin,h) for h in range(1,request.horizon_hours+1)],dtype=np.float32)
    baseline=np.asarray([power[-24+(h-1)%24] for h in range(1,request.horizon_hours+1)])
    if bundle['kind']=='Prophet_TS':
        import pandas as pd
        dates=[origin+timedelta(hours=i) for i in range(request.horizon_hours)]
        pred=np.maximum(0,bundle['model'].predict(pd.DataFrame({'ds':dates})).yhat.to_numpy())
    else:pred=baseline if bundle['model'] is None else np.maximum(0,bundle['model'].predict(x)+(baseline if bundle.get('residual_correction') else 0))
    points=[{'period_start':origin+timedelta(hours=i),'period_end':origin+timedelta(hours=i+1),'predicted_power_kw':float(p),'predicted_energy_kwh':float(p),'seasonal_baseline_kw':float(baseline[i]),'reference_history_timestamp':history[-24+i%24].timestamp,'explanation':'Selected seasonal persistence repeats this completed historical hourly reading' if bundle['model'] is None else 'Horizon-conditioned model uses only the completed 48-hour history and known future calendar values'} for i,p in enumerate(pred)]
    return {'origin':origin,'horizon_hours':request.horizon_hours,'selected_model':bundle['kind'],'time_basis':'Unshifted source-clock timestamps; site-local convention assumed, not independently confirmed','total_energy_kwh':float(np.sum(pred)),'points':points}
