# Overrides

Reviewed, per dataset changes applied by the importers after their
mechanical conversion, one directory per site:

    src/overrides/<site>/<dataset path as the server spells it>.json5

The file format is documented at the top of `src/scripts/cat_override.py`.
When and how to write one, and the checks it must pass, are in
`src/curation/`.

Each file records a hash of the server definition it was reviewed
against.  When the definition changes the importer stops on that dataset
and prints the new hash; review the override against the new definition
before updating it.
