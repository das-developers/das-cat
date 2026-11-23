# Schema sources

The `*.json5` files here are the editable sources for the published
schemas in `schema/<type>/v<version>.json`.  They are JSON5 only so they
can carry comments.  What gets published is strict JSON, because any
tool may fetch a schema and apply it, and the JSON Schema spec assumes
JSON.

## Workflow

    edit src/schema/*.json5
    make schema       # writes schema/<type>/v<version>.json
    make check        # fails if a published schema does not match the sources
    make validate     # check, then test/validate.sh

Commit the sources and the generated files together.  `make check`
rebuilds into a scratch directory and compares, so it catches a source
edited without a rebuild and a hand edit to a generated file.

## JSON5 subset

`src/scripts/json5_to_json.py` handles only `//` and `/* */` comments and
trailing commas, then parses with Python's strict `json`.  Other JSON5
features (single quotes, unquoted keys, hex numbers, ...) and duplicate
keys are errors, reported with the file and line.  If a source needs one
of those features, extend the converter; don't work around it.

## Versions

Each node type with a published schema has a version of its own, set in
the top-level Makefile (`CATALOG_VER`, `SOURCESET_VER`,
`HTTPSTREAMSRC_VER`).  The importer stamps the same numbers on what it
writes (`g_dVersion` in `src/scripts/dsdf_cat_import`).

Bump a type's version when a change would make a node of that type that
passed now fail, or the reverse.  Also update the `(X.Y)` line in the
source's header comment.  The file of the old version stays as
published; this directory only holds the source of the current one.
Fixes that do not change validation results can go into the current
version.

`catobj`, `node` and `reference` are shared pieces and have no version.
Each published schema carries its own copy of them, so a change to one
of them is a change to every type that uses it, and bumps each of those.

The schemas check the `version` member's pattern but do not pin its
value.  `test/validate_tree.py` picks the schema by a node's type and
version, and says so when there is none for that version.

## Building

`src/scripts/schema_bundle.py SOURCE.json5 VERSION OUT.json` writes one
published schema.  Sources refer to each other by file name
(`"$ref":"node.json#/$defs/Contacts"`).  The bundle keeps those
references as written and places a copy of each source it uses under its
own `$defs`, keyed by file name and keeping its `$id`.  That is a JSON
Schema 2020-12 compound document: validators resolve the reference to
the copy inside the file.  The bundle's own `$id` is `v<version>.json`.

## Structure notes

- `catobj` is the base for everything, and `node` adds what full nodes
  have.  `reference` is a catobj and is not a node.
- `node.json#/$defs/Child` is what may appear under a `catalog` member,
  of a Catalog or a SourceSet.  An entry with `urls` or `locations` is
  checked as a Reference.  Any other entry is a node held in place and
  is checked only as a catalog object, which requires its `type`; its
  own schema is applied separately, by type and version.  A container
  schema does not name the schemas of what it may hold, which is what
  lets the types version apart.
- Catalog, SourceSet and HttpStreamSrc each pin `type` with `const`.
- Choices between alternative members (`name` or `label`, `urls` or
  `locations`) use `anyOf`, so that transitional nodes carrying both still
  pass.
- `httpstreamsrc.json5` has the vocabulary das2C reads and the importer
  writes.  Inner objects are closed, so a misspelled member fails.
  It is the reference for 0.7; nodes from other generators are expected
  to be brought in line with it.
