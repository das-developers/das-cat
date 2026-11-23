# Curating catalog nodes

This directory is the working instruction set for anyone, person or
software agent, who reviews the catalog nodes made from das2 servers and
improves the ones a mechanical conversion can't get right.

Read these in order:

1. `README.md` (this file): how the work is split and what you deliver.
2. `rules.md`: the rules a node must follow, with the reasons.
3. `survey.md`: how to look at the inputs before proposing anything.
4. `overrides.md`: how to write an override file.
5. `checks.md`: the checks an override must pass before it is offered
   for review.

## How the work is split

    das2 server                         the authority for what a dataset
      DSDF files                        offers; maintained by its owner
         |
         v
    src/scripts/dsdf_cat_import         mechanical, repeatable conversion
         |                              to catalog nodes; no judgment
         v
    src/overrides/<site>/...json5       reviewed, per dataset changes that
         |                              need judgment; applied every run
         v
    catalog nodes                       never edited by hand

The converter runs unattended and must give the same output for the
same input.  Anything it can't decide from the DSDF alone is not guessed
at; it is left plain, and a curator decides whether an override is
worth writing.  A curator comes back when a DSDF changes under an
override (the converter stops and says so) or when a new kind of source
appears.

## What you deliver

Not nodes.  A curation pass produces, for review by the catalog's owner:

- **Override files** under `src/overrides/<site>/<dataset path>.json5`,
  each saying in comments why it exists.
- **An upstream fix list**: things that are wrong or missing in a DSDF
  or a reader, with the dataset, the line, and where known the source
  file.  You do not edit DSDFs or readers yourself unless asked to.
- **Open questions** you could not settle from the inputs.

Every override is a proposal until the owner has read it.  Say plainly
what you checked and what you could not check (for example a dataset
that needs a login).

## First question for any change: who should make it?

1. Can the DSDF say it?  Then it goes on the upstream fix list.  Text
   (titles, help text, element descriptions, examples, contacts, units,
   coordinate and data lines) always can.  An override that restates
   DSDF text goes stale; one that the DSDF could replace should not
   exist.
2. Is it true of every dataset of this kind?  Then it is a converter
   change, not an override.  Propose it.
3. Is it a judgment about this one dataset that a DSDF has no words
   for?  That is an override.  The usual cases are in `rules.md`:
   where a choice belongs in the interface, one selector that mixes two
   kinds of thing, free text that is really a typed list, inverted
   toggles, and short captions.

## Tools

All paths are from the repository top.

    src/scripts/dsdf_cat_import     the converter; -h for options
    src/scripts/cat_override.py     the override format, and a preview
                                    program: NODE.json OVERRIDE.json5
    test/test_dsdf_cat_import.py    unit tests, no network
    test/validate_tree.py           schema check of a generated tree
    test/url_check.py               what every example sends, and a
                                    compare of two trees
    das_fetch (from das2C)          reads a node as a client does:
                                    'das_fetch node FILE' lists what a
                                    user sees, 'das_fetch url FILE KEY=VAL'
                                    shows what would be sent

Use a scratch directory that is not tracked for trees and downloads.
