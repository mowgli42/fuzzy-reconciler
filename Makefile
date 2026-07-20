.PHONY: install fixtures test backend frontend demo

install:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[test]"
	cd frontend && npm install

fixtures:
	.venv/bin/python scripts/generate_sample_data.py

test:
	PYTHONPATH=src .venv/bin/pytest -q

backend:
	PYTHONPATH=src .venv/bin/uvicorn fuzzy_reconciler.api.app:app --host 0.0.0.0 --port 8010 --reload

frontend:
	cd frontend && npm run dev -- --host 0.0.0.0 --port 5173

demo: fixtures
	PYTHONPATH=src .venv/bin/python -c "from fuzzy_reconciler.matching.engine import compare_lists; from fuzzy_reconciler.models import Entity, MatchConfig, MatchWeights; import json; d=json.load(open('fixtures/small_demo.json')); cfg=MatchConfig(max_geo_distance_m=350,date_tolerance_days=30,weights=MatchWeights(geo=0.3,name=0.2,attr=0.35,temporal=0.15)); r=compare_lists([Entity(**e) for e in d['list_a']],[Entity(**e) for e in d['list_b']],cfg); print(r.summary)"
