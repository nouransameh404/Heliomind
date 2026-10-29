"""Record the already-completed reproducible benchmark in local MLflow."""
from pathlib import Path
import argparse,json
import pandas as pd
import mlflow
p=argparse.ArgumentParser();p.add_argument('--models',required=True);p.add_argument('--tracking',required=True);args=p.parse_args()
models=Path(args.models).resolve();tracking=Path(args.tracking).resolve();tracking.mkdir(parents=True,exist_ok=True)
mlflow.set_tracking_uri(tracking.as_uri());mlflow.set_experiment('AliceSprings_Forward_24_48h')
report=json.loads((models/'training_report.json').read_text());test=pd.read_csv(models/'test_metrics.csv')
receipts=[]
for record in report['experiments']:
    name=record['model']
    with mlflow.start_run(run_name=name) as run:
        mlflow.log_params({'model':name,'forecast_horizon_hours':48,'history_hours':48,'data_sha256':report['data_sha256'],'future_weather':'not_used','selected':name==report['selected_model'],'split':'chronological_65_15_20_with_purged_labels'})
        for key,value in record['validation'].items():mlflow.log_metric('validation_'+key,value)
        metrics=test[(test.model==name)&test.horizon_hours.isna()].iloc[0]
        for key in ['MAE_kw','RMSE_kw','R2']:mlflow.log_metric('test_'+key,float(metrics[key]))
        mlflow.log_dict(record,'parameters_and_warnings.json');mlflow.log_artifact(str(models/'training_report.json'));mlflow.log_artifact(str(models/'metrics_by_horizon.csv'))
        artifact=models/'benchmarks'/f'{name}.joblib'
        if artifact.is_file():mlflow.log_artifact(str(artifact),'model')
        if name==report['selected_model']:mlflow.log_artifact(str(models/'forward_model.joblib'),'selected_model')
        receipts.append({'name':name,'run_id':run.info.run_id})
(models/'mlflow_runs.json').write_text(json.dumps(receipts,indent=2))
print('Tracked',len(receipts),'MLflow runs at',tracking)
