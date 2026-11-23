# Rules for catalog nodes

Each rule has its reason, because the reason is what tells you how to
apply it to a case this file did not foresee.

## 1. What is sent must not change

Clients have years of saved requests (over a thousand Autoplot .vap
files for Juno alone) that carry parameter strings.  Servers cache by
the exact request text.  So:

- For any choice a dataset already offered, the bytes sent must stay the
  same.  Restructuring the interface is fine; changing what a control
  sends is not.
- Do not add a choice the DSDF does not offer, not even a reader's
  documented default written out.  A request that spells out a default
  misses the cache that the same request without it would hit.  New
  choices need the dataset owner's explicit agreement first.
- Order matters.  Flags are sent in the order the protocol section
  lists them, so leave that order as converted.  The elements joined
  into one flag (`-mfr 12Ex`) are sent in the order of the properties
  that supply them and, within a list, the order of its choices, so a
  split or a reordering of those changes what is sent unless it keeps the
  DSDF's element order.  Moving a property to another section does not
  change what is sent (clients on das2C 3.0.6 or later).

`test/url_check.py compare` checks the examples.  For controls no
example uses, check by hand with `das_fetch url`.

## 2. The DSDF is the authority

Where a DSDF and anything else disagree, the DSDF is right, and where
the DSDF is wrong it gets fixed at its source.  Do not paper over a DSDF
problem in an override or ask for a special case in the converter.  The
converter refuses a DSDF it can't convert as written (an illegal token,
a param outside the structured sub-values form) and names the problem,
so the fix happens upstream.

## 3. Only what the DSDF exposes

If a reader has an option the DSDF does not list, assume that was on
purpose.  Reading reader source or help text is the right way to learn
what an exposed option means; it is not a source of new options.

## 4. A choice goes in the section it is about

The interface has four sections.

- `coords`: a choice about a coordinate, its range, its resolution, a
  band of it.
- `data`: a choice about a variable.  A variable that can be left out or
  added has a boolean `enabled` property.  A reader that takes a list of
  fields or variables to output is variable selection, however its
  DSDF spells it.
- `formats`: a choice about the output serialization.
- `options`: only what is about none of the above.

Options is where a conversion puts everything, so it is where to look.
An option that changes the range of a coordinate, or the values a
variable comes out with, belongs to that coordinate or variable: try to
place it there, and leave it an option only when it fits neither.

"Variable" here is meant as a CDF variable is: a vector is one
variable.  Three outputs that are the components of one field are one
entry under `data`, and the frame they are given in is a property of
it (`data/B/props/frame`), since in another frame the same columns are
other components.

A form is drawn section by section.  A user looking for "which
variables do I get" looks under data, and a client that knows nothing
about a source can still offer "turn this variable off" if the toggle is
where toggles go.

## 5. One selector or several switches

Several values for one thing ("which sensors", "which frequencies to
notch out") is one property with `"multi": true`: a list.  Independent
things that each stand alone (a data variable, a correction to apply)
are a boolean each.

A das2 `set:` param is one selector and converts to one list.  If its
elements are really two kinds of thing, bands and sensors say, split it
into two lists that fill the same flag, in the DSDF's element order.

## 6. Defaults are only written when they are true

A property's `value` is what is in effect when a request says nothing.
Write a default only if a form showing it would be telling the truth in
every state.  Counter example: a reader where choosing any receiver
replaces the default set for all receivers.  Showing the defaults
ticked would show receivers as on that the request has just turned off.
Leave such values empty and let the title or description say what
happens.

Likewise say so, in a description, when "nothing selected" means
"everything" (a reader that outputs all fields unless some are named).

Defaults on properties that fill one joined flag are safe in one
respect: a client sends such a flag whole, so when the user changes the
sensors the default bands travel with them.  That holds within a flag,
not between flags.

## 7. Names people type are identifiers

Group and property names become keys (`das_fetch ... time.min=...`,
`data.r.enabled=false`) and GUI ids.  They must match
`[A-Za-z_][A-Za-z0-9_]*`, at most 63 characters, lower case preferred.
What is sent to the server is separate (`pval`, flag `value`, `prefix`,
`suffix`) and may be anything.  If the natural name is not what the
server wants,
name it well and send the server's spelling: an HFR band named `HF1`
that sends `1`.

Renaming a key breaks saved requisitions that use it.  Rename only when
a node is new or the gain is clear, and say so in the override.

## 8. label and title

`label` is a short caption for tight spaces, a few words.  `title` is
the one line explanation beside it.  `description` is longer help.  The
converter can only use a DSDF token as the label; better captions are a
fair use of an override.  Do not restate DSDF titles in overrides.

## 9. Coordinates are physical dimensions

A coordinate is a dimension the data live in: time, frequency, energy.
Reference and offset arrays that only exist to pack a stream (sample
offsets within a waveform capture) are not coordinates and get no entry.

## 10. Ranges

Every range has an exclusive upper end, `set.range` included.  To let a
largest legal value through, the bound sits just above it.

## 11. Examples are small and belong in the DSDF

An example is a request a new user will run without thinking.  Keep the
reply under about 20 MB, never over 100 MB; a cached dataset can afford
a longer span than an uncached one.  Examples come from DSDF
`exampleRange_NN` and `exampleParams_NN` lines, so a missing or
oversized example is an upstream fix, not an override.

## 12. Be a polite client

Surveys read `server=list` and `server=dsdf`, which are cheap.  Live
data checks use short time ranges.  Do not run long uncached reads, do
not hammer a server in parallel, and do not look for credentials: a
dataset behind a login is reported as "checked at URL level only".

## 13. Each section has its own strings

The interface section is a contract with people and with the programs
they write: property names and choice values end up in scripts and
saved requests.  The protocol section is a contract with the server:
what it takes, spelled as it takes it.  The two change for different
reasons and should be able to.

- The protocol names its strings.  A switch has its `value`.  A flag
  with a prefix, or a parameter of its own, that takes one of a fixed
  set of strings lists them in an `enum` of its own, a plain list.
  One that takes any number, time or text has no list.  The converter
  writes that `enum` from DSDF `option:` and `set:` lists.  It is not
  the interface's `set.enum`, which holds the choices a person sees.
- The interface shows words fit for a person.  When the server's string
  will do, the choice is that string and nothing more is said.  When it
  will not, the choice has a plain `value` and a `pval` naming the
  listed string it stands for: `{"value": "80khz", "pval": "--80khz"}`.
  The converter does this for strings with leading dashes; anything
  else that reads as argument syntax is an override.
- Nothing the interface offers may send a string the protocol does not
  list.  The converter and das2C both refuse that.
- One choice may have no string: the default the server gives when the
  request says nothing.  It is written as the property's `value`, which
  is not sent.  Not for a required control, and not for a part of a
  joined flag.
- The list says which strings exist.  It does not say which go
  together, and titles and descriptions still have to.
- The protocol section has no user strings: no label, title or name on
  a parameter or flag.  What it may have is a `comment`, one string, a
  note for a developer reading that section by itself.  The converter
  fills it with the DSDF's own title and paramInfo text.  Clients do
  not show it, and an override that rewords the interface leaves it
  alone, so the server author's wording stays on record.

Decide the interface words before a node is first published.  A `pval`
can be added behind a published choice at any time without breaking a
client; the choice's own value can't be changed afterwards.

## 14. A stub says what it stands for

Where a node holds something about another node, an entry in a
`catalog` list or a summary of a source inside a SourceSet, that entry
carries the `type` of the thing it stands for.  A reader can then deal
with the entry without fetching its target, and each node type can
change version without the nodes that point at it changing with it.
