"""Audit the unchanged deployed benchmark; chronological refit is diagnostic only."""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
import joblib,xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.impute import SimpleImputer
from sklearn.metrics import confusion_matrix,precision_recall_fscore_support,average_precision_score
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/anomaly_review';OUT.mkdir(parents=True,exist_ok=True)
M=ROOT/'heliomind-integrated/anomaly/models'
f=json.loads((M/'metadata.json').read_text())['features']
df=pd.read_csv(ROOT/'data/processed/Anomaly/kaggle_anomaly_data.csv',parse_dates=['DATE_TIME']).sort_values(['SOURCE_KEY','DATE_TIME']).reset_index(drop=True)
df['hour']=df.DATE_TIME.dt.hour;df['month']=df.DATE_TIME.dt.month
df['temperature_difference']=df.MODULE_TEMPERATURE-df.AMBIENT_TEMPERATURE
df['power_difference']=df.DC_POWER-df.AC_POWER
for col,key in [('DC_POWER','zero_dc_power'),('IRRADIATION','zero_irradiation')]:df[key]=(df[col]==0).astype(int)
df['dc_power_per_irradiation']=df.DC_POWER/df.IRRADIATION.replace(0,np.nan)
for col,prev,change in [('DC_POWER','previous_dc_power','dc_power_change'),('DAILY_YIELD','previous_daily_yield','daily_yield_change')]:
 df[prev]=df.groupby('SOURCE_KEY')[col].shift(1);df[change]=df[col]-df[prev]
X=df[f];y=df.is_anomaly
tr,te=train_test_split(np.arange(len(df)),test_size=.2,stratify=y,random_state=42)
imp=joblib.load(M/'imputer.joblib');booster=xgb.Booster();booster.load_model(M/'anomaly_model.json');booster.set_param({'nthread':2})
assert list(imp.feature_names_in_)==f
assert np.allclose(SimpleImputer(strategy='median').fit(X.iloc[tr]).statistics_,imp.statistics_)
def metrics(y,p):
 pr,re,fs,_=precision_recall_fscore_support(y,p>.5,average='binary',zero_division=0)
 return dict(confusion_matrix=confusion_matrix(y,p>.5,labels=[0,1]).tolist(),precision=pr,recall=re,F1=fs,average_precision=average_precision_score(y,p),rows=len(y),positives=int(y.sum()))
v=imp.transform(X.iloc[te]);dm=xgb.DMatrix(v);p=booster.predict(dm)
c=booster.predict(xgb.DMatrix(v[:512]),pred_contribs=True)
assert np.allclose(1/(1+np.exp(-c.sum(axis=1))),p[:512],atol=1e-5)
pd.DataFrame({'feature':f,'mean_absolute_SHAP_log_odds':abs(c[:,:-1]).mean(axis=0)}).sort_values('mean_absolute_SHAP_log_odds',ascending=False).to_csv(OUT/'global_shap.csv',index=False)
days=np.sort(df.DATE_TIME.dt.normalize().unique());cut=days[int(len(days)*.8)]
a=df.DATE_TIME<cut;b=~a
im=SimpleImputer(strategy='median');xt=im.fit_transform(X[a]);xv=im.transform(X[b])
model=xgb.XGBClassifier(n_estimators=442,max_depth=6,learning_rate=.19555684160820405,min_child_weight=6,subsample=.9633063543866615,colsample_bytree=.9990961940195767,gamma=.1333905071376425,reg_lambda=1.8932323211830573,scale_pos_weight=float((y[a]==0).sum()/max(1,(y[a]==1).sum())),random_state=42,n_jobs=2,eval_metric='logloss')
model.fit(xt,y[a]);q=model.predict_proba(xv)[:,1]
r={'deployed_model_sha256':hashlib.sha256((M/'anomaly_model.json').read_bytes()).hexdigest(),'label_source':'Synthetic faults injected by Data Cleaning notebook; not verified human fault annotations','original_random_split':metrics(y.iloc[te],p),'chronological_diagnostic':{'cutoff':str(pd.Timestamp(cut)),'training_rows':int(a.sum()),'test_rows':int(b.sum()),'train_only_imputer':True,'deployment_changed':False,'metrics':metrics(y[b],q)},'limitations':['Original deployed model uses random split; its shuffled CV imputation was fitted before folds.','Chronological diagnostic refits a separate model; original hyperparameters came from prior random-split search, so this is not a blind external validation.','Soiling injection modifies a full day while labelling only ten rows. Synthetic labels are incomplete.','SHAP explains model scores, not a physical fault diagnosis; probabilities are uncalibrated.','Global SHAP uses the first 512 rows of the deterministic shuffled test split.']}
(OUT/'evaluation.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
