# catalog-root
Contains the upper few nodes of the federated das2 data source catalog.  Redundant copy mirrored from das2.org for reliability.

## Layout

| Directory | Contents |
|---|---|
| `cat/` | Catalog nodes, strict JSON.  URLs inside published nodes point here, so paths under `cat/` should not move. |
| `schema/` | JSON Schemas for catalog nodes, strict JSON, one directory per schema set version. |
| `src/` | Everything authored or run: schema sources, import scripts, the catalog browse CGI. |
| `test/` | Validation script and example nodes. |

## Schemas

Schemas are published at `schema/v<version>/<type>.json`, for example

    https://raw.githubusercontent.com/das-developers/das-cat/main/schema/v0.7/catalog.json

Every node type in a set carries the set's version, so a node's own
`type` and `version` members are enough to find its schema: a
`"type":"HttpStreamSrc", "version":"0.7"` node is described by
`schema/v0.7/httpstreamsrc.json`.  Nodes do not need a `$schema` member.

Schema `$id` and `$ref` values are relative, so a copy of a version
directory works from any host or a local checkout.

A published version directory is frozen.  Later edits there may fix typos
or descriptions, but they do not change which nodes pass or fail.  Any
change of that kind goes into a new version directory.  Versions after
0.9 go to 1.0, not 0.10.

To validate nodes, run `make validate` from the repository root (needs
network access the first time, to build a Python venv).
