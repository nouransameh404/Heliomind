"""Log the completed seven-model experiment without retraining."""
from pathlib import Path
import json
import pandas as pd
import mlflow
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/forward_seven'
mlflow.set_tracking_uri((OUT/'mlruns').resolve().as_uri())
mlflow.set_experiment('Solar_Forecast_Seven_24_48h')
report=json.loads((OUT/'training_report.json').read_text());test=pd.read_csv(OUT/'test_metrics.csv');runs=[]
for row in report['experiments']:
    name=row['model']
    with mlflow.start_run(run_name=name) as run:
        mlflow.log_params({'model':name,'history_hours':48,'max_horizon_hours':48,'selection':'validation_MAE','future_measured_weather':False,'selected':name==report['selected_model'],'data_sha256':report['data_sha256']})
        mlflow.log_dict(row['params'],'parameters.json')
        mlflow.log_dict(row['warnings'],'warnings.json')
        for key,value in row['validation'].items():mlflow.log_metric('validation_'+key,value)
        metric=test[(test.model==name)&test.horizon_hours.isna()].iloc[0]
        for key in ['MAE_kw','RMSE_kw','R2']:mlflow.log_metric('test_'+key,float(metric[key]))
        mlflow.log_artifact(str(OUT/'training_report.json'))
        if name=='XGBoost_Tree':
            mlflow.log_artifact(str(OUT/'optuna_trials.csv'))
            mlflow.log_artifact(str(OUT/'optuna_best.json'))
        path=OUT/'benchmarks'/f'{name}.joblib'
        if path.exists():mlflow.log_artifact(str(path),'model')
        runs.append({'model':name,'run_id':run.info.run_id})
(OUT/'mlflow_runs.json').write_text(json.dumps(runs,indent=2))
print('Logged',len(runs),'runs')
