# Das Federated Catalog

The federated catalog is intended to replace the `server=list` and 
`server=dsdf` end points for individual das2 servers.  Full navigation
of the catalog will be documented upon reaching version 1.0.

This repository contains:

1. The upper few nodes of the catalog for reliablity in case das.org is down.

2. JSON5 Schemas for validating nodes.

3. Importers for data from `server=list` and `server=dsdf` endpoints on
   das2 servers.

## Checking nodes

To check catalog nodes against un-deployed schemas, use the following,
run from the root directory:

```bash
python -m pip install jsonschema check-jsonschema json5
check-jsonschema -v \ 
  --base-uri $(pwd)/schemas/ \   # <-- Trailing slash required
  --schemafile $(pwd)/schemas/catalog.json5 \
  /path/to/your/*.json
```

Once schemas are deployed, some validators may be able to retreive the
necessary schema documents via the embedded `$schema` properties.



