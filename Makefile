# Build the published schemas, schema/<type>/v<version>.json, from the
# commented JSON5 sources in src/schema/.  The generated files are
# committed on purpose: clients fetch them straight from the repository,
# so they must exist on main.

BUNDLE  := src/scripts/schema_bundle.py
CONVERT := src/scripts/json5_to_json.py

# Each node type has a version of its own.  A change that makes a node
# that passed fail, or the reverse, bumps that type alone and leaves its
# older schema files as published.  After 0.9 comes 1.0, not 0.10.
# The importer stamps the same numbers on the nodes it writes
# (g_dVersion in src/scripts/dsdf_cat_import).
CATALOG_VER       := 0.5
SOURCESET_VER     := 0.2
HTTPSTREAMSRC_VER := 0.7

# Every source is a prerequisite of every schema: each published file
# carries its own copy of the shared pieces (catobj, node, reference).
SCHEMA_SRC := $(wildcard src/schema/*.json5)
SCHEMA_OUT := schema/catalog/v$(CATALOG_VER).json \
              schema/sourceset/v$(SOURCESET_VER).json \
              schema/httpstreamsrc/v$(HTTPSTREAMSRC_VER).json

.PHONY: all schema check validate

all: schema

schema: $(SCHEMA_OUT)

schema/catalog/v$(CATALOG_VER).json: $(SCHEMA_SRC) $(BUNDLE) $(CONVERT)
	@mkdir -p $(dir $@)
	$(BUNDLE) src/schema/catalog.json5 $(CATALOG_VER) $@

schema/sourceset/v$(SOURCESET_VER).json: $(SCHEMA_SRC) $(BUNDLE) $(CONVERT)
	@mkdir -p $(dir $@)
	$(BUNDLE) src/schema/sourceset.json5 $(SOURCESET_VER) $@

schema/httpstreamsrc/v$(HTTPSTREAMSRC_VER).json: $(SCHEMA_SRC) $(BUNDLE) $(CONVERT)
	@mkdir -p $(dir $@)
	$(BUNDLE) src/schema/httpstreamsrc.json5 $(HTTPSTREAMSRC_VER) $@

# Rebuild the current schemas into a scratch directory and compare with
# the published files.  Catches a source edited without a rebuild and a
# hand edit to a generated file.  Independent of file times and of git
# state.  Older versions of a type are not looked at, they are frozen.
check:
	@d=$$(mktemp -d) && trap 'rm -rf "$$d"' EXIT && nBad=0 && \
	for f in $(SCHEMA_OUT); do \
		t=$$(basename $$(dirname $$f)); v=$$(basename $$f .json); \
		$(BUNDLE) src/schema/$$t.json5 $${v#v} $$d/$$t.json || exit 1; \
		if cmp -s $$d/$$t.json $$f; then \
			echo "$$f matches src/schema/"; \
		else \
			echo "$$f is stale, run make schema"; nBad=1; \
		fi; \
	done; exit $$nBad

validate: check
	test/validate.sh
