# HttpStreamSrc: how settings become a request

The schema, `schema/httpstreamsrc/v0.7.json`, says which nodes are well
formed.  This page says what a well formed node means: given a node and
a person's settings, which URL is requested.  Programs that write nodes
(dasflex, `src/scripts/dsdf_cat_import`) and programs that read them
(das2C) hold to the same rules, so that a node means one thing.

It covers HttpStreamSrc 0.7.  das2C follows these rules from version
3.0.6 on; items marked *3.0.6* are not understood by earlier clients.

## The two sections

    interface   what a person or program may ask for, with all the
                captions and titles
    protocol    what the server takes, and nothing else

A property in the interface that can be changed has a `set` block that
names the protocol parameter its value travels in, and for a parameter
built from flags, which flag:

    "interface": {"options": {"props": {
        "rate": {"type": "enum", "value": "10khz",
                 "set": {"param": "params", "flag": "rate",
                         "enum": [{"value": "10khz", "pval": "--10khz"},
                                  {"value": "80khz", "pval": "--80khz"}]}}
    }}},
    "protocol": {"httpParams": {"params": {"flagSep": " ", "flags": {
        "rate":  {"prefix": "", "enum": ["--10khz", "--80khz"]},
        "no_Ex": {"value": "--Ex=false"}
    }}}}

Here `rate=80khz` in a request sends `params=--80khz`.

The interface may be rearranged, a choice moved from the options to a
data variable, without changing what is requested, because the request
text is settled by the protocol section alone.

## What one property sends

- A value equal to the property's default is not sent, unless the
  property is required.  A required property with a default is sent even
  when the request says nothing about it.
- A boolean sends in one state only, the one `set.value` names, true if
  not given.  The other state is the server's default and is silent.
- An enum sends the chosen item's `pval`, or its `value` when it has no
  `pval`.  An item may instead name a `flag`, which picking the item
  switches on.
- Anything else sends the value as given.
- An empty value in a request takes back what an earlier entry for the
  same property set.  That is how a setting made after an example undoes
  one of the example's settings.
- When all properties have spoken, every protocol parameter marked
  required must be present, or no URL is made.

## Parameters and flags

A plain parameter carries one value, and the last property to speak
wins.  With `subSep` every property that feeds it adds an element,
joined with that text: `read.data=a,b`.  With `"repeat": true` each
element is sent as a pair of its own: `parameter=bx&parameter=bz`.
(*3.0.6*)

A parameter with `flags` is assembled from pieces, one per flag sent,
joined with `flagSep` (a blank if not given).  A flag is one of:

- A switch, fed by a boolean.  It sends its `value`, or its own name if
  it has none.
- A slot, fed by anything else.  It sends `prefix`, the value, and
  `suffix` if there is one (*3.0.6*): `{"prefix": "--win=", "suffix":
  "s"}` sends `--win=2.5s`.

A slot with `subSep` joins everything sent to it behind one prefix,
`-lfdr ExEw` or `fan=090,270`, and is closed by its suffix once.  A
switch on such a flag sends its `set.pval` as its element.  A slot with
`"repeat": true` is sent whole once per item: `-n bad_data -n fake_data`.

The names of flags are for `set.flag` to point at.  They are not sent.

### Order

- Flags are sent in the order the protocol section lists them, whatever
  order the interface has their properties in.  (*3.0.6*; earlier
  clients use interface order, so writers should keep the two the same.)
- Elements joined into one flag or parameter go in the order of the
  properties that supply them.
- The items of an enumerated list go in the order the node lists the
  choices, whatever order they were picked in.

One selection therefore makes one URL, which matters to servers that
cache by request text.

## The protocol section names its own strings

A slot, or a plain parameter, may carry an `enum`: every string the
server takes there, or takes as one element there when values are
joined or repeated.  The interface can then show people other words:

    interface item   {"value": "80khz", "pval": "--80khz"}
    protocol flag    {"prefix": "", "enum": ["--10khz", "--80khz"]}

Every string about to be sent is compared with that list, exactly, as
text (so 256 and "256" match, 1 and 1.0 do not), each item of a list on
its own.  Where a flag has a prefix and suffix the list is of what goes
between them.  A string that is not listed makes no URL.  For a choice
that means the node's two sections disagree and the node is at fault;
for typed text it means the value is refused.

With no `enum` anything is sent, as suits times, numbers and free text.
A default is not sent, so a choice that is the server's own default
needs no listed string.  The list says which strings exist, not which
may be combined.

## Lists

(*3.0.6*)  A property with `"multi": true` holds a list: the sensors to
output, the frequencies to remove.  Its `type`, `set.enum` and
`set.range` describe one item.  `"multi": [2, 24]` also bounds the
number of items when a list is given at all; an empty list, nothing
selected, sends nothing.  A boolean is not a list.

Nodes write list values, defaults and example settings, as JSON lists.
An item may not hold a comma or appear twice.

What a list feeds says how its items travel: a parameter or flag with
`subSep` joins them, one with `repeat` sends them one at a time.  A node
that gives neither is refused.

## A joined value is sent whole

Several properties may feed one joined value, a band list and a sensor
list making `-hfr ABEx`.  The server sees a single value, so it is sent
whole or not at all: if any of those properties is off its default, the
others send their defaults too.  `-hfr Ew` alone would be read by the
server as "no bands".

## One of several

Groups whose `enabled` toggles share an `xorGroup` name are an exclusive
set, radio buttons.  The formats of a source are one, named "format",
and data variables may form others.  The node writes each member as a
plain boolean, and at most one is on by default.  Readers keep the rule:

- The last member a request switches on is on and the rest are off,
  whatever their defaults or earlier entries (an example's) said.
- Switching none on leaves the node's choice.  Switching that one off
  without choosing another is refused; there is no "none" to ask a
  server for.
- A member that is off sends nothing, defaults and required settings
  included.  A value given for a setting of a member that is off is
  refused as a contradiction.
- A required setting inside a member is asked for only while that
  member is on.
- A node with two members on by default is broken, and gets no URL
  until a request says which is meant.

das2C 3.0.6 enforces all of this.  Earlier clients treated each toggle
as a boolean of its own.

## Around the node

A client may let its user add raw parameters, text that goes into the
URL as given (`das_fetch -p`, das2C `DasReq_setRaw()`).  They are put on
last, override what the node would have sent, and are not checked
against anything.  They are the one way around a node and have to be
asked for.

Values are percent encoded.  das2C leaves `: / @ , =` plain so that
times stay readable; servers decode either form the same way.

Each of `protocol.baseUrls` is a mirror, tried in order.  If a base URL
has no `?` the client adds one before the first pair, else it adds `&`.
