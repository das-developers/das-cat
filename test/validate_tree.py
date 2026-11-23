#!/usr/bin/env python3

"""Validate catalog nodes against the published schemas.

   validate_tree.py [-c] [-s SCHEMA_ROOT] TREE [TREE...]

Each .json file under a TREE (or a TREE that is one file) is a node.  A
node is checked against the schema for its own "type" and "version"
members, SCHEMA_ROOT/<type, lower case>/v<version>.json: a
"type":"HttpStreamSrc", "version":"0.7" node against
httpstreamsrc/v0.7.json.  Node types are versioned one by one, so the
files of one tree are usually checked against several schemas.

A node held in place inside another, a value under a "catalog" member
that is not a reference to somewhere else, is checked the same way, by
its own type and version.  The schema of the container only makes sure
it says what it is.

A node whose type has schemas but not for its version is reported and
counts as a failure.  With -c it is checked against the newest schema of
its type instead, and the count of such nodes is printed.  That is for
nodes stamped before their type had a schema, the root catalog nodes
for one.  A file whose type has no schema at all (not a node type this
repository describes) is a failure either way.

SCHEMA_ROOT defaults to schema/ in this repository; build it with 'make
schema' first.  Needs check-jsonschema, from the repository's venv
(test/validate.sh makes it) or the PATH.

The schemas only take http and https URLs, so a tree made with a file://
ROOT_URL for das_fetch tests will fail on every URL.  Validate a tree
made with the ROOT_URL it will be published at.

Exit 0 if everything validates, 7 if not, or if there was nothing to
validate.
"""

import sys
import os
import re
import json
import shutil
import tempfile
import subprocess

g_sRepo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

g_reVerFile = re.compile(r'^v(\d+(\.\d+)*)\.json$')

def _schemas(sRoot):
	"""{type directory name: {version: schema path}} for what is published"""
	dOut = {}
	if not os.path.isdir(sRoot): return dOut
	for sType in sorted(os.listdir(sRoot)):
		sDir = os.path.join(sRoot, sType)
		if not os.path.isdir(sDir): continue
		dVer = {}
		for sName in os.listdir(sDir):
			m = g_reVerFile.match(sName)
			if m: dVer[m.group(1)] = os.path.join(sDir, sName)
		if dVer: dOut[sType] = dVer
	return dOut

def _newest(dVer):
	return max(dVer, key=lambda s: [int(t) for t in s.split('.')])

def _nodes(dNode, sWhere, lOut):
	"""A node and the nodes it holds in place, as (where, node) pairs.
	An entry with urls or locations points elsewhere and is the business
	of its container's schema."""
	lOut.append((sWhere, dNode))
	dKids = dNode.get('catalog')
	if not isinstance(dKids, dict): return lOut
	for (sKey, dKid) in dKids.items():
		if not isinstance(dKid, dict): continue
		if ('urls' in dKid) or ('locations' in dKid): continue
		_nodes(dKid, '%s#/catalog/%s'%(sWhere, sKey), lOut)
	return lOut

def main(lArgs):
	sRoot = os.path.join(g_sRepo, 'schema')
	bCurrent = False
	lTrees = []
	i = 1
	while i < len(lArgs):
		if lArgs[i] in ('-h', '--help'):
			sys.stdout.write(__doc__)
			return 0
		if lArgs[i] == '-c':
			bCurrent = True
			i += 1
			continue
		if (lArgs[i] == '-s') and (i + 1 < len(lArgs)):
			sRoot = lArgs[i+1]
			i += 2
			continue
		lTrees.append(lArgs[i])
		i += 1
	if not lTrees:
		sys.stderr.write(__doc__)
		return 3

	dSchemas = _schemas(os.path.abspath(sRoot))
	if not dSchemas:
		sys.stdout.write("No schemas under %s, run 'make schema' first\n"%sRoot)
		return 7

	sCheck = os.path.join(g_sRepo, 'venv', 'bin', 'check-jsonschema')
	if not os.path.isfile(sCheck): sCheck = 'check-jsonschema'

	# (type, version) -> [(where, node)], and how many of each were checked
	# against a schema of another version
	dWork = {}
	dAssumed = {}
	nOdd = 0
	for sTree in lTrees:
		if not os.path.exists(sTree):
			sys.stdout.write("%s: no such file or directory\n"%sTree)
			nOdd += 1
			continue
		lPaths = [sTree] if os.path.isfile(sTree) else [
			os.path.join(sDir, s) for (sDir, lDirs, lNames) in os.walk(sTree)
			for s in lNames if s.endswith('.json')]
		for sPath in sorted(lPaths):
			try:
				with open(sPath, encoding='utf-8') as f: dTop = json.load(f)
				if not isinstance(dTop, dict): raise ValueError("not an object")
			except (OSError, ValueError) as e:
				sys.stdout.write("%s: not readable as a node, %s\n"%(sPath, e))
				nOdd += 1
				continue

			for (sWhere, dNode) in _nodes(dTop, sPath, []):
				sType = dNode.get('type')
				sVer = dNode.get('version')
				dVer = dSchemas.get(sType.lower()) if isinstance(sType, str) else None
				if dVer is None:
					sys.stdout.write("%s: no schema for type '%s'\n"%(sWhere, sType))
					nOdd += 1
					continue
				if sVer not in dVer:
					if not bCurrent:
						sys.stdout.write("%s: no schema for %s version '%s' (there is %s)\n"%(
							sWhere, sType, sVer, ', '.join(sorted(dVer))))
						nOdd += 1
						continue
					sVer = _newest(dVer)
					dAssumed[(sType, sVer)] = dAssumed.get((sType, sVer), 0) + 1
				dWork.setdefault((sType, sVer), []).append((sWhere, dNode))

	nBad = nOdd
	if not dWork:
		sys.stdout.write("No nodes found, nothing was validated\n")
		nBad += 1

	# check-jsonschema takes files, so every node is written out by itself,
	# also those that are files already: a node held in place has to be,
	# and one way of doing it is one way of reporting it
	sTmp = tempfile.mkdtemp(prefix='validate_tree_')
	try:
		for (sType, sVer) in sorted(dWork):
			lNodes = dWork[(sType, sVer)]
			sSchema = dSchemas[sType.lower()][sVer]
			nFail = 0
			# in batches, a whole site does not fit on one command line
			for n in range(0, len(lNodes), 200):
				dName = {}
				for (j, (sWhere, dNode)) in enumerate(lNodes[n:n+200]):
					sFile = os.path.join(sTmp, 'n%06d.json'%(n + j))
					with open(sFile, 'w', encoding='utf-8') as f: json.dump(dNode, f)
					dName[sFile] = sWhere
				res = subprocess.run(
					[sCheck, '--schemafile', sSchema] + sorted(dName),
					stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
				if res.returncode != 0:
					nFail += 1
					sOut = res.stdout
					for (sFile, sWhere) in dName.items(): sOut = sOut.replace(sFile, sWhere)
					sys.stdout.write(sOut)
				for sFile in dName: os.remove(sFile)
			sNote = ''
			if (sType, sVer) in dAssumed:
				sNote = '  (%d stamped with another version)'%dAssumed[(sType, sVer)]
			sys.stdout.write("%-14s %-5s %4d nodes  %s%s\n"%(
				sType, sVer, len(lNodes), 'FAILED' if nFail else 'ok', sNote))
			nBad += nFail
	finally:
		shutil.rmtree(sTmp, ignore_errors=True)
	return 7 if nBad else 0

if __name__ == "__main__":
	sys.exit(main(sys.argv))
