MODULE_big = isam_am
OBJS = isam_handler.o isam_am_build.o isam_am_insert.o isam_am_scan.o \
       isam_am_vacuum.o isam_am_cost.o isam_am_stats.o \
       core/isam_io.o core/isam_io_pg.o core/isam_index.o core/isam_search.o \
       core/isam_insert.o core/isam_vacuum.o
EXTENSION = isam_am
DATA = isam_am--1.0.sql isam_am--1.0--1.1.sql

PG_CPPFLAGS = -DISAM_IN_POSTGRES -I$(CURDIR)/core
PG_CFLAGS = -Wno-declaration-after-statement

PG_CONFIG ?= pg_config
PGXS := $(shell $(PG_CONFIG) --pgxs)
include $(PGXS)
