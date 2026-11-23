# Writing an override

An override is a small file of named changes that the converter applies
to one dataset's source node after converting it.  The format, with
every operation, is documented at the top of
`src/scripts/cat_override.py`.  This file is about using it well.

## Where it goes

    src/overrides/<site>/<dataset path as the server spells it>.json5

for example `src/overrides/uiowa/Cassini/RPWS/Survey.json5`.  The
converter is pointed at the site directory with `-o`.

## The members

    {
       // Why this file exists.  Written for the person who will review
       // it and the person who will find it stale in two years.
       "dataset": "Cassini/RPWS/Survey",
       "dsdf":    "sha256:834ce215aa1b544d",
       "ops": [ ... ]
    }

- `dataset` must be the dataset the file is filed under.  It catches a
  copied file that was not edited.
- `dsdf` is the hash of the DSDF lines the node's structure comes from
  (params, coordinate, data and item lines, examples).  If the DSDF
  changes there, the converter refuses to apply the override, does not
  write the dataset, and prints the new hash.  That is the signal to
  read the override against the new DSDF.  Only then copy the new hash
  in.  To get the hash for a new override, leave `"dsdf": null`, run the
  converter and read it from the message.
- `urlChange`, optional, a sentence.  Present only when the override
  changes what an existing example sends, on purpose and with the
  owner's agreement.  It is what lets `test/url_check.py` pass.
- `ops`, the changes, in order.

Comments are part of the deliverable.  Say what the DSDF has, why that
is not enough, what the override does about it, and what you verified.
If you decided not to do something obvious (write defaults, rename a
key), say that too, so the next reader does not "fix" it.

## Ops in one page

    {"op": "test",    "path": P, "value": V}    stop unless P holds V
    {"op": "add",     "path": P, "value": V}    new member, or array insert
    {"op": "replace", "path": P, "value": V}    P must exist; keeps its place
    {"op": "remove",  "path": P}
    {"op": "move",    "from": F, "path": P}
    {"op": "copy",    "from": F, "path": P}

Paths are JSON Pointers into the node: `/interface/options/props/mfr`,
`/protocol/httpParams/params/flags/mfr/subSep`, array items by index,
`/interface/options/props/hfr/set/enum/3`.

Extensions: a `*` segment runs the op for every member at that point;
`"before"` and `"after"` place a new object member; add, move and copy
make missing parent objects; a move within one object is a rename in
place; and example settings follow a moved property.

Preview one override on one node without running the converter:

    src/scripts/cat_override.py NODE.json OVERRIDE.json5 | less

## Habits that keep overrides small and honest

- **Change, don't restate.**  To split a list in two, copy it and remove
  the elements that do not belong, rather than typing both lists out.
  Titles and element descriptions then keep coming from the DSDF.
- **Guard what you count on.**  If an op removes "element 3", put a
  `test` before it that element 3 is what you think it is.  If a flag
  must have a certain prefix for the change to be safe, test it.
- **Move, don't remove and add,** when a property keeps its meaning, so
  examples that set it follow it.  When the meaning flips (a `no_r`
  switch becoming an `enabled` toggle that is on by default) remove and
  add instead: a moved `true` would then mean the opposite.
- **Leave the protocol alone** unless the interface change needs it.
  The usual reason is giving a flag the `subSep` a list needs.
- **One reason per file.**  If a dataset needs two unrelated changes,
  they can share a file, but each gets its own comment block.
- **Keep order on purpose.**  A new property goes where the one it
  replaces was (`"before"`).  Among properties that fill the same flag,
  property order is send order.

## Patterns

Options that are variable selection, with no variables listed in the
DSDF (each option becomes a variable with an `enabled` toggle):

    {"op": "move", "from": "/interface/options/props/*",
                   "path": "/interface/data/*/props/enabled"},
    {"op": "move", "from": "/interface/data/*/props/enabled/title",
                   "path": "/interface/data/*/title", "before": "props"},
    {"op": "move", "from": "/interface/data/*/props/enabled/label",
                   "path": "/interface/data/*/label", "before": "title"},
    {"op": "remove", "path": "/interface/options"}

An inverted switch on a variable the DSDF does list:

    {"op": "add", "path": "/interface/data/r/props/enabled",
     "value": {"type": "boolean", "value": true,
               "set": {"param": "params", "flag": "no_r", "value": false}}},
    {"op": "remove", "path": "/interface/options/props/no_r"}

Free text that is a bounded list of numbers:

    {"op": "add", "path": "/protocol/httpParams/params/flags/NOTCHES/subSep", "value": " "},
    {"op": "replace", "path": "/interface/options/props/NOTCHES/type", "value": "real"},
    {"op": "add", "path": "/interface/options/props/NOTCHES/multi", "value": [1, 24], "after": "type"},
    {"op": "replace", "path": "/interface/options/props/NOTCHES/value", "value": []},
    {"op": "add", "path": "/interface/options/props/NOTCHES/set/range", "value": [0.0, 14.41]}

A value with a better name than the server's spelling:

    {"op": "replace", "path": ".../set/enum/3/value", "value": "HF1"},
    {"op": "add",     "path": ".../set/enum/3/pval",  "value": "1"}

Working examples of each are under `src/overrides/uiowa/`.
