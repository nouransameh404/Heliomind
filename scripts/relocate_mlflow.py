"""Repair forecast MLflow artifact URIs after moving the project."""
from pathlib import Path
import yaml
project=Path(__file__).resolve().parents[1]
for relative in ['reports/forward48/mlruns','reports/forward_seven/mlruns']:
    root=project/relative
    for meta in root.glob('*/meta.yaml'):
        data=yaml.safe_load(meta.read_text());data['artifact_location']=meta.parent.as_uri();meta.write_text(yaml.safe_dump(data))
    for meta in root.glob('*/*/meta.yaml'):
        data=yaml.safe_load(meta.read_text());data['artifact_uri']=(meta.parent/'artifacts').as_uri();meta.write_text(yaml.safe_dump(data))
    print('Updated',root)
