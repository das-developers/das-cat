# Surveying the inputs

Look at everything before proposing anything.  A rule or an override
shaped by the first three datasets you read will be wrong for the
fourth; the hardest dataset on the server is the one to design against.

## 1. Take a snapshot

A das2 server lists its datasets and serves each definition:

    SERVER?server=list
    SERVER?server=dsdf&dataset=PATH

Save both for every dataset into a scratch directory, so the survey can
be rerun offline and so two servers that should hold the same
definitions can be compared.  Sites with mirrors list them in failover
order; the first server that has a dataset supplies its content and the
converter warns when a mirror's copy differs.

## 2. Run the converter and read every message

    src/scripts/dsdf_cat_import -n [-m MIRROR_URL] SERVER_URL / ROOT_URL OUT_DIR

`-n` writes nothing.  Messages fall in three groups:

- **ERROR, dataset not written**: the DSDF can't be converted as
  written.  Upstream fix list, with the line quoted.
- **WARNING**: converted, but something is off: an example range that
  does not parse, a dataset with no usable example, values wrapped in
  stray quotes, mirrors that differ, element descriptions that name no
  element.  Upstream fix list.
- Nothing: converted cleanly.  That is not the same as "good".

## 3. Read the nodes as a user would

For each dataset that has options:

    das_fetch node FILE

lists coordinates, data variables, formats and options with their types,
allowed values and titles.  Ask of each option:

- Is it about a coordinate, a variable or the format?  (rules.md 4)
  If it changes the coordinate range or the values that come out, look
  for its home under a coordinate or a variable first, and leave it an
  option only when none fits.  Names that give it away: `coords`,
  `frame`, `component`, `units`, `band`, `rate`, `channel`, `antenna`,
  `sensor`, and any option that lists the dataset's own outputs.
- Are several data variables the components of one vector?  Then they
  are one variable, and a frame choice is its property, not three
  variables whose names are only right in one frame.  (rules.md 4)
- Does a choice show the server's argument syntax, `--80khz`,
  `KEY=VALUE`?  (rules.md 13)
- Are there many switches that are one selection, or one list that is
  two kinds of thing?  (rules.md 5)
- Is a free text option really a number, a list of numbers, one of a few
  words?
- Does a switch named `no_x` turn a variable off?
- Would a user understand the caption without the title?

Datasets with no options rarely need anything.

## 4. Find out what an option means before moving it

A title is not always enough to know that "none selected" means "all",
or that picking one receiver drops the others.  In order of trust:

1. The reader's help text and argument handling, when the source is at
   hand.  Read it for meaning only (rules.md 3).
2. A short live request with and without the option, comparing size and
   the packet headers of the reply.
3. The dataset's technical contact, by way of the catalog owner.

Write down what you found and how in the override's comments.  If you
could not find out, do not guess: leave the option where it is and list
the question.

## 5. Count before generalizing

When a pattern looks general ("every `set:` should become a list",
"every `no_x` switch is an inverted enable"), list every dataset that
shows it and check the exceptions before proposing a converter change.
State the counts with the proposal.
