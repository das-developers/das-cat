# Build the published schemas in schema/<version>/ from the commented
# JSON5 sources in src/schema/.  The generated files are committed on
# purpose: clients fetch them straight from the repository, so they must
# exist on main.

CONVERT := src/scripts/json5_to_json

# Version of the schema set, and of every node type in it.  src/schema/
# holds only the current set; older schema/v*/ directories are frozen and
# not rebuilt.  After v0.9 comes v1.0, not v0.10.
SCHEMA_VER := v0.7
SCHEMA_DIR := schema/$(SCHEMA_VER)

SCHEMA_SRC := $(wildcard src/schema/*.json5)
SCHEMA_OUT := $(patsubst src/schema/%.json5,$(SCHEMA_DIR)/%.json,$(SCHEMA_SRC))

.PHONY: all schema check validate

all: schema

schema: $(SCHEMA_OUT)

$(SCHEMA_DIR)/%.json: src/schema/%.json5 $(CONVERT) | $(SCHEMA_DIR)
	$(CONVERT) $< $@

$(SCHEMA_DIR):
	mkdir -p $@

# Rebuild every schema into a scratch directory and compare with the
# current version directory.
# Catches a source edited without a rebuild, a hand edit to a generated
# file, and a generated file whose source was removed.  Independent of
# file times and of git state.
check:
	@d=$$(mktemp -d) && trap 'rm -rf "$$d"' EXIT && \
	for f in $(SCHEMA_SRC); do \
		b=$$(basename $$f .json5); \
		$(CONVERT) $$f $$d/$$b.json || exit 1; \
	done && \
	if diff -r $$d $(SCHEMA_DIR); then \
		echo "$(SCHEMA_DIR)/ matches src/schema/"; \
	else \
		echo "$(SCHEMA_DIR)/ is stale, run make schema"; exit 1; \
	fi

validate: check
	test/validate.sh $(SCHEMA_DIR)
