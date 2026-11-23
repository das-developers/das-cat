#!/usr/bin/env python3

"""Apply a reviewed override file to a generated catalog node.

Importers convert server definitions to catalog nodes mechanically.  Some
nodes need judgment a conversion table does not have: a server option
that is really a choice of data variable belongs under 'data', one
selector that mixes two kinds of thing reads better as two.  Those edits
live in override files, one per dataset, kept beside the importer and
reviewed like code.  The importer applies them every time it runs, so a
node is always "conversion, then these named changes", never a hand
edited file.

An override file is JSON with comments and trailing commas (the subset
json5_to_json.py reads)::

   {
      // Why, in comments.  Reviewers read these.
      "dataset": "Juno/WAV/Housekeeping",  // server path it is for
      "dsdf":    "sha256:0123456789abcdef",// definition it was reviewed against
      "ops": [
         {"op": "move", "from": "/interface/options/props/*",
                        "path": "/interface/data/*/props/enabled"},
         ...
      ]
   }

``ops`` are JSON Patch (RFC 6902) operations on JSON Pointer (RFC 6901)
paths into the node: add, remove, replace, move, copy and test, with the
RFC's meaning, plus these extensions:

  * ``*`` as one whole path segment stands for every member of the object
    at that point.  The op is run once per member, and ``*`` segments in
    the op's other path are replaced with the member's name.  The members
    are taken from ``from`` for move and copy, from ``path`` otherwise.
    Matching nothing is an error, and so is a wildcard move or copy whose
    ``path`` has no ``*``, since every member would land on one target.
  * add, move and copy create missing parent objects.
  * add, move and copy into an object take ``"before": KEY`` or
    ``"after": KEY`` to place the new member.  Without one it goes last,
    except that a move within one object, a rename, keeps its place.  A
    move of a member onto itself with a placement just reorders it.
    Order matters: clients send list items in property order and servers
    may cache by the exact request text.
  * Example settings follow a move.  A setting keyed
    ``options/props/p12v`` becomes ``data/p12v/props/enabled`` when
    ``/interface/options/props/p12v`` is moved there, and moving a whole
    group or section renames every setting under it.  Only the key
    follows: if the move also changes what a value means (a list split
    in two, a switch whose sense flips) the override must set the
    example right itself.

``test`` is the guard against a definition that changed under the
override: a test that fails stops the override, and the node is not
written.  It compares as JSON does, so true is not 1.

Run as a program to preview one override on one node::

   cat_override.py NODE.json OVERRIDE.json5 > patched.json
"""

import sys
import os
import re
import json
import copy

from importlib.machinery import SourceFileLoader

g_lOps   = ('add', 'remove', 'replace', 'move', 'copy', 'test')
g_lKeys  = ('dataset', 'dsdf', 'urlChange', 'ops')

# str.isdigit() is true for superscripts and other scripts' digits
g_reIndex = re.compile(r'^(0|[1-9][0-9]*)$', re.ASCII)

class OverrideError(Exception):
	"""An override that can't be read or does not apply to its node"""
	pass

##############################################################################
# Reading

def _json5():
	"""The repository's JSON5 subset reader, loaded from beside this file
	so that overrides and schema sources are read by one piece of code"""
	sPath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'json5_to_json.py')
	return SourceFileLoader('json5_to_json', sPath).load_module()

