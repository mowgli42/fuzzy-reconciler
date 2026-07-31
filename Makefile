.PHONY: install fixtures import-samples fixtures-regions fixtures-regions-small fixtures-regions-canonical test backend frontend demo

install:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[test]"
	cd frontend && npm install

fixtures:
	.venv/bin/python scripts/generate_sample_data.py

import-samples:
	.venv/bin/python scripts/generate_import_samples.py

# Small committed set for CI / clean checkout (tracked under fixtures/regions/canonical/).
fixtures-regions-canonical:
	.venv/bin/python scripts/generate_regional_locations.py --region iran --count 40 --seed 42 --out fixtures/regions/canonical/iran_base.json
	.venv/bin/python scripts/generate_delta.py --base fixtures/regions/canonical/iran_base.json --out fixtures/regions/canonical/iran_delta.json --also-write-pair fixtures/regions/canonical/iran_pair.json --seed 99 --fraction 0.9

# Synthetic hot-spot regional fixtures (radars, missile sites, etc.) + delta pair.
# Large outputs under fixtures/regions/*_base.json are gitignored; regenerate after checkout.
fixtures-regions-small:
	.venv/bin/python scripts/generate_regional_locations.py --region all --count 50 --out fixtures/regions/
	.venv/bin/python scripts/generate_delta.py --base fixtures/regions/iran_base.json --out fixtures/regions/iran_delta.json --also-write-pair fixtures/regions/iran_pair.json --seed 99 --fraction 0.9

fixtures-regions:
	.venv/bin/python scripts/generate_regional_locations.py --region all --count 500 --out fixtures/regions/
	.venv/bin/python scripts/generate_delta.py --base fixtures/regions/iran_base.json --out fixtures/regions/iran_delta.json --also-write-pair fixtures/regions/iran_pair.json --seed 99 --fraction 0.85

test: import-samples
	PYTHONPATH=src .venv/bin/pytest -q

backend:
	PYTHONPATH=src .venv/bin/uvicorn fuzzy_reconciler.api.app:app --host 0.0.0.0 --port 8010 --reload

frontend:
	cd frontend && npm run dev -- --host 0.0.0.0 --port 5173

demo: fixtures
	PYTHONPATH=src .venv/bin/python -c "from fuzzy_reconciler.matching.engine import compare_lists; from fuzzy_reconciler.models import Entity, MatchConfig, MatchWeights; import json; d=json.load(open('fixtures/small_demo.json')); cfg=MatchConfig(max_geo_distance_m=350,date_tolerance_days=30,weights=MatchWeights(geo=0.3,name=0.2,attr=0.35,temporal=0.15)); r=compare_lists([Entity(**e) for e in d['list_a']],[Entity(**e) for e in d['list_b']],cfg); print(r.summary)"
