PY := .venv/bin/python
VENV := .venv

.PHONY: all data warehouse analysis analytics docs test clean venv

all: docs test

venv:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.txt

data:
	$(PY) src/generate_data.py

warehouse: data
	$(PY) src/build_warehouse.py

analysis: warehouse
	$(PY) src/run_sql_analysis.py

analytics: analysis
	$(PY) src/model_churn.py
	$(PY) src/rfm_segments.py
	$(PY) src/ab_test_winback.py
	$(PY) src/build_analytics_doc.py

docs: analytics
	$(PY) src/business_case.py
	$(PY) src/build_dashboard.py
	$(PY) src/build_roadmap.py
	$(PY) src/build_readme.py

test:
	$(PY) -m pytest tests/ -q

clean:
	rm -rf outputs data/raw data/sample .pytest_cache
