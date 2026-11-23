#!/usr/bin/env python3

"""The browse URL check: does the catalog browser ask servers for the same
thing das2C does.

src/browse/das2cat_cgi_browse.py turns the settings of a source page's form
into a request URL by itself, it is a single file with no das libraries
under it.  das2C is the program that defines what a node's settings send.
This runs both over every HttpStreamSrc node in a tree and compares, with
das_fetch (from das2C) standing for das2C.  Nothing is contacted.

   browse_url_check.py TREE [-n COUNT] [-s SEED]

For each source node under TREE:

   examples   Each example, as the link the page gives for it, must make
              the URL 'das_fetch url NODE N' prints.  An example neither
              program can make a URL of is a fault in the node, not a
              difference; those are counted and, with -v, listed.

   forms      The page is printed with each example filled in, the form on
              it is read back the way a browser would and submitted.  That
              must make the same URL again.  The plain page, nothing
              filled in, is submitted too.

   settings   COUNT (default 20) forms are filled in at random, good values
              and bad, and given to both programs.  They must make the
              same URL, or both refuse.

Anything that differs is listed and the exit value is 5.  A TREE that is not
a directory or has no source nodes is an error too (exit 5): a check that
looked at nothing has not passed.

Options:
   -f PATH   The das_fetch program, default $DAS_FETCH, else 'das_fetch'
             from PATH.  It must be from das2C 3.0.6 or later.
   -n COUNT  Random forms per node, 0 for none
   -s SEED   Seed for the random forms, default 1, so that a failure can be
             had again
   -v        List the examples that both programs refuse, with das_fetch's
             reason
"""

import sys
import os
import json
import random
import subprocess
import importlib.util

from html.parser import HTMLParser
from urllib.parse import urlsplit, parse_qsl

class CheckError(Exception):
	"""The check could not look at what it was asked to"""
	pass

def loadBrowser():
	sHere = os.path.dirname(os.path.abspath(__file__))
	sFile = os.path.join(sHere, '..', 'src', 'browse', 'das2cat_cgi_browse.py')
	spec = importlib.util.spec_from_file_location('das2cat_cgi_browse', sFile)
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)
	return mod

def _sources(sTree):
	"""Relative path of each HttpStreamSrc file, sorted"""
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
				lOut.append(os.path.relpath(sPath, sTree))
	if not lOut:
		raise CheckError("%s has no HttpStreamSrc nodes"%sTree)
	return sorted(lOut)

def fetchUrl(sFetch, sFile, lArgs):
	"""What das_fetch makes of a node and an example number or KEY=VALUE
	settings: the URL, or 'ERROR' and its reason"""
	try:
		res = subprocess.run(
			[sFetch, '--no-cache', '-l', 'error', 'url', sFile] + lArgs,
			stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
		)
	except OSError as e:
		raise CheckError("Can't run %s: %s"%(sFetch, e))
	if (res.returncode == 0) and res.stdout.strip():
		return res.stdout.strip()
	return 'ERROR %s'%(' '.join(res.stderr.split()) or 'das_fetch exit %d'%res.returncode)

def browseUrl(mod, src, lQuery):
	"""What the browser makes of a query string, and the requisition it
	read the query as"""
	lReq = mod.queryReq(src, lQuery)
	(lOk, lWhy, dX) = mod.checkReq(src, lReq)
	if lWhy: return ('ERROR %s'%'; '.join(lWhy), lReq)
	(sUrl, sWhy) = mod.reqUrl(src, lOk, dX, 0)
	if sUrl is None: return ('ERROR %s'%sWhy, lReq)
	return (sUrl, lReq)


class FormReader(HTMLParser):
	"""Collects what a browser would send for the download form of a source
	page, the one with a '_form' field, if the 'Show URL' button is used"""

	def __init__(self):
		HTMLParser.__init__(self)
		self.lForms = []
		self.lCur = None
		self.dSelect = None

	def handle_starttag(self, sTag, lAttrs):
		d = dict(lAttrs)
		if sTag == 'form':
			self.lCur = []
		elif self.lCur is None:
			return
		elif sTag == 'input':
			sType = d.get('type', 'text')
			if 'name' not in d: return
			if sType in ('text', 'hidden'):
				self.lCur.append((d['name'], d.get('value', '')))
			elif sType in ('checkbox', 'radio'):
				if 'checked' in d: self.lCur.append((d['name'], d.get('value', 'on')))
			elif (sType == 'submit') and (d['name'] == '_show'):
				self.lCur.append((d['name'], d.get('value', '')))
		elif sTag == 'select':
			self.dSelect = {'name': d.get('name'), 'opts': [], 'multi': 'multiple' in d}
		elif (sTag == 'option') and (self.dSelect is not None):
			self.dSelect['opts'].append((d.get('value', ''), 'selected' in d))

	def handle_endtag(self, sTag):
		if (sTag == 'select') and (self.dSelect is not None) and (self.lCur is not None):
			lOpts = self.dSelect['opts']
			lSel = [sVal for (sVal, bSel) in lOpts if bSel]
			# a drop down with nothing marked shows, and sends, its first
			if not lSel and lOpts and not self.dSelect['multi']: lSel = [lOpts[0][0]]
			for sVal in lSel: self.lCur.append((self.dSelect['name'], sVal))
			self.dSelect = None
		elif (sTag == 'form') and (self.lCur is not None):
			self.lForms.append(self.lCur)
			self.lCur = None

