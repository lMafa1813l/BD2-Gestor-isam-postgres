# Atajos del repo
test:            ## pruebas del nucleo ISAM en C (no requiere PostgreSQL)
	$(MAKE) -C tests test
integration:     ## Bloque 4: Docker + pruebas end-to-end del AM ISAM
	./docker/integration.sh
crash:           ## Bloque 4: simula una caida y verifica recuperacion (WAL / UNLOGGED)
	./docker/crash.sh
bench:           ## Bloque 5: benchmark sin indice vs B-tree vs ISAM (N, T, CLIENTS, FILL, DATASETS, CONFIGS)
	./docker/bench.sh
overflow:        ## Bloque 6: experimento de overflow (INSERT_MODE=dist|narrow, DATASET, N, BATCHES, CONFIGS)
	./docker/overflow.sh
crash-load:      ## Bloque 6: kill del servidor bajo carga concurrente de inserts y verificacion del indice
	./docker/crash_load.sh
report:          ## validar resultados corregidos y generar tablas/figuras del informe
	mkdir -p .cache/stage1-report
	cp Informe_IEtapa.tex .cache/stage1-report/Informe_IEtapa.tex
	MPLCONFIGDIR=.cache/matplotlib python3 benchmarks/build_report.py --output-dir .cache/stage1-report --report .cache/stage1-report/Informe_IEtapa.tex
demo:            ## defensa: igualdad, ausencia, rango, overflow, VACUUM y REINDEX
	./docker/demo.sh
pdf:             ## informe de Etapa I (requiere pdflatex/TeX Live)
	latexmk -pdf -interaction=nonstopmode -halt-on-error Informe_IEtapa.tex
pdf-final:        ## informe conjunto de indexación y distribución
	latexmk -pdf -interaction=nonstopmode -halt-on-error Informe_Final.tex
dist-up:
	./distributed/run.sh up
dist-stop:
	./distributed/run.sh stop
dist-setup:
	./distributed/run.sh up
	flock -n ".cache/$${DIST_PROJECT:-bd2_dist}.lock" "$${DIST_PYTHON:-.venv-dist/bin/python}" distributed/manage.py setup $(DIST_ARGS)
dist-demo:
	./distributed/run.sh up
	flock -n ".cache/$${DIST_PROJECT:-bd2_dist}.lock" "$${DIST_PYTHON:-.venv-dist/bin/python}" distributed/manage.py demo $(DIST_ARGS)
dist-smoke:
	./distributed/run.sh smoke $(DIST_ARGS)
dist-validate:
	./distributed/run.sh validate $(DIST_ARGS)
dist-bench:
	./distributed/run.sh bench $(DIST_ARGS)
dist-report:
	MPLCONFIGDIR=.cache/matplotlib python3 distributed/summarize.py docs/results/distributed/model docs/results/distributed/base --validation docs/results/distributed/acceptance --out docs/results/distributed
clean:
	$(MAKE) -C tests clean
.PHONY: test integration crash bench overflow crash-load report demo pdf pdf-final clean dist-up dist-stop dist-setup dist-demo dist-smoke dist-validate dist-bench dist-report
