# Schema sources

The `*.json5` files here are the editable sources for the published
schemas in `schema/v<version>/`.  They are JSON5 only so they can carry
comments.  What gets published is strict JSON, because any tool may fetch
a schema and apply it, and the JSON Schema spec assumes JSON.

## Workflow

    edit src/schema/*.json5
    make schema       # writes schema/$(SCHEMA_VER)/*.json
    make check        # fails if the published set does not match the sources
    make validate     # check, then test/validate.sh against the set

Commit the sources and the generated files together.  `make check`
rebuilds into a scratch directory and diffs, so it catches a source
edited without a rebuild, a hand edit to a generated file, and a
generated file whose source was removed.

## JSON5 subset

`src/scripts/json5_to_json` handles only `//` and `/* */` comments and
trailing commas, then parses with Python's strict `json`.  Other JSON5
features (single quotes, unquoted keys, hex numbers, ...) and duplicate
keys are errors, reported with the file and line.  If a source needs one
of those features, extend the converter; don't work around it.

## Versions

`SCHEMA_VER` in the top-level Makefile names the set being built.  This
directory holds only the current set; older `schema/v*/` directories are
frozen and not rebuilt (see the top-level README).

Start a new version, by bumping `SCHEMA_VER`, when a change would make a
node that passed now fail, or the reverse.  Also update the `(X.Y)` line
in each source's header comment.  The old directory stays as published.
Fixes that do not change validation results can go into the current set.

Every node type shares the set's version.  The schemas check the
`version` member's pattern but do not pin its value, so nodes written
before a type took on the set's number (Catalog 0.5, SourceSet 0.1) still
validate.

## Structure notes

- `catobj` is the base for everything, and `node` adds what full nodes
  have.  `reference` is a catobj and is not a node.
- `catalog.json#/$defs/Child` lists what may appear under a `catalog`
  member.  `sourceset` uses it too.  Sourceset can't simply `$ref`
  catalog.json, because catalog's `unevaluatedProperties:false` only sees
  members evaluated inside catalog's own subschemas, so it would reject
  sourceset's extra members.
- Catalog, SourceSet and HttpStreamSrc each pin `type` with `const`.
  Without that, a plain Catalog would also match SourceSet and fail the
  child `oneOf`.
- Choices between alternative members (`name` or `label`, `urls` or
  `locations`) use `anyOf`, so that transitional nodes carrying both still
  pass.
- `httpstreamsrc.json5` still uses a draft parameter vocabulary that does
  not match the nodes dasflex emits, so real HttpStreamSrc nodes fail it
  for now.
