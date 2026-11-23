#!/usr/bin/env python3

"""The URL check: what every example in a catalog tree sends to its server.

A source node's examples are settings in interface terms.  das_fetch (from
das2C) turns each into the URL a client would request, without contacting
anything.  Those URLs are the part of a node that servers and their caches
see, so they are what must not change by accident when the importer, an
override or the node layout changes.

   url_check.py urls TREE
      Print one line per example of every HttpStreamSrc under TREE:
      node path, example number, URL.  A node with no examples gets one
      line saying so, so that it still counts in a compare.  An example
      that can't be turned into a URL prints ERROR and das_fetch's reason
      instead, and the exit value is 5.

   url_check.py compare TREE_A TREE_B [-o OVERRIDE_DIR]
      Compare the two tables.  Exit 0 if every example in both trees
      gives the same URL.  With -o, a dataset whose override file has a
      "urlChange" member is allowed to send something else, as long as
      the example still exists and makes a URL; the member's text, the
      reason, is printed.  Anything else that differs, a node or example
      missing from one tree included, is listed and the exit value is 5.

A TREE that is not a directory, has no source nodes, or has a file that
can't be read as JSON is an error too (exit 5): a check that looked at
nothing has not passed.

Options:
   -f PATH   The das_fetch program, default $DAS_FETCH, else 'das_fetch'
             from PATH.  It must be from das2C 3.0.6 or later to read
             list ("multi") properties.

Typical use: build a tree with the importer alone and one with -o, then
compare them; or build the boolean and --multi forms and compare those.
"""

import sys
import os
import json
import subprocess

from importlib.machinery import SourceFileLoader

class CheckError(Exception):
	"""The check could not look at what it was asked to"""
	pass

def _sources(sTree):
	"""(relative path, node) for each HttpStreamSrc file, sorted"""
	if not os.path.isdir(sTree):
		raise CheckError("%s is not a directory"%sTree)
	lOut = []
	for (sDir, lDirs, lNames) in os.walk(sTree):
		for sName in lNames:
			if not sName.endswith('.json'): continue
			sPath = os.path.join(sDir, sName)
			try:
				with open(sPath, encoding='utf-8') as f: dNode = json.load(f)
			except (OSError, ValueError) as e:
				raise CheckError("%s: %s"%(sPath, e))
			if isinstance(dNode, dict) and (dNode.get('type') == 'HttpStreamSrc'):
				lOut.append((os.path.relpath(sPath, sTree), dNode))
	if not lOut:
		raise CheckError("%s has no HttpStreamSrc nodes"%sTree)
	return sorted(lOut, key=lambda t: t[0])

g_sNoEx = '(no examples)'

def urlTable(sTree, sFetch):
	"""{(relative path, example number): URL or 'ERROR ...'}.  A node
	without examples has one entry, number -1, so that every node is in
	the table."""
	dOut = {}
	for (sRel, dNode) in _sources(sTree):
		lEx = dNode.get('interface', {}).get('examples', [])
		if not lEx: dOut[(sRel, -1)] = g_sNoEx
		for i in range(len(lEx)):
			try:
				res = subprocess.run(
					[sFetch, '--no-cache', '-l', 'error', 'url', os.path.join(sTree, sRel), str(i)],
					stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
				)
			except OSError as e:
				raise CheckError("Can't run %s: %s"%(sFetch, e))
			if (res.returncode == 0) and res.stdout.strip():
				dOut[(sRel, i)] = res.stdout.strip()
			else:
				sWhy = ' '.join(res.stderr.split()) or 'das_fetch exit %d'%res.returncode
				dOut[(sRel, i)] = 'ERROR %s'%sWhy
	return dOut

def _urlChanges(sOverDir):
	"""{lower case dataset path: reason} for overrides that say they
	change what is sent"""
	sHere = os.path.dirname(os.path.abspath(__file__))
	mod = SourceFileLoader('cat_override', os.path.join(
		sHere, '..', 'src', 'scripts', 'cat_override.py')).load_module()
	dOut = {}
	for (sDir, lDirs, lNames) in os.walk(sOverDir):
		for sName in lNames:
			if not sName.endswith('.json5'): continue
			sFile = os.path.join(sDir, sName)
			try:
				dOver = mod.loadOverride(sFile)
			except mod.OverrideError as e:
				sys.stderr.write("ERROR: %s\n"%e)
				continue
			if dOver['urlChange']:
				sDs = os.path.relpath(sFile, sOverDir)[:-len('.json5')]
				dOut[sDs.replace(os.sep, '/').lower()] = dOver['urlChange']
	return dOut

def _dataset(sRel):
	"""'uiowa/cassini/rpws/survey/das2.json' -> 'cassini/rpws/survey'"""
	l = sRel.replace(os.sep, '/').split('/')
	return '/'.join(l[1:-1])

def main(lArgs):
	sFetch = os.environ.get('DAS_FETCH', 'das_fetch')
	sOverDir = None
	lPos = []
	i = 1
	while i < len(lArgs):
		if lArgs[i] in ('-h', '--help'):
			sys.stdout.write(__doc__)
			return 0
		if (lArgs[i] in ('-f', '-o')) and (i + 1 < len(lArgs)):
			if lArgs[i] == '-f': sFetch = lArgs[i+1]
			else: sOverDir = lArgs[i+1]
			i += 2
			continue
		lPos.append(lArgs[i])
		i += 1

	try:
		return _run(lPos, sFetch, sOverDir)
	except CheckError as e:
		sys.stderr.write("ERROR: %s\n"%e)
		return 5

def _run(lPos, sFetch, sOverDir):
	if (len(lPos) == 2) and (lPos[0] == 'urls'):
		dTab = urlTable(lPos[1], sFetch)
		nBad = 0
		for (sRel, n) in sorted(dTab):
			if dTab[(sRel, n)].startswith('ERROR'): nBad += 1
			sys.stdout.write("%s\t%d\t%s\n"%(sRel, n, dTab[(sRel, n)]))
		nEx = len([t for t in dTab if t[1] >= 0])
		sys.stderr.write("%d examples, %d without a URL, %d nodes with no example\n"%(
			nEx, nBad, len(dTab) - nEx))
		return 5 if nBad else 0

	if (len(lPos) == 3) and (lPos[0] == 'compare'):
		dA = urlTable(lPos[1], sFetch)
		dB = urlTable(lPos[2], sFetch)
		dAllow = _urlChanges(sOverDir) if sOverDir else {}
		nBad = 0
		lSaid = []
		for tKey in sorted(set(dA) | set(dB)):
			(sA, sB) = (dA.get(tKey, '(no such example)'), dB.get(tKey, '(no such example)'))
			if (sA == sB) and not sA.startswith('ERROR'): continue
			sDs = _dataset(tKey[0])
			# an allowed change is still a URL on both sides, not an example
			# or a node that went missing
			if (sA != sB) and (sDs in dAllow) and sA.startswith('http') and sB.startswith('http'):
				if sDs not in lSaid:
					lSaid.append(sDs)
					sys.stdout.write("allowed: %s, %s\n"%(sDs, dAllow[sDs]))
				continue
			nBad += 1
			sys.stdout.write("%s example %d\n   %s\n   %s\n"%(tKey[0], tKey[1], sA, sB))
		nEx = len([t for t in (set(dA) | set(dB)) if t[1] >= 0])
		sys.stdout.write("%d examples compared, %d differ or fail\n"%(nEx, nBad))
		return 5 if nBad else 0

	sys.stderr.write(__doc__)
	return 3

if __name__ == "__main__":
	sys.exit(main(sys.argv))
