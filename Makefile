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
report:          ## Bloque 6: resumen en Markdown y graficos PNG del ultimo CSV de benchmarks/results/
	python3 benchmarks/summarize.py
	python3 benchmarks/plot.py
clean:
	$(MAKE) -C tests clean
.PHONY: test integration crash bench overflow crash-load report clean
