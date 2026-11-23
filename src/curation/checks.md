# Checks

An override is ready for review when all of these pass.  Run them from
the repository top.  TREE names are scratch directories of your own.

## 1. Unit tests

    python3 test/test_dsdf_cat_import.py

Also reads every file under `src/overrides` and checks it is filed
under the dataset it names and carries a hash.

## 2. The converter applies it

    src/scripts/dsdf_cat_import -o src/overrides/SITE \
        [-m MIRROR_URL] SERVER_URL / ROOT_URL TREE

Exit value 0, or 5 with only datasets you already know about.  Before a
node is written the converter checks it: every control names a
parameter and flag that exist, lists feed something that says how a
list travels, nothing offered sends a string the protocol section does
not list, names are identifiers, examples only set what can be set.
A dataset that fails is not written and the message says why.

Build two trees, one without `-o` and one with.

## 3. The schemas accept it

    make schema
    test/validate_tree.py TREE

The tree must have been made with an http(s) `ROOT_URL`.

## 4. Nothing sent has changed

    test/url_check.py compare PLAIN_TREE OVERRIDE_TREE -o src/overrides/SITE

It must report no differences.  When the converter itself changed,
compare a tree made before the change with one made after in the same
way.  These trees are made with a `file://` `ROOT_URL` so das_fetch can
read them in place.  An intended difference
needs a `urlChange` member in the override and the owner's agreement
(rules.md 1).

Examples do not exercise every control.  For each property an override
touched, compare by hand what the plain node and the overridden node
send for the same selection:

    das_fetch url -o params PLAIN_NODE    0 mfr=1,2,Ex
    das_fetch url -o params OVERRIDE_NODE 0 mfr_bands=1,2 mfr_sensors=Ex

A control that gained a default sends nothing when the default is
chosen, where it used to send the choice.  That is the point of a
default, but say so in the override's comments, with what tells you the
server treats the two requests alike.

## 5. It reads well

    das_fetch node OVERRIDE_NODE

Read the listing as someone who has never seen the dataset.  Captions
short, titles one line, each choice in the section it is about, nothing
shown as a default that is not one.

## 6. The server agrees

Where the dataset can be read without a login, make one short request
per changed control and look at the reply: its size, its packet
headers, any message from the reader.  An empty reply is a finding to
report, not necessarily a fault of the override; compare with the same
request made through the plain node.  State in the override's comments,
or in your report, which controls were checked live and which only at
URL level.

## What to hand over

- The override files.
- The results of checks 1 to 4, as counts.
- The hand comparisons from check 4 and the live requests from check 6.
- The upstream fix list and open questions.
