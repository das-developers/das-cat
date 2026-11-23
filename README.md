# catalog-root
Contains the upper few nodes of the federated das2 data source catalog.  Redundant copy mirrored from das2.org for reliability.

## Layout

| Directory | Contents |
|---|---|
| `cat/` | Catalog nodes, strict JSON.  URLs inside published nodes point here, so paths under `cat/` should not move. |
| `schema/` | JSON Schemas for catalog nodes, strict JSON, one directory per node type and one file per version of it. |
| `src/` | Everything authored or run: schema sources, import scripts, the catalog browse CGI. |
| `test/` | Validation scripts, importer unit tests and example nodes. |

## Schemas

Schemas are published at `schema/<type>/v<version>.json`, for example

    https://raw.githubusercontent.com/das-developers/das-cat/main/schema/httpstreamsrc/v0.7.json

A node's own `type` and `version` members are enough to find its schema:
a `"type":"HttpStreamSrc", "version":"0.7"` node is described by
`schema/httpstreamsrc/v0.7.json`.  Nodes do not need a `$schema` member.

Each node type has a version of its own.  A SourceSet or a Catalog does
not change version because a kind of node it may list did.  What makes
that possible is one rule: every entry in a `catalog` member carries the
`type` of the thing it stands for.  A container's schema checks its
entries as references, or, for a node held in place, only that it says
what it is; the node itself is checked against the schema for its own
type and version.

| Node type | Version |
|---|---|
| Catalog | 0.5 |
| SourceSet | 0.2 |
| HttpStreamSrc | 0.7 |

Each schema file is self-contained, with relative ids, so a copy works
from any host or a local checkout and nothing else has to be fetched.

A published schema file is frozen.  Later edits may fix typos or
descriptions, but they do not change which nodes pass or fail.  Any
change of that kind is a new version of that type, in a new file beside
the old one.  Versions after 0.9 go to 1.0, not 0.10.

To validate nodes, run `make validate` from the repository root (needs
network access the first time, to build a Python venv).

## Generating site catalogs

Site catalogs are not written by hand.  `src/scripts/dsdf_cat_import`
reads the dataset definitions a das2 server offers and writes the nodes:
a Catalog per server directory, and per dataset a SourceSet with an
HttpStreamSrc under it.  The conversion is mechanical and repeatable.
Changes that take judgment are kept as reviewed override files under
`src/overrides/<site>/`, one per dataset, and applied by the importer
each time it runs.  `src/curation/` says when an override is called for,
how to write one and the checks it must pass.

    src/scripts/uiowa.sh OUT_DIR           # the U. Iowa site, both servers
    python3 test/test_dsdf_cat_import.py   # importer unit tests, no network
    test/validate_tree.py OUT_DIR          # every node against the schemas
    test/url_check.py urls TREE            # what each example sends (needs
                                           # das_fetch from das2C)
