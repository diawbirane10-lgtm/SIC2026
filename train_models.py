from pathlib import Path
import json
import joblib
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, log_loss
from sklearn.model_selection import train_test_split
from flowtrust_core import CLASSES, FEATURE_NAMES, generate_dataset

ROOT=Path(__file__).resolve().parent
MODELS=ROOT/'models'; MODELS.mkdir(exist_ok=True)
X,y=generate_dataset(samples_per_class=800, seed=2026)
Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=0.25,random_state=2026,stratify=y)
rf=RandomForestClassifier(n_estimators=220,max_depth=16,min_samples_leaf=2,class_weight='balanced',random_state=2026,n_jobs=-1)
rf.fit(Xtr,ytr)
proba=rf.predict_proba(Xte); pred=rf.predict(Xte)
iso=IsolationForest(n_estimators=180,contamination=0.035,random_state=2026,n_jobs=-1).fit(Xtr)
joblib.dump({'model':rf,'features':FEATURE_NAMES,'classes':CLASSES},MODELS/'afr_rf_diagnostic_v1.joblib',compress=('gzip',3))
joblib.dump({'model':iso,'features':FEATURE_NAMES},MODELS/'afr_isolation_known_domain_v1.joblib',compress=('gzip',3))
report={'model_id':'afr-rf-diagnostic-v1','dataset':'synthetic_sil_v1','synthetic_data_only':True,'seed':2026,'samples_per_class':800,'training_samples':len(ytr),'test_samples':len(yte),'classes':CLASSES,'feature_names':FEATURE_NAMES,'accuracy':accuracy_score(yte,pred),'balanced_accuracy':balanced_accuracy_score(yte,pred),'multiclass_log_loss':log_loss(yte,proba,labels=rf.classes_),'confusion_matrix':confusion_matrix(yte,pred,labels=CLASSES).tolist(),'warning':'Les performances concernent uniquement le banc de donnees synthetiques SIL.'}
(ROOT/'model_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))