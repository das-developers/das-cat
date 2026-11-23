#!/usr/bin/env python3
"""Build one self-contained published schema from the schema sources.

Usage: schema_bundle.py SOURCE.json5 VERSION [OUTPUT]

The sources in src/schema/ refer to each other by file name
("$ref":"node.json", "node.json#/$defs/Contacts").  That is convenient to
write but ties every published schema to its neighbors, and the node types
are versioned one by one: an HttpStreamSrc schema may move to a new
version while Catalog stays where it is.  So each published schema carries
its own copy of what it uses.

SOURCE is read with every source it refers to, directly or through
another, from the same directory (node.json is node.json5 there).  Each
of those is placed under the output's "$defs", keyed by its file name and
keeping its "$id".  That is a JSON Schema 2020-12 compound document: a
"$ref" to "node.json" resolves to the copy inside the file, and nothing
else is fetched.  References are not rewritten, so a published schema
reads like its source.

The output's own "$id" is v<VERSION>.json, relative as all ids here are,
so a copy of the schema directory works from any host or checkout.

Output is tab indented with a trailing newline.  With no OUTPUT it goes to
standard output.  With OUTPUT a temporary file is written and renamed, so
a failed run does not leave a truncated target for make to consider fresh.
"""

import sys
import os
import json

from importlib.machinery import SourceFileLoader

def _json5():
	"""The JSON5 subset reader, from beside this file"""
	sPath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'json5_to_json.py')
	return SourceFileLoader('json5_to_json', sPath).load_module()

def _load(mod, sPath):
	with open(sPath, encoding='utf-8') as f: sText = f.read()
	try:
		return json.loads(mod.stripExtensions(sText), object_pairs_hook=mod.noDupKeys)
	except ValueError as e:
		raise ValueError("%s: %s"%(sPath, e))

def _refs(obj, lOut):
	"""File names of the other schemas an object refers to, in the order
	met.  '#/...' is a reference within the same schema and is left out."""
	if isinstance(obj, dict):
		for (sKey, val) in obj.items():
			if (sKey == '$ref') and isinstance(val, str):
				sFile = val.split('#')[0]
				if sFile and (sFile not in lOut): lOut.append(sFile)
			else:
				_refs(val, lOut)
	elif isinstance(obj, list):
		for val in obj: _refs(val, lOut)
	return lOut

def bundle(sSrc, sVer):
	"""The compound schema for source file sSrc as a dict.

	:raises ValueError: A source can't be read, a reference names a file
	   that is not a schema source, an id does not match its file name, or
	   the schema already has a "$defs" member of a file's name.
	"""
	mod = _json5()
	sDir = os.path.dirname(os.path.abspath(sSrc))
	dRoot = _load(mod, sSrc)
	sSelf = os.path.basename(sSrc)[:-len('.json5')] + '.json'

	# Everything reachable, each file once.  A schema may refer back to
	# the one being built; that copy is not needed, see below.
	dParts = {}
	lTodo = _refs(dRoot, [])
	while lTodo:
		sFile = lTodo.pop(0)
		if (sFile in dParts) or (sFile == sSelf): continue
		if ('/' in sFile) or not sFile.endswith('.json'):
			raise ValueError("%s: reference to '%s', which is not a schema source"%(sSrc, sFile))
		dPart = _load(mod, os.path.join(sDir, sFile + '5'))
		if dPart.get('$id') != sFile:
			raise ValueError("%s5: its $id is '%s', expected '%s'"%(
				os.path.join(sDir, sFile), dPart.get('$id'), sFile))
		dParts[sFile] = dPart
		lTodo += _refs(dPart, [])

	for dPart in dParts.values():
		if sSelf in _refs(dPart, []):
			# The root's id is its version, so its file name would resolve
			# to nothing.  No source needs this today.
			raise ValueError("%s: a schema it uses refers back to %s, which a "
			                 "bundle can't hold"%(sSrc, sSelf))

	dOut = {}
	for (sKey, val) in dRoot.items():
		dOut[sKey] = 'v%s.json'%sVer if sKey == '$id' else val
	if '$id' not in dOut:
		raise ValueError("%s: no $id"%sSrc)

	dDefs = dOut.setdefault('$defs', {})
	for sFile in sorted(dParts):
		if sFile in dDefs:
			raise ValueError("%s: $defs already has a member '%s'"%(sSrc, sFile))
		# The dialect is the bundle's; one $schema at the top is enough
		dDefs[sFile] = {k:v for (k, v) in dParts[sFile].items() if k != '$schema'}
	return dOut

def main(lArgs):
	if (len(lArgs) < 3) or (len(lArgs) > 4) or (lArgs[1] in ('-h', '--help')):
		sys.stderr.write(__doc__)
		return 3
	(sSrc, sVer) = lArgs[1:3]
	if not sSrc.endswith('.json5'):
		sys.stderr.write("ERROR: %s is not a .json5 schema source\n"%sSrc)
		return 3
	try:
		dOut = bundle(sSrc, sVer)
	except (OSError, ValueError) as e:
		sys.stderr.write("ERROR: %s\n"%e)
		return 7
	sOut = json.dumps(dOut, ensure_ascii=False, indent='\t') + '\n'

	if len(lArgs) == 3:
		sys.stdout.write(sOut)
		return 0
	sDest = lArgs[3]
	with open(sDest + '.tmp', 'w', encoding='utf-8') as f: f.write(sOut)
	os.rename(sDest + '.tmp', sDest)
	return 0

if __name__ == "__main__":
	sys.exit(main(sys.argv))
