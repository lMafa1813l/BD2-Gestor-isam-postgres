CC      ?= gcc
CFLAGS  ?= -std=c11 -Wall -Wextra -Wpedantic -O2 -g
CORE    := ../isam_am/core
SRCS    := $(CORE)/isam_io.c $(CORE)/isam_io_file.c $(CORE)/isam_index.c $(CORE)/isam_search.c $(CORE)/isam_insert.c $(CORE)/isam_vacuum.c
HDRS    := $(wildcard $(CORE)/*.h)
BINS    := test_isam_core test_isam_insert

test: $(BINS)
	./test_isam_core
	./test_isam_insert

test_isam_core: test_isam_core.c $(SRCS) $(HDRS)
	$(CC) $(CFLAGS) -I$(CORE) -o $@ test_isam_core.c $(SRCS)

test_isam_insert: test_isam_insert.c $(SRCS) $(HDRS)
	$(CC) $(CFLAGS) -I$(CORE) -o $@ test_isam_insert.c $(SRCS)

clean:
	rm -f $(BINS)

.PHONY: test clean