def loadOverride(sFile):
	"""Read and shape check an override file.

	:param sFile: Path of the override, JSON with comments and trailing
	   commas.
	:returns: The override as a dict with every optional member present:
	   dataset (may be None), dsdf (may be None), urlChange (may be None)
	   and ops.
	:raises OverrideError: Unreadable, not that subset of JSON5, an unknown
	   member, or an op that is not one of the six with the members it
	   needs.
	"""
	mod = _json5()
	try:
		with open(sFile, encoding='utf-8') as f: sText = f.read()
		dOver = json.loads(mod.stripExtensions(sText), object_pairs_hook=mod.noDupKeys)
	except (OSError, ValueError) as e:
		raise OverrideError("%s: %s"%(sFile, e))

	if not isinstance(dOver, dict):
		raise OverrideError("%s: an override is an object"%sFile)
	for sKey in dOver:
		if sKey not in g_lKeys:
			raise OverrideError("%s: unknown member '%s'"%(sFile, sKey))

	dOver.setdefault('dataset', None)
	dOver.setdefault('dsdf', None)
	dOver.setdefault('urlChange', None)

	lOps = dOver.get('ops')
	if not isinstance(lOps, list) or not lOps:
		raise OverrideError("%s: no ops"%sFile)
	for (i, dOp) in enumerate(lOps):
		sAt = "%s: op %d"%(sFile, i)
		if not isinstance(dOp, dict) or (dOp.get('op') not in g_lOps):
			raise OverrideError("%s is not one of %s"%(sAt, ', '.join(g_lOps)))
		sOp = dOp['op']
		lNeed = ['path']
		if sOp in ('move', 'copy'): lNeed.append('from')
		if sOp in ('add', 'replace', 'test'): lNeed.append('value')
		lMay = ['op', 'before', 'after'] if sOp in ('add', 'move', 'copy') else ['op']
		for sKey in lNeed:
			if sKey not in dOp:
				raise OverrideError("%s (%s) has no '%s'"%(sAt, sOp, sKey))
		for sKey in dOp:
			if sKey not in lNeed + lMay:
				raise OverrideError("%s (%s) has an unknown member '%s'"%(sAt, sOp, sKey))
		if ('before' in dOp) and ('after' in dOp):
			raise OverrideError("%s (%s) has both before and after"%(sAt, sOp))
		for sKey in ('path', 'from', 'before', 'after'):
			if (sKey in dOp) and not isinstance(dOp[sKey], str):
				raise OverrideError("%s (%s) member '%s' is not a string"%(sAt, sOp, sKey))
	for sKey in ('dataset', 'dsdf', 'urlChange'):
		if (dOver[sKey] is not None) and not isinstance(dOver[sKey], str):
			raise OverrideError("%s: member '%s' is not a string"%(sFile, sKey))
	return dOver

##############################################################################
# JSON Pointers

def _ptr(sPath):
	"""A JSON Pointer to its list of reference tokens"""
	if sPath == '': return []
	if not isinstance(sPath, str) or not sPath.startswith('/'):
		raise OverrideError("'%s' is not a JSON Pointer, it must start with '/'"%sPath)
	return [s.replace('~1', '/').replace('~0', '~') for s in sPath[1:].split('/')]

def _str(lPtr):
	return ''.join('/' + s.replace('~', '~0').replace('/', '~1') for s in lPtr)

def _index(lCont, sTok, bAppend, lPtr):
	"""An array index token to an int.  '-' is one past the end, allowed
	only where a new element may go."""
	if (sTok == '-') and bAppend: return len(lCont)
	if not g_reIndex.match(sTok):
		raise OverrideError("'%s' is not an array index, at %s"%(sTok, _str(lPtr)))
	n = int(sTok)
	if n > len(lCont) - (0 if bAppend else 1):
		raise OverrideError("%s is past the end of the array"%_str(lPtr))
	return n

def _step(cont, sTok, lPtr):
	"""One existing member or element"""
	if isinstance(cont, dict):
		if sTok not in cont: raise OverrideError("%s does not exist"%_str(lPtr))
		return cont[sTok]
	if isinstance(cont, list):
		return cont[_index(cont, sTok, False, lPtr)]
	raise OverrideError("%s is inside a value that is not an object or an array"%_str(lPtr))

def _get(doc, lPtr):
	cont = doc
	for (i, sTok) in enumerate(lPtr): cont = _step(cont, sTok, lPtr[:i+1])
	return cont

def _parent(doc, lPtr, bCreate):
	"""The container the last token of lPtr is in.  With bCreate missing
	objects on the way are made, last in their parents."""
	if not lPtr: raise OverrideError("The whole node can't be the target of an op")
	cont = doc
	for (i, sTok) in enumerate(lPtr[:-1]):
		if bCreate and isinstance(cont, dict) and (sTok not in cont):
			cont[sTok] = {}
		cont = _step(cont, sTok, lPtr[:i+1])
	if not isinstance(cont, (dict, list)):
		raise OverrideError("%s is inside a value that is not an object or an array"%_str(lPtr))
	return cont