def formQuery(mod, dNode, lQuery):
	"""Print a source page for a query string, read its form back and
	return what submitting it would send"""
	del mod.g_lOut[:]
	mod.prnHttpSource(dNode, lQuery)
	sHtml = ''.join(mod.g_lOut)
	del mod.g_lOut[:]
	reader = FormReader()
	reader.feed(sHtml)
	lForms = [l for l in reader.lForms if ('_form', '1') in l]
	if len(lForms) != 1:
		raise CheckError("%s: the page has %d download forms"%(dNode['_url'], len(lForms)))

	# Example links have to come back to the same page
	return lForms[0]

def exampleLinks(mod, dNode):
	"""The query strings of the example links on a source page"""
	class Links(HTMLParser):
		def __init__(self):
			HTMLParser.__init__(self)
			self.lOut = []
			self.bIn = False
		def handle_starttag(self, sTag, lAttrs):
			if sTag == 'form': self.bIn = True
			if (sTag == 'a') and not self.bIn and ('?' in dict(lAttrs).get('href', '')):
				self.lOut.append(dict(lAttrs)['href'])
	del mod.g_lOut[:]
	mod.prnHttpSource(dNode, [])
	links = Links()
	links.feed(''.join(mod.g_lOut))
	del mod.g_lOut[:]
	return [parse_qsl(urlsplit(s).query, keep_blank_values=True) for s in links.lOut]


g_lNumbers = ['1', '7', '50', '2.5', '0.125', '1e3', '-3', '0', '1000000']
g_lJunk = ['abc', '1,2', 'x y', '%&=', '7 ', '1_0']

def randomQuery(mod, src, lBase, rand):
	"""A form as some browser might send it: the settings in lBase, then
	each control changed with some chance.  Mostly good values."""
	dBase = {}
	for (sKey, sVal) in lBase: dBase.setdefault(sKey, []).append(sVal)
	state = mod.FormState(src, mod.queryReq(src, lBase))

	lQuery = [('_form', '1')]
	for grp in src.groups:
		if (grp.xor is not None) and (grp.enable.set is not None):
			# one of the radio buttons of each set, said once
			lSet = [g for g in src.groups if g.xor == grp.xor]
			if lSet[0] is grp:
				lQuery.append(('_xor.%s'%grp.xor, rand.choice(lSet).enable.key))

		for p in grp.props:
			if (p.set is None) or (p.isEnable() and (grp.xor is not None)): continue
			bChange = (rand.random() < 0.35)

			if p.type == 'bool':
				bOn = state.isOn(p)
				if bChange: bOn = not bOn
				if bOn: lQuery.append((p.key, 'true'))

			elif (p.type == 'enum') and p.multi:
				lOn = [s for s in p.enum if s.lower() in state.items(p)]
				if bChange:
					lOn = [s for s in p.enum if rand.random() < 0.4]
				for s in lOn: lQuery.append((p.key, s))

			elif p.type == 'enum':
				sVal = state.text(p)
				if bChange: sVal = rand.choice(p.enum + [''])
				lQuery.append((p.key, sVal))

			elif p.type == 'time':
				# das2C reads times and the browser does not, so only good
				# ones go to both
				lQuery.append((p.key, state.text(p)))

			else:
				sVal = state.text(p)
				if bChange:
					nPick = rand.random()
					if nPick < 0.15: sVal = ''
					elif nPick < 0.30: sVal = rand.choice(g_lJunk)
					elif p.multi:
						sVal = ','.join(rand.sample(g_lNumbers, rand.randint(1, 4)))
					else:
						sVal = rand.choice(g_lNumbers)
				lQuery.append((p.key, sVal))
	return lQuery


