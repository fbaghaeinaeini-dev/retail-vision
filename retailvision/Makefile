.PHONY: install track pipeline dashboard test lint clean synthetic

install:
	pip install -e ".[dev]"

track:
	python -m scripts.run_tracker --video $(VIDEO) --db data/retailvision.db

pipeline:
	python -m scripts.run_pipeline --db data/retailvision.db --video-id $(VIDEO_ID)

dashboard:
	cd dashboard && npm run dev

synthetic:
	python -m scripts.generate_synthetic --db data/synthetic.db

test:
	pytest tests/ -v --tb=short

lint:
	ruff check . --fix
	ruff format .

clean:
	rm -rf output/* data/*.db __pycache__ .pytest_cache
