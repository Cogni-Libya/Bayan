PY ?= python3

all: bayan_benchmark_report.pdf

build/analysis.json: analyse.py systems.py
	$(PY) analyse.py

figures tables: build/analysis.json
	$(PY) figures.py && $(PY) tables.py

bayan_benchmark_report.pdf: report.tex figures tables
	latexmk -xelatex -interaction=nonstopmode -jobname=bayan_benchmark_report report.tex

scores:
	$(PY) collect.py

clean:
	latexmk -C -jobname=bayan_benchmark_report

.PHONY: all figures tables scores clean