def _place(dCont, sKey, value, sBefore, sAfter, lPtr):
	"""Set a member of an object at a chosen place.  A member that already
	exists is replaced where it is unless a place is given."""
	sRef = sBefore if sBefore is not None else sAfter
	if sRef is None:
		dCont[sKey] = value
		return
	if sRef == sKey:
		raise OverrideError("%s can't be placed before or after itself"%_str(lPtr))
	if sRef not in dCont:
		raise OverrideError("No member '%s' to place %s %s"%(
			sRef, _str(lPtr), 'before' if sBefore is not None else 'after'))
	lItems = [(k, v) for (k, v) in dCont.items() if k != sKey]
	n = [k for (k, v) in lItems].index(sRef) + (0 if sBefore is not None else 1)
	lItems.insert(n, (sKey, value))
	dCont.clear()
	dCont.update(lItems)

def _add(doc, lPtr, value, sBefore=None, sAfter=None):
	cont = _parent(doc, lPtr, True)
	if isinstance(cont, dict):
		_place(cont, lPtr[-1], value, sBefore, sAfter, lPtr)
	else:
		if (sBefore is not None) or (sAfter is not None):
			raise OverrideError("before and after place object members, %s is an "
			                    "array element, use its index"%_str(lPtr))
		cont.insert(_index(cont, lPtr[-1], True, lPtr), value)

def _remove(doc, lPtr):
	cont = _parent(doc, lPtr, False)
	_step(cont, lPtr[-1], lPtr)   # must exist
	if isinstance(cont, dict): return cont.pop(lPtr[-1])
	return cont.pop(_index(cont, lPtr[-1], False, lPtr))

def _replace(doc, lPtr, value):
	cont = _parent(doc, lPtr, False)
	_step(cont, lPtr[-1], lPtr)
	if isinstance(cont, dict): cont[lPtr[-1]] = value   # keeps its place
	else: cont[_index(cont, lPtr[-1], False, lPtr)] = value

##############################################################################
# Ops

def _expand(doc, dOp):
	"""The concrete ops a wildcard op stands for, itself if it has none"""
	sBind = 'from' if dOp['op'] in ('move', 'copy') else 'path'
	lBind = _ptr(dOp[sBind])
	if '*' not in lBind:
		if '*' in _ptr(dOp['path']):
			raise OverrideError("'*' in path needs a '*' in from to take names from")
		return [dOp]
	if lBind.count('*') > 1:
		raise OverrideError("%s has more than one '*'"%dOp[sBind])

	n = lBind.index('*')
	cont = _get(doc, lBind[:n])
	if not isinstance(cont, dict):
		raise OverrideError("%s is not an object, '*' has no members to "
		                    "stand for"%_str(lBind[:n]))
	if not cont:
		raise OverrideError("%s matches nothing"%dOp[sBind])
	if sBind == 'from':
		lPath = _ptr(dOp['path'])
		if ('*' not in lPath) and (lPath[-1:] != ['-']):
			raise OverrideError("%s names several members but path %s only one "
			                    "place, give path a '*' too"%(dOp['from'], dOp['path']))

	lOut = []
	for sKey in list(cont):
		d = dict(dOp)
		for s in ('from', 'path'):
			if s in d: d[s] = _str([sKey if t == '*' else t for t in _ptr(d[s])])
		lOut.append(d)
	return lOut

def _same(a, b):
	"""Equality as JSON has it: Python's True == 1 is not wanted here"""
	if isinstance(a, bool) or isinstance(b, bool):
		return isinstance(a, bool) and isinstance(b, bool) and (a == b)
	if isinstance(a, dict) and isinstance(b, dict):
		return (set(a) == set(b)) and all(_same(a[k], b[k]) for k in a)
	if isinstance(a, list) and isinstance(b, list):
		return (len(a) == len(b)) and all(_same(x, y) for (x, y) in zip(a, b))
	if isinstance(a, (dict, list)) or isinstance(b, (dict, list)): return False
	return a == b