def main(lArgs):
	sFetch = os.environ.get('DAS_FETCH', 'das_fetch')
	nRandom = 20
	nSeed = 1
	bVerbose = False
	lPos = []
	i = 1
	while i < len(lArgs):
		if lArgs[i] in ('-h', '--help'):
			sys.stdout.write(__doc__)
			return 0
		if lArgs[i] == '-v':
			bVerbose = True
			i += 1
			continue
		if (lArgs[i] in ('-f', '-n', '-s')) and (i + 1 < len(lArgs)):
			if lArgs[i] == '-f': sFetch = lArgs[i+1]
			elif lArgs[i] == '-n': nRandom = int(lArgs[i+1])
			else: nSeed = int(lArgs[i+1])
			i += 2
			continue
		lPos.append(lArgs[i])
		i += 1

	if len(lPos) != 1:
		sys.stderr.write(__doc__)
		return 3
	try:
		return _run(lPos[0], sFetch, nRandom, nSeed, bVerbose)
	except CheckError as e:
		sys.stderr.write("ERROR: %s\n"%e)
		return 5

def _same(sA, sB):
	"""The two programs agree: one URL, or both refuse.  Their reasons are
	worded for different readers and are not compared."""
	if sA.startswith('ERROR') and sB.startswith('ERROR'): return True
	return sA == sB

def _run(sTree, sFetch, nRandom, nSeed, bVerbose):
	mod = loadBrowser()

	# The page is printed as it would be on a server
	os.environ.update({
		'SERVER_NAME':'localhost', 'SCRIPT_NAME':'/browse', 'SERVER_PORT':'80'
	})

	rand = random.Random(nSeed)
	dCount = {'nodes':0, 'examples':0, 'forms':0, 'settings':0, 'refused':0, 'broken':0}
	lBad = []

	def differ(sRel, sWhat, sMine, sTheirs, lReq=None):
		lBad.append((sRel, sWhat))
		sys.stdout.write("%s, %s\n   browser:   %s\n   das_fetch: %s\n"%(sRel, sWhat, sMine, sTheirs))
		if lReq is not None:
			sys.stdout.write("   settings:  %s\n"%' '.join(['%s=%s'%t for t in lReq]))

	for sRel in _sources(sTree):
		sFile = os.path.join(sTree, sRel)
		with open(sFile, encoding='utf-8') as f:
			dNode = json.loads(f.read(), parse_int=mod.Num, parse_float=mod.Num)
		dNode['_url'] = 'http://localhost/%s'%sRel.replace(os.sep, '/')
		dNode['_path'] = 'tag:das2.org,2012:site:/%s'%sRel.replace(os.sep, '/')[:-len('.json')]
		src = mod.Source(dNode)
		dCount['nodes'] += 1

		# The plain page, submitted as it stands
		lQuery = formQuery(mod, dNode, [])
		(sMine, lReq) = browseUrl(mod, src, lQuery)
		sTheirs = fetchUrl(sFetch, sFile, ['%s=%s'%t for t in lReq])
		dCount['forms'] += 1
		if not _same(sMine, sTheirs): differ(sRel, 'plain form', sMine, sTheirs, lReq)

		lLinks = exampleLinks(mod, dNode)
		if len(lLinks) != len(src.examples):
			differ(sRel, 'example links', '%d links'%len(lLinks), '%d examples'%len(src.examples))
			continue

		for (i, lLink) in enumerate(lLinks):
			sTheirs = fetchUrl(sFetch, sFile, [str(i)])
			dCount['examples'] += 1
			if sTheirs.startswith('ERROR'):
				dCount['broken'] += 1
				if bVerbose: sys.stdout.write("%s, example %d makes no URL: %s\n"%(sRel, i, sTheirs))

			(sMine, lReq) = browseUrl(mod, src, lLink)
			if not _same(sMine, sTheirs): differ(sRel, 'example %d link'%i, sMine, sTheirs, lReq)

			# and after a trip through the form
			lQuery = formQuery(mod, dNode, lLink)
			(sMine, lReq) = browseUrl(mod, src, lQuery)
			dCount['forms'] += 1
			if not _same(sMine, sTheirs): differ(sRel, 'example %d form'%i, sMine, sTheirs, lReq)

		lBase = lLinks[0] if lLinks else []
		for i in range(nRandom):
			lQuery = randomQuery(mod, src, lBase, rand)
			(sMine, lReq) = browseUrl(mod, src, lQuery)
			sTheirs = fetchUrl(sFetch, sFile, ['%s=%s'%t for t in lReq])
			dCount['settings'] += 1
			if sTheirs.startswith('ERROR'): dCount['refused'] += 1
			if not _same(sMine, sTheirs): differ(sRel, 'settings %d'%i, sMine, sTheirs, lReq)

	sys.stdout.write(
		"%d nodes: %d examples (%d make no URL in either program), %d forms read back, "
		"%d random settings (%d refused by das_fetch), %d differ\n"%(dCount['nodes'],
		dCount['examples'], dCount['broken'], dCount['forms'], dCount['settings'],
		dCount['refused'], len(lBad))
	)
	return 5 if lBad else 0

if __name__ == "__main__":
	sys.exit(main(sys.argv))
