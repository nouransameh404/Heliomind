"""Leakage-controlled direct 1–48 hour PV benchmark. No future measured weather.
Run: python scripts/train_forward.py --raw PATH --output PATH
"""
import argparse,csv,hashlib,json,time,warnings
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"heliomind-integrated"))
from lightgbm import LGBMRegressor
from prophet import Prophet
from forecast.seven_models import LSTMForecast
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.compose import TransformedTargetRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from xgboost import XGBRegressor
import joblib

HISTORY=48
FEATURES=[f'power_lag_{i}h' for i in range(1,49)]+['mean_6h','mean_24h','std_24h','horizon','target_hour_sin','target_hour_cos','target_year_sin','target_year_cos']
def features(history,origin,h):
    a=np.asarray(history,dtype=float);target=pd.Timestamp(origin)+pd.Timedelta(hours=h-1)
    return [*a[::-1],a[-6:].mean(),a[-24:].mean(),a[-24:].std(),h,np.sin(2*np.pi*target.hour/24),np.cos(2*np.pi*target.hour/24),np.sin(2*np.pi*target.dayofyear/365.25),np.cos(2*np.pi*target.dayofyear/365.25)]
def seasonal(history,h):return float(history[-24+(h-1)%24])
def metrics(y,p):return {'MAE_kw':float(mean_absolute_error(y,p)),'RMSE_kw':float(np.sqrt(mean_squared_error(y,p))),'R2':float(r2_score(y,p))}
def read_raw(path):
    values=[];bad=invalid=negative=0
    with open(path,newline='',encoding='utf-8-sig') as f:
        reader=csv.reader(f);header=next(reader);ti=header.index('timestamp');pi=header.index('241_DKA_Totals_PV_Active_Power')
        for row in reader:
            if len(row)!=len(header):bad+=1;continue
            try:p=float(row[pi]);t=pd.Timestamp(row[ti])
            except (ValueError,TypeError):invalid+=1;continue
            if not np.isfinite(p) or pd.isna(t):invalid+=1;continue
            if p<0:negative+=1;p=0.0
            values.append((t,p))
    d=pd.DataFrame(values,columns=['timestamp','power_kw']);duplicate=int(d.timestamp.duplicated().sum());d=d.drop_duplicates('timestamp').sort_values('timestamp')
    d=d.set_index('timestamp');hourly=d.power_kw.resample('1h').agg(['mean','count']);hourly['power_kw']=hourly['mean'].where(hourly['count']>=9)
    return hourly,{'raw_structurally_bad_rows':bad,'invalid_power_or_time_rows':invalid,'observed_negative_power_clipped_to_zero':negative,'target_definition':'Nonnegative PV output proxy: observed negative net active-power readings clipped to zero; missing observations remain missing','duplicate_timestamps_removed':duplicate,'hourly_bins':len(hourly),'usable_hourly_bins':int(hourly.power_kw.notna().sum()),'minimum_observations_per_hour':9,'expected_observations_per_hour':12,'missing_power_imputation':'none','clock_assumption':'Source timestamps treated as site-local clock, inferred from daytime pattern; timezone metadata not independently confirmed. No UTC conversion or solar-position calculation.'}