def _doOp(doc, dOp):
	sOp = dOp['op']
	lPath = _ptr(dOp['path'])

	if sOp == 'add':
		_add(doc, lPath, copy.deepcopy(dOp['value']), dOp.get('before'), dOp.get('after'))
	elif sOp == 'remove':
		_remove(doc, lPath)
	elif sOp == 'replace':
		_replace(doc, lPath, copy.deepcopy(dOp['value']))
	elif sOp == 'test':
		val = _get(doc, lPath)
		if not _same(val, dOp['value']):
			raise OverrideError("%s is %s, the override expects %s"%(
				dOp['path'], json.dumps(val), json.dumps(dOp['value'])))
	else:
		lFrom = _ptr(dOp['from'])
		if sOp == 'copy':
			_add(doc, lPath, copy.deepcopy(_get(doc, lFrom)), dOp.get('before'), dOp.get('after'))
			return
		sBefore = dOp.get('before')
		sAfter = dOp.get('after')
		contFrom = _parent(doc, lFrom, False)
		_step(contFrom, lFrom[-1], lFrom)   # must exist, even to stay put
		if lFrom == lPath:
			# onto itself: nothing moves, but a placement reorders
			if (sBefore is not None) or (sAfter is not None):
				_add(doc, lPath, _remove(doc, lFrom), sBefore, sAfter)
			return
		if lPath[:len(lFrom)] == lFrom:
			raise OverrideError("%s can't be moved into itself"%dOp['from'])

		# A rename keeps the member where it was unless told otherwise
		if (sBefore is None) and (sAfter is None) and isinstance(contFrom, dict) \
		   and (lFrom[:-1] == lPath[:-1]) and (lPath[-1] not in contFrom):
			lItems = [(lPath[-1] if k == lFrom[-1] else k, v) for (k, v) in contFrom.items()]
			contFrom.clear()
			contFrom.update(lItems)
		else:
			_add(doc, lPath, _remove(doc, lFrom), sBefore, sAfter)
		_followMove(doc, lFrom, lPath)

def _followMove(doc, lFrom, lTo):
	"""Rename example settings keys for what was just moved: the property
	itself, or everything under a group or section.  Done at the moment of
	the move, so a later op that rewrites an example is left alone."""
	dIface = doc.get('interface') if isinstance(doc, dict) else None
	lEx = dIface.get('examples') if isinstance(dIface, dict) else None
	if not isinstance(lEx, list): return
	if (lFrom[:1] != ['interface']) or (lTo[:1] != ['interface']): return
	if (len(lFrom) < 2) or (len(lTo) < 2): return
	sOld = '/'.join(lFrom[1:])
	sNew = '/'.join(lTo[1:])
	for dEx in lEx:
		dSet = dEx.get('settings') if isinstance(dEx, dict) else None
		if not isinstance(dSet, dict): continue
		if not any((k == sOld) or k.startswith(sOld + '/') for k in dSet): continue
		lItems = []
		for (k, v) in dSet.items():
			if (k == sOld) or k.startswith(sOld + '/'):
				lItems.append((sNew + k[len(sOld):], v))
			elif (k == sNew) or k.startswith(sNew + '/'):
				pass   # set what the move overwrote, it is gone
			else:
				lItems.append((k, v))
		dSet.clear()
		dSet.update(lItems)

def applyOps(dNode, lOps):
	"""Apply override ops to a node, in place.

	:param dNode: The node as built by an importer.  On failure it is left
	   partly changed, so pass a copy if the original still matters.
	:param lOps: The ops list of an override, see the module description.
	:raises OverrideError: An op that does not apply, with its number and
	   the path that failed.
	"""
	if not isinstance(dNode, dict):
		raise OverrideError("The node is not an object")
	for (i, dOp) in enumerate(lOps):
		try:
			for d in _expand(dNode, dOp): _doOp(dNode, d)
		except OverrideError as e:
			raise OverrideError("op %d (%s): %s"%(i, dOp['op'], e))

##############################################################################

def main(lArgs):
	if (len(lArgs) != 3) or (lArgs[1] in ('-h', '--help')):
		sys.stderr.write(__doc__)
		return 3
	try:
		with open(lArgs[1], encoding='utf-8') as f: dNode = json.load(f)
		dOver = loadOverride(lArgs[2])
		applyOps(dNode, dOver['ops'])
	except (OSError, ValueError, OverrideError) as e:
		sys.stderr.write("ERROR: %s\n"%e)
		return 5
	sys.stdout.write(json.dumps(dNode, ensure_ascii=False, indent='\t') + '\n')
	return 0

if __name__ == "__main__":
	sys.exit(main(sys.argv))