def run(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    hourly,audit=read_raw(args.raw);hourly.to_csv(out/'hourly_power.csv',index_label='timestamp')
    series=hourly.power_kw;times=series.index;power=series.to_numpy();n=len(power)
    cut1=times[int(n*.65)];cut2=times[int(n*.80)];stop=times[-1]+pd.Timedelta(hours=1)
    data={name:{'X':[],'y':[],'base':[],'origins':[],'h':[]} for name in ['train','validation','test']}
    for i in range(47,n-48):
        origin=times[i]+pd.Timedelta(hours=1);end=origin+pd.Timedelta(hours=48)
        name='train' if end<=cut1 else 'validation' if origin>=cut1 and end<=cut2 else 'test' if origin>=cut2 and end<=stop else None
        if name is None:continue
        if origin.hour%(3 if name=='train' else 6):continue
        history=power[i-47:i+1];target=power[i+1:i+49]
        if not np.isfinite(history).all() or not np.isfinite(target).all():continue
        dest=data[name]
        for h,y in enumerate(target,1):
            dest['X'].append(features(history,origin,h));dest['y'].append(y);dest['base'].append(seasonal(history,h));dest['origins'].append(origin.isoformat());dest['h'].append(h)
    for name,d in data.items():
        if not d['y']:raise RuntimeError('No complete windows in '+name)
        d['X']=np.asarray(d['X'],dtype=np.float32);d['y']=np.asarray(d['y']);d['base']=np.asarray(d['base'])
    candidates={
      'seasonal_persistence':None,
      'Ridge_Linear':make_pipeline(StandardScaler(),Ridge(alpha=1.0)),
      'XGBoost_Tree':XGBRegressor(n_estimators=150,learning_rate=.1,max_depth=6,random_state=42,n_jobs=2),
      'LightGBM_Tree':LGBMRegressor(n_estimators=150,learning_rate=.1,max_depth=6,random_state=42,n_jobs=2,verbosity=-1),
      'MLP_Deep':make_pipeline(StandardScaler(),MLPRegressor(hidden_layer_sizes=(100,50),max_iter=500,random_state=42)),
      'Prophet_TS':Prophet(daily_seasonality=True,yearly_seasonality=True),
      'LSTM_Deep_TS':LSTMForecast(epochs=10,batch_size=32)}
    import optuna
    def objective(trial):
        params={'n_estimators':trial.suggest_categorical('n_estimators',[100,150,250]),'max_depth':trial.suggest_int('max_depth',2,6),'learning_rate':trial.suggest_float('learning_rate',.02,.15,log=True),'reg_lambda':trial.suggest_float('reg_lambda',1.,20.,log=True)}
        estimator=XGBRegressor(**params,random_state=42,n_jobs=2)
        estimator.fit(data['train']['X'],data['train']['y'])
        return mean_absolute_error(data['validation']['y'],np.maximum(0,estimator.predict(data['validation']['X'])))
    study=optuna.create_study(direction='minimize',sampler=optuna.samplers.TPESampler(seed=42))
    study.enqueue_trial({'n_estimators':150,'max_depth':6,'learning_rate':.1,'reg_lambda':1.0})
    study.optimize(objective,n_trials=8)
    study.trials_dataframe().to_csv(out/'optuna_trials.csv',index=False)
    (out/'optuna_best.json').write_text(json.dumps({'parameters':study.best_params,'validation_MAE_kw':study.best_value,'selection_data':'validation only','n_trials':8},indent=2))
    candidates['XGBoost_Tree']=XGBRegressor(**study.best_params,random_state=42,n_jobs=2)
    def predict(name,model,d):
        if model is None:return d['base']
        if name=='Prophet_TS':
            dates=pd.to_datetime(d['origins'])+pd.to_timedelta(np.asarray(d['h'])-1,unit='h')
            unique=pd.DatetimeIndex(dates).unique()
            pred=model.predict(pd.DataFrame({'ds':unique})).set_index('ds').yhat
            return np.maximum(0,pred.reindex(dates).to_numpy())
        return np.maximum(0,model.predict(d['X']))
    records=[];models={};val=data['validation'];test=data['test']
    for name,model in candidates.items():
        started=time.time()
        if model is not None:
            with warnings.catch_warnings(record=True) as caught:
                if name=='Prophet_TS':
                    model.fit(series.loc[series.index<cut1].dropna().rename('y').rename_axis('ds').reset_index())
                else:model.fit(data['train']['X'],data['train']['y'])
            (out/'benchmarks').mkdir(exist_ok=True)
            joblib.dump(model,out/'benchmarks'/f'{name}.joblib')
        pred=predict(name,model,val)
        record={'model':name,'validation':metrics(val['y'],pred),'fit_seconds':round(time.time()-started,3),'params':{} if model is None else {k:str(v) for k,v in (model.get_params() if hasattr(model,'get_params') else {'daily_seasonality':True,'yearly_seasonality':True}).items() if k not in ['regressor','transformer','weights']},'warnings':[] if model is None else [str(w.message) for w in caught]}
        records.append(record);models[name]=model;print(json.dumps(record),flush=True)
    chosen=min(records,key=lambda record:record['validation']['MAE_kw'])['model']
    # Never choose or retune based on test performance.
    per=[];summary=[]
    for name,model in models.items():
        pred=predict(name,model,test)
        summary.append({'model':name,**metrics(test['y'],pred)})
        for h in range(1,49):
            mask=np.asarray(test['h'])==h;per.append({'model':name,'horizon_h':h,**metrics(test['y'][mask],pred[mask])})
        for horizon in [24,48]:
            mask=np.asarray(test['h'])<=horizon
            summary.append({'model':name,'horizon_hours':horizon,**metrics(test['y'][mask],pred[mask])})
    pd.DataFrame(summary).to_csv(out/'test_metrics.csv',index=False);pd.DataFrame(per).to_csv(out/'metrics_by_horizon.csv',index=False)
    bundle={'kind':chosen,'residual_correction':'residual' in chosen,'model':models[chosen],'features':FEATURES,'history_hours':48,'max_horizon_hours':48}
    joblib.dump(bundle,out/'forward_model.joblib')
    if models[chosen] is not None and chosen.startswith('xgboost'):models[chosen].save_model(out/'forward_xgboost.json')
    spec={'selected_by':'lowest validation MAE, never test MAE','selected_model':chosen,'audit':audit,'features':FEATURES,'history_hours':48,'horizons':[24,48],'forecast_method':'direct pooled horizon-conditioned predictions; no recursive predicted lags','weather':'No contemporaneous or future measured weather used','hourly_target':'mean kW of each full 1-hour interval, requiring >=9 valid 5-minute observations','split_boundaries':{'train_label_end_at_or_before':str(cut1),'validation_origin_at_or_after':str(cut1),'validation_label_end_at_or_before':str(cut2),'test_origin_at_or_after':str(cut2)},'windows':{name:len(set(d['origins'])) for name,d in data.items()},'experiments':records,'data_sha256':hashlib.sha256(Path(args.raw).read_bytes()).hexdigest(),'limitations':['Test period has been inspected during project development; this is not a blind external evaluation.','Single site and one-year data; not proven for other plants or years.','Timezone is an explicit assumption pending independent source confirmation.','Operational anomalies retained in target; no unverified anomaly-to-zero cleaning.','Overlapping rolling test windows; errors are not independent statistical samples.','Forecast skill and coverage depend on complete 48-hour history and target windows.']}
    (out/'training_report.json').write_text(json.dumps(spec,indent=2))
    (out/'experiment_log.json').write_text(json.dumps(records,indent=2))
    # Test-period historical origin for a reproducible honest demo.
    origin=pd.Timestamp(test['origins'][0]);history=series.loc[(series.index>=origin-pd.Timedelta(hours=48))&(series.index<origin)]
    example={'horizon_hours':48,'history':[{'timestamp':t.isoformat(),'power_kw':float(v)} for t,v in history.items()]}
    (out/'forward_example.json').write_text(json.dumps(example,indent=2))
    actual=series.loc[(series.index>=origin)&(series.index<origin+pd.Timedelta(hours=48))]
    (out/'demo_actual.json').write_text(json.dumps({'origin':origin.isoformat(),'actual':[{'period_start':t.isoformat(),'power_kw':float(v)} for t,v in actual.items()]},indent=2))
    print('SELECTED',chosen,'WINDOWS',spec['windows'],flush=True)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--raw',required=True);parser.add_argument('--output',required=True);run(parser.parse_args())
