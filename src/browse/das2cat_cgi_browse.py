#!/usr/bin/python3

# Copyright 2018,2026 Chris Piker
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# (MIT License)

# Standalone CGI script federated catalog client.  Does not depend on other
# das libraries, or on anything outside the python standard library.
#
# Reads Catalog 0.5, SourceSet 0.2 and HttpStreamSrc 0.7 nodes.
#
# A source page needs no javascript.  Its form comes back to this script,
# which turns the settings into the request URL and redirects the browser
# to the data server.  The rules for that are in doc/httpstreamsrc.md.  The
# program that defines them is das2C (das3/source.c), and the section
# "Request building" below follows DasSrc_check() and DasSrc_reqUrl() there
# step by step, so that a fix in one can be carried to the other.
# test/browse_url_check.py compares the two over a tree of nodes.

import sys
import os
import re
import json
import html
import traceback
import urllib.request

from urllib.parse import parse_qsl, quote, urlencode

g_lOut = []

def pout(thing):
	g_lOut.append("%s\n"%thing)

def perr(thing):
	s = "%s\n"%thing
	sys.stderr.buffer.write(s.encode('utf-8'))

def esc(thing):
	"""Node text is not ours.  Everything from a node goes through here on
	its way into the page, attribute values included."""
	return html.escape("%s"%thing, quote=True)


# Toggle the hierarchy we wish to show with this copy of the browse tool
#g_sTree = 'test'
g_sTree = 'site'

#############################################################################
# Builtin defaults (update for your site)

# These name the root node file itself.  A directory URL only works on a
# server set up to hand out index.json for it.
g_lCatRoots = [
	"https://das2.org/catalog/index.json",
	"https://raw.githubusercontent.com/das-developers/das-cat/master/cat/index.json"
	#"http://das2.org/cat_test/index.json"
	# alternate root catalog mirror sites for reliablilty go here
]

g_sDefDas2SiteTag = 'tag:das2.org,2012:%s'%g_sTree

# prepend the same protocol (http or https) as the script was called under
g_sStyleSheet = "://das2.org/cat_resource/style.css"
g_sLogo       = "://das2.org/cat_resource/das2logo_rv.png"

# Seconds to wait on any one catalog file
g_nTimeout = 20


#############################################################################
def _missingKeyError(sKey, sUrl):
	pout(
'''<p class="error">Format error in node from <a href="%s">%s</a>,
key <b>%s</b> is missing.</p>
'''%(esc(sUrl), esc(sUrl), esc(sKey)))
	return None


#############################################################################
g_sScriptUrl = None

def scriptUrl():
	global g_sScriptUrl

	if g_sScriptUrl:
		return g_sScriptUrl

	sProto = 'http://'
	sPort = ''

	if os.getenv('HTTPS') != None:
		if os.getenv('HTTPS').lower() in ['1','on']:
			sProto = 'https://'

	if os.getenv('SERVER_PORT'):
		nPort = int(os.getenv('SERVER_PORT'))
	else:

		nPort = 80
		if sProto == 'https://':
			nPort = 443

	if (sProto == 'http://' and nPort != 80) or (sProto == 'https://' and nPort != 443):
		sPort = ':%d' % nPort

	g_sScriptUrl = "%s%s%s%s"%(sProto, os.getenv('SERVER_NAME'), sPort,
	                           os.getenv('SCRIPT_NAME'))
	return g_sScriptUrl


#############################################################################
def catPathToBrowseUrl(sPath):
	"""Given a catalog path ID return a URL within this browse tool that can
	be used ot view that ID"""

	if sPath == None:
		return scriptUrl()

	s = "%s:/"%g_sDefDas2SiteTag
	if sPath.startswith(s):
		return "%s/%s"%(scriptUrl(), sPath[len(s) : ])

	return '%s/%s'%(scriptUrl(), sPath)

def pathInfoToCatId(sPathInfo):
	""" Given a path info determine the catalog ID I'm looking for.  Note
	this function can't return None because no path info is taken to mean that
	the root of the das2 site:/ (or test:/) hierarchy is desired.
	"""
	if (sPathInfo == None) or (len(sPathInfo) == 0) or (sPathInfo == '/'):
		return g_sDefDas2SiteTag

	if sPathInfo[0] == '/':
		sPathInfo = sPathInfo[1:]

	if not sPathInfo.startswith("tag:"):
		return "%s:/%s"%(g_sDefDas2SiteTag, sPathInfo)
	else:
		return sPathInfo


#############################################################################
# Reading nodes

class Num(str):
	"""A JSON number, kept as the text the node has.  What a node says is
	sent to servers and compared with protocol lists as text, and 1.0 read
	as a float and written again is not always 1.0."""
	pass

def getJson(sUrl):
	"""Get one node.

	Returns:
		The node as a dictionary, or None if it could not be read for any
		reason.
	"""
	# urlopen() would read file: URLs too, and node URLs can come from
	# anywhere once a person may type one in the resolve box
	if not sUrl.lower().startswith(('http://', 'https://')):
		return None
	try:
		with urllib.request.urlopen(sUrl, timeout=g_nTimeout) as f:
			sText = f.read().decode('utf-8')
		dNode = json.loads(sText, parse_int=Num, parse_float=Num)
	except Exception as e:
		return None

	if not isinstance(dNode, dict) or not isinstance(dNode.get('type'), str):
		return None

	# Newer nodes have a label, older ones a name
	if ('name' not in dNode) and ('label' in dNode):
		dNode['name'] = dNode['label']
	return dNode

def _subKey(dNode):
	"""The member of a node that lists its children, None if it has none"""
	for sKey in ('catalog', 'sources'):   # 'sources' is the Collection of 2018
		if isinstance(dNode.get(sKey), dict): return sKey
	return None

def _separator(dNode):
	sSep = '/'
	if 'separator' in dNode:
		sSep = dNode['separator']
		if sSep == None:
			sSep = ""
	return sSep


#############################################################################
# Get Node definition and path information by Id

def _getNode(lAttempted, lPathTo, sUrl, sPath, sWanted):

	if sUrl not in lAttempted:
		lAttempted.append(sUrl)
	else:
		# We have a loop, break it here
		pout("Loop detected in catalog, at %s, needs to be fixed<br><br>"%esc(sUrl))
		return None

	dNode = getJson(sUrl)
	if dNode == None:
		return None

	# Slide in the catalog path and the source URL so it stays attached
	dNode['_url'] = sUrl
	dNode['_path'] = sPath

	if (sPath == sWanted) or (sPath[:-1] == sWanted) or (sPath == sWanted[:-1]):
		# This is the node you're looking for, note that the root catalog's
		# _path is None, so setting None for the sWanted will match the root
		return dNode

	# See if I match up to a '/'
	if not sWanted.startswith(sPath):
		# This isn't the node you looking for and I don't know how you got here
		return None

	# This is an ancester of the node you're looking for check the catalog
	sCatElement = _subKey(dNode)
	if sCatElement == None:
		return None   # Don't have a catalog

	dCat = dNode[sCatElement]
	sSep = _separator(dNode)

	# For each sub item append it's path to mine and see if the requested
	# path starts with total child string
	for sKey in dCat:
		sSubPath = "%s%s%s"%(sPath, sSep, sKey)

		if not sWanted.startswith(sSubPath):
			continue

		dCatEnt = dCat[sKey]        # This is the one, try all the urls
		if not isinstance(dCatEnt, dict) or ('urls' not in dCatEnt):
			continue

		for sUrl in dCatEnt['urls']:
			# Going for a sub node, add in my information so that they can get
			# back to me rapidly, but only if I'm part of the site hierarchy,
			# other hierarchies aren't the focus of this browse tool
			if sPath.startswith(g_sDefDas2SiteTag):
				lPathTo.append(
					(dNode.get('name', ''), dNode.get('title', ''), catPathToBrowseUrl(sPath) )
				)

				dSubNode = _getNode(lAttempted, lPathTo, sUrl, sSubPath, sWanted)
				if dSubNode != None:
					return dSubNode

				lPathTo.pop()

			else:
				dSubNode = _getNode(lAttempted, lPathTo, sUrl, sSubPath, sWanted)
				if dSubNode != None:
					return dSubNode

	return None

############################################################################
# We're stateless so we'll always have to navigate from the top down.  A real
# app would cache nodes along the way making subsequent lookups faster.
# das2C does this automatically

def getNode(sWanted):
	"""Get a catalog node item and return items along the path to it.

	The basic resolution is that:

	   1. Each node that is loaded is supplied with it's name by it's parent.

		2. To form child nodes the separator is combined with the calalog entry
		   and passed to the sub-node loader.


	arguments:
		sWanted - The virtual path that is desired, these look like
		          "tag:das2.org,2012:site:/uiowa" (or test:/) or a direct
		          URL to a JSON file, for ex: http://...
	returns:
		(dNode, lPathTo, lUrls )

		dNode - The final node, or None if it couldn't be reached

		lPathTo - A list of Names, Titles and Browse tool URLs for items
		          leading to this location, last item (dNode) is not included
					 Each element of the path to list is (Name, Title, Browse_URL)

		lUrls - A list of Catalog URLs used to arrive at this infomation, mostly
		        for diagnostic purposes
	"""
	lAttempted = []
	lPathTo = []

	sLow = sWanted.lower()
	if sLow.startswith('http'):
		lAttempted.append(sWanted)

		# just go get it, path information will be empty
		dNode = getJson(sWanted)
		if dNode == None:
			return (None, [], lAttempted)
		dNode['_url'] = sWanted
		dNode['_path'] = ""           # I did not walk a catalog to get here
		                              # path information not available
		return (dNode, lPathTo, lAttempted)

	else:
		sPath = ""
		for sUrl in g_lCatRoots:
			dNode = _getNode(lAttempted, lPathTo, sUrl, sPath, sWanted)
			if dNode != None:
				return (dNode, lPathTo, lAttempted)

	return (None, [], lAttempted)

############################################################################

def getDirectSubs(dNode, sListKey, tTypes=None):
	"""Get sub-nodes of a node.  Not used at part of normal getNode traversal.

	Args:
		dNode - The node for which sub-items are desired
		sListKey - The key to the json object that lists the sub-nodes
		tTypes - If given, only get sub-nodes the listing says are one of
		         these types.  Not everything listed is a node, a das2 DSDF
		         for one is not.
	returns:
		A dictionary of direct sub-nodes which may be empty if no sub-nodes are
		present
	"""
	dRet = {}
	if sListKey not in dNode: return dRet

	dSubs = dNode[sListKey]
	sSep = _separator(dNode)

	for sKey in dSubs:
		dCatEnt = dSubs[sKey]
		if not isinstance(dCatEnt, dict): continue
		if (tTypes is not None) and (dCatEnt.get('type') not in tTypes): continue

		for sUrl in dCatEnt.get('urls', []):
			dSubNode = getJson(sUrl)
			if dSubNode == None:
				continue   # Complain here?

			# Slide in the source URL and path we took so it stays attached.
			# A node read by its URL has no path, and neither do its children
			dSubNode['_url'] = sUrl
			dSubNode['_path'] = ""
			if dNode['_path']:
				dSubNode['_path'] = "%s%s%s"%(dNode['_path'], sSep, sKey)
			dRet[sKey] = dSubNode
			break

	return dRet


#############################################################################
def prnBrowseBar(lPathTo, dNode):
	"""lPathTo a list of (Name, Title, Browse_URL) triplets leading to dNode
	"""
	if len(lPathTo) == 0:
		return

	pout('  <ul id="catnav">')
	for i in range(0, len(lPathTo)):
		sName = lPathTo[i][0].rstrip('/')
		if i == 0:
			pout('  <li><a href="%s">%s</a></li>'%(esc(lPathTo[i][2]), esc(sName)))
		else:
			pout('  <li>&gt; <a href="%s">%s</a></li>'%(esc(lPathTo[i][2]), esc(sName)))

	if 'label' in dNode: sLabel = dNode['label']
	else: sLabel = dNode.get('name', '')

	pout('  <li> &gt; %s</li>'%esc(sLabel))
	pout('</ul>')

#############################################################################
def prnIdentifiers(dNode, bResolveLink=True):
	"""Where this page came from, at the bottom of each kind of page"""
	pout('<div class="identifers">')
	sPath = esc(dNode['_path'])
	if bResolveLink and dNode['_path']:
		sPath = '<a href="%s?%s">%s</a>'%(
			esc(scriptUrl()), esc(urlencode([('resolve', dNode['_path'])])), sPath
		)
	pout('<br><br>Catalog Path: %s &nbsp; <br>Read From: <a href="%s">%s</a>'%(
	     sPath, esc(dNode['_url']), esc(dNode['_url'])))
	pout('</div>')

#############################################################################
def prnCatalog(dNode):

	dSub = dNode['catalog']
	sSep = _separator(dNode)

	if 'title' in dNode:
		pout("<h3>%s</h3>"%esc(dNode['title']))

	if 'description' in dNode:
		pout("<p>%s<br><br></p>"%esc(dNode['description']))

	lKeys = list(dSub.keys())
	lKeys.sort()
	pout('<ul>')
	for sKey in lKeys:
		dEnt = dSub[sKey]
		if not isinstance(dEnt, dict): continue
		sSubUrl = catPathToBrowseUrl(dNode['_path'] + sSep + sKey)
		if 'label' in dEnt:
			sName = esc(dEnt['label'])
		elif 'name' in dEnt:
			sName = esc(dEnt['name'])
		else:
			sName = esc(sKey)
		if len(sName) < 2:
			sName = " &nbsp; %s &nbsp;"%sName

		sType = dEnt.get('type', 'node')
		if 'title' in dEnt:
			sTitle = dEnt['title']
		elif 'description' in dEnt:
			sTitle = dEnt['description']
		else:
			sTitle = "An untitled %s"%sType

		sClass = "cat_cat"
		if sType in ('Collection', 'HttpStreamSrc', 'SourceSet'):
			sClass = "type_stream"
		elif sType == 'Das2DSDF':
			sClass = "type_legacy"

		pout('<li class="%s"><a href="%s">%s</a> - %s<br></li>'%(
			sClass, esc(sSubUrl), sName, esc(sTitle)))

	pout('</ul>')

	prnIdentifiers(dNode)

	pout('<hr class="code_sep">')

	sURI = dNode['_path']
	sURI = sURI.replace('tag:das2.org,2012:','')

	if len(lKeys) > 0:
		sSubNode = "subnode = node['%s']"%lKeys[0]
	else:
		sSubNode = "# Catalog has no sub nodes"

	pout('<button class="accordian">Using this node with Python 3</button>')
	pout('<div class="code">')
	pout('''
<blockquote class="code"><pre><code>
   import json
   import das2

   node = das2.get_node("%s")

   # Pretty print node content
   s = json.dumps(node.props, ensure_ascii=False, indent="  ", sort_keys=True)
   print(s)

   # List and access sub-nodes
   node.keys()
   %s

</code></pre></blockquote>
'''%(esc(sURI), esc(sSubNode)))
	pout('</div>')

	pout('<button class="accordian">Using this node with C99</button>')
	pout('<div class="code">')
	pout('''
<blockquote class="code"><pre><code>
   #include &lt;stdio.h&gt;
   #include &lt;das2/core.h&gt;

   DasNode* pRoot = new_RootNode(NULL, NULL, NULL);
   DasNode* pNode = DasNode_subNode(pRoot, "%s", NULL, NULL);
   DasJdo*  pJdo  = DasNode_getJdo(pNode, NULL);
   size_t uLen;
   const char* sOut = DasJdo_writePretty(pJdo, "   ", "\\n", &uLen);
   fputs(sOut, stdout);

</code></pre></blockquote>
'''%esc(dNode['_path']))
	pout('</div>')


#############################################################################
# Request building: a source node and a set of settings to a URL
#
# Names here follow das3/source.c in das2C.  A requisition is a list of
# (property key, value text) pairs in the order they were said, keys being
# 'coords.time.min', 'data.ex.enabled', 'formats.das2.text', 'options.gain'.

def _scalar(v):
	"""A JSON string, number or boolean as text, None for anything else"""
	if v is True: return 'true'
	if v is False: return 'false'
	if isinstance(v, str): return str(v)
	return None

def _strieq(a, b):
	return a.lower() == b.lower()

def _split(sVal):
	"""The items of a list value.  Items are trimmed of blanks and may come
	out empty, blanks alone are no items."""
	if sVal.strip(' ') == '': return []
	return [s.strip(' ') for s in sVal.split(',')]

def _noValue(sVal, bList):
	"""True for a value that says nothing"""
	if bList: sVal = sVal.lstrip(' ')
	return sVal == ''

def _sameItems(sA, sB):
	(lA, lB) = (_split(sA), _split(sB))
	if len(lA) != len(lB): return False
	lB = [s.lower() for s in lB]
	return all(s.lower() in lB for s in lA)

def _parseBool(s):
	"""True, False, or None if s is not a word for either"""
	if s is None: return None
	if s.lower() in ('true', 'yes', 'on', '1', 't', 'y'): return True
	if s.lower() in ('false', 'no', 'off', '0', 'f', 'n'): return False
	return None

g_dTypeNames = {
	'boolean':'bool', 'bool':'bool', 'integer':'int', 'int':'int',
	'real':'real', 'double':'real', 'float':'real',
	'isotime':'time', 'time':'time', 'datetime':'time',
	'enum':'enum', 'string':'text', 'text':'text'
}

def _typeByName(s):
	if not isinstance(s, str): return None
	return g_dTypeNames.get(s.lower())

def _str(d, sKey):
	"""A string member of a dictionary, else None"""
	v = d.get(sKey)
	return str(v) if (isinstance(v, str) and not isinstance(v, Num)) else None


class SrcProp(object):
	"""One member of a group's 'props'.  A property with a set block that
	names a protocol parameter is a control, 'set' is then not None."""

	def __init__(self, grp, sName, d, dParams):
		self.grp = grp
		self.name = sName
		self.d = d
		if grp.name: self.key = '%s.%s.%s'%(grp.sec, grp.name, sName)
		else: self.key = '%s.%s'%(grp.sec, sName)

		# "multi": true, or [fewest, most] items.  hi None is no limit.
		(self.multi, self.lo, self.hi) = (False, 1, 1)
		m = d.get('multi')
		if (m is True) or isinstance(m, list):
			(self.multi, self.lo, self.hi) = (True, 0, None)
			try:
				(nLo, nHi) = (int(m[0]), int(m[1]))
				if (len(m) == 2) and (0 <= nLo <= nHi) and (nHi > 0):
					(self.lo, self.hi) = (nLo, nHi)
			except (TypeError, ValueError, IndexError):
				pass

		# The default.  A list is kept as its items joined with commas, and
		# an empty one is no default
		v = d.get('value')
		if self.multi:
			l = [_scalar(x) for x in (v if isinstance(v, list) else [v])]
			l = [s for s in l if s is not None]
			self.value = ','.join(l) if l else None
		else:
			self.value = _scalar(v)

		self.set = None
		self.param = None
		self.dParam = {}
		self.required = False
		self.enum = []    # item values
		self.items = []   # item dictionaries, in step with enum
		dSet = d.get('set')
		if isinstance(dSet, dict) and (_str(dSet, 'param') is not None):
			self.set = dSet
			self.param = dSet['param']
			if isinstance(dParams.get(self.param), dict):
				self.dParam = dParams[self.param]
			self.required = (dSet.get('required') is True) or (self.dParam.get('required') is True)
			if isinstance(dSet.get('enum'), list):
				for item in dSet['enum']:
					s = _scalar(item.get('value') if isinstance(item, dict) else item)
					if s is None: continue
					self.enum.append(s)
					self.items.append(item if isinstance(item, dict) else {})

		self.type = self._resolveType()
		if self.multi and (self.type == 'bool'):
			(self.multi, self.lo, self.hi) = (False, 1, 1)   # on or off has nothing to list
			self.value = _scalar(v)

	def _resolveType(self):
		"""Preference order: a set enum list, the property's type, a boolean
		default, a flag toggle, the protocol parameter's type, the shape of
		the value, then text."""
		if self.enum: return 'enum'
		sType = _typeByName(self.d.get('type'))
		if (sType is not None) and (sType != 'enum'): return sType
		if isinstance(self.d.get('value'), bool): return 'bool'
		if self.set and not self.multi and (_str(self.set, 'flag') is not None): return 'bool'
		sType = _typeByName(self.dParam.get('type'))
		if (sType is not None) and (sType != 'enum'): return sType
		if isinstance(self.d.get('value'), Num): return 'real'
		return 'text'

	def isEnable(self):
		return self is self.grp.enable


class SrcGroup(object):
	"""A coordinate, a data variable, a format, or the options"""

	def __init__(self, sSec, sName, d, dParams):
		self.sec = sSec
		self.name = sName
		self.d = d
		self.key = '%s.%s'%(sSec, sName) if sName else sSec
		self.props = []
		self.enable = None   # the 'enabled' toggle
		self.xor = None      # the exclusive set this group is a member of
		dProps = d.get('props')
		if not isinstance(dProps, dict): return
		for (sProp, dProp) in dProps.items():
			if not isinstance(dProp, dict): continue
			if not (('value' in dProp) or ('set' in dProp) or ('type' in dProp)): continue
			p = SrcProp(self, sProp, dProp, dParams)
			self.props.append(p)
			if (sProp.lower() in ('enabled', 'enable')) and (self.enable is None):
				self.enable = p
				self.xor = _str(dProp, 'xorGroup')

	def label(self):
		return self.d.get('label') or self.name or self.sec


class Source(object):
	"""The parts of an HttpStreamSrc 0.7 node used to make requests"""

	def __init__(self, dNode):
		dProto = dNode.get('protocol')
		if not isinstance(dProto, dict): dProto = {}
		self.baseUrls = [s for s in dProto.get('baseUrls', []) if isinstance(s, str)]
		self.params = dProto.get('httpParams')
		if not isinstance(self.params, dict): self.params = {}

		dIface = dNode.get('interface')
		if not isinstance(dIface, dict): dIface = {}
		self.iface = dIface

		# Groups in presentation order: time first for coordinates, otherwise
		# as the node lists them.  Options are one group with no name.
		self.groups = []
		for sSec in ('coords', 'data', 'formats'):
			dSec = dIface.get(sSec)
			if not isinstance(dSec, dict): continue
			lNames = list(dSec.keys())
			if sSec == 'coords':
				lNames = [s for s in lNames if s.lower() == 'time'] + \
				         [s for s in lNames if s.lower() != 'time']
			for sName in lNames:
				if isinstance(dSec[sName], dict):
					self.groups.append(SrcGroup(sSec, sName, dSec[sName], self.params))
		if isinstance(dIface.get('options'), dict):
			self.groups.append(SrcGroup('options', '', dIface['options'], self.params))

		self.props = [p for g in self.groups for p in g.props]
		self.byKey = dict([(p.key, p) for p in self.props])

		self.examples = dIface.get('examples')
		if not isinstance(self.examples, list): self.examples = []

	def section(self, sSec):
		return [g for g in self.groups if g.sec == sSec]


def exampleReq(dExample):
	"""An example's settings as a requisition.  Setting paths look like
	'coords/time/props/min', keys like 'coords.time.min'."""
	lReq = []
	dSettings = dExample.get('settings') if isinstance(dExample, dict) else None
	if not isinstance(dSettings, dict): return lReq
	for (sPath, v) in dSettings.items():
		sKey = '.'.join([s for s in sPath.split('/') if s != 'props'])
		if isinstance(v, list):
			l = [_scalar(x) for x in v]
			l = [s for s in l if s is not None]
			if not l: continue
			lReq.append((sKey, ','.join(l)))
		elif _scalar(v) is not None:
			lReq.append((sKey, _scalar(v)))
	return lReq


# Exclusive sets.  Groups whose enable toggles carry the same "xorGroup"
# name are radio buttons.  A node writes each member as an ordinary boolean
# that knows nothing of the others, so what a requisition says of them is
# settled here once:
#
#   - The last member a requisition switches on is on, the others are off,
#     whatever they default to and whatever was said of them before.
#   - If it switches none on, the node's defaults stand, less any member it
#     switches off.

class _Xor(object):
	def __init__(self):
		self.state = None   # None: not in a set, else True for on
		self.said = None    # the requisition's last word on the toggle
		self.defOn = False  # on in the node
		self.at = 0         # the entry that said it

def _xorStates(src, lMatch):
	"""lMatch is a requisition with properties in place of keys, None for a
	key that names no property.  Returns {group: _Xor}."""
	dX = {}
	for g in src.groups:
		x = _Xor()
		if g.xor is not None:
			x.defOn = (_parseBool(g.enable.value) is True)
			x.state = x.defOn
		dX[g] = x

	for (i, (p, sVal)) in enumerate(lMatch):
		if (p is None) or (dX[p.grp].state is None) or not p.isEnable(): continue
		x = dX[p.grp]
		if sVal == '': x.said = None                # took it back
		elif _parseBool(sVal) is None: continue     # the check refuses it
		else: x.said = _parseBool(sVal)
		x.at = i

	for g in src.groups:
		x = dX[g]
		if x.state is None: continue
		bWinner = False
		bMe = (x.said is True)
		for h in src.groups:
			y = dX[h]
			if (h is g) or (y.said is not True) or (h.xor != g.xor): continue
			bWinner = True
			if y.at > x.at: bMe = False
		if bMe: x.state = True
		elif bWinner or (x.said is False): x.state = False
	return dX

def _xorIdle(dX, p):
	"""A property that has no say in this request: any but the toggle of a
	member that is off"""
	return (dX[p.grp].state is False) and not p.isEnable()

def _propSays(p):
	"""What to call a property when talking to a person"""
	sGrp = p.grp.d.get('label') or p.grp.name
	sProp = p.d.get('label') or p.name
	if p.isEnable(): return "'%s'"%(sGrp or sProp)
	if p.grp.sec == 'options': return "'%s'"%sProp
	return "'%s %s'"%(sGrp, sProp)

# Numbers as C reads them.  int() and float() take more: 1_000, ' 7 '.
g_reInt = re.compile(r'^\s*[+-]?[0-9]+$')
g_reReal = re.compile(r'^\s*[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?$')

def _checkOne(p, sVal):
	"""Why one value, or one item of a list, can't be used, else None"""
	if p.type == 'bool':
		if _parseBool(sVal) is None:
			return "'%s' is not a boolean value for %s, use true or false"%(sVal, _propSays(p))
	elif p.type == 'enum':
		if not any(_strieq(s, sVal) for s in p.enum):
			return "'%s' is not an allowed value for %s, choose one of: %s"%(
				sVal, _propSays(p), ', '.join(p.enum))
	elif p.type == 'int':
		if not g_reInt.match(sVal):
			return "'%s' is not an integer value for %s"%(sVal, _propSays(p))
	elif p.type == 'real':
		if not g_reReal.match(sVal):
			return "'%s' is not a real value for %s"%(sVal, _propSays(p))
	# Times are left to the server.  das2C parses them, and takes many more
	# forms than are worth repeating in a stand-in.
	return None

def _checkValue(p, sVal):
	if not p.multi: return _checkOne(p, sVal)

	lItems = _split(sVal)
	for (i, sItem) in enumerate(lItems):
		if sItem == '':
			return "'%s' has an empty item, %s takes values separated by single commas"%(
				sVal, _propSays(p))
		sWhy = _checkOne(p, sItem)
		if sWhy: return sWhy
		# Enum items are matched without regard to case, free text goes to
		# the server as typed
		for sPrev in lItems[:i]:
			if (_strieq(sItem, sPrev) if p.enum else (sItem == sPrev)):
				return "'%s' is given twice for %s"%(sItem, _propSays(p))

	# No items is nothing selected, which is not a count to bound
	n = len(lItems)
	if (n > 0) and ((n < p.lo) or ((p.hi is not None) and (n > p.hi))):
		if p.hi is None:
			return "%s takes at least %d values, %d given"%(_propSays(p), p.lo, n)
		if p.lo == p.hi:
			return "%s takes %d values, %d given"%(_propSays(p), p.lo, n)
		return "%s takes %d to %d values, %d given"%(_propSays(p), p.lo or 1, p.hi, n)
	return None

def checkReq(src, lReq):
	"""Hold a requisition to the node, as DasSrc_check() does.

	Returns:
		(lOk, lWhy, dX): the entries that stand as (property, value) pairs,
		the reasons the others do not, and the exclusive set states.
	"""
	lMatch = [(src.byKey.get(sKey), sVal) for (sKey, sVal) in lReq]
	dX = _xorStates(src, lMatch)
	lOk = []
	lWhy = []
	lPresent = []

	for (u, (p, sVal)) in enumerate(lMatch):
		if p is None:
			lWhy.append("No property named '%s' in this source"%lReq[u][0])
			continue
		if p.set is None:
			lWhy.append("%s is a fixed property of this source and cannot be set"%_propSays(p))
			continue
		lPresent.append(p)

		# A setting of a format that is not the one chosen, or of any member
		# of an exclusive set that is off.  Sending it would be a request no
		# form could have made; dropping it would hide that the user and the
		# request disagree.
		if _xorIdle(dX, p):
			if _noValue(sVal, p.multi):
				lOk.append((p, sVal))
			else:
				lWhy.append("%s is a setting of '%s', which is not selected"%(
					_propSays(p), p.grp.label()))
			continue

		# Radio buttons have no "none"
		x = dX[p.grp]
		if (x.said is False) and (x.at == u) and x.defOn and p.isEnable() and \
		   not any((dX[h].state is True) and (h.xor == p.grp.xor) for h in src.groups):
			lWhy.append("%s cannot be switched off by itself, one of the '%s' "
			            "choices is always on"%(_propSays(p), p.grp.xor))
			continue

		if _noValue(sVal, p.multi):
			if p.required and (p.value is None):
				lWhy.append("%s is required, give it a value"%_propSays(p))
			else:
				lOk.append((p, sVal))
			continue

		sWhy = _checkValue(p, sVal)
		if sWhy:
			lWhy.append(sWhy)
			continue
		lOk.append((p, sVal))

	# required controls nobody mentioned
	for p in src.props:
		if (p.set is None) or not p.required or (p.value is not None) or (p in lPresent):
			continue
		if _xorIdle(dX, p): continue   # asked for when chosen
		lWhy.append("%s is required, give it a value"%_propSays(p))

	return (lOk, lWhy, dX)


# The output parameter list.  A flag set parameter collects one piece per
# flag sent and is joined with its flagSep when the URL is built, not as
# controls are visited, because a flag with a subSep gathers elements from
# controls anywhere in the node into one piece.
#
# Pieces are kept in the order the parameter's "flags" object lists the
# flags, not the order controls are visited in, so that what is sent is a
# matter of the protocol section alone.
#
# A parameter that is not a flag set takes several values the same way:
# with its own subSep it is a single merged piece, with "repeat" every
# value is a piece and each goes out as its own NAME=VALUE pair.

class _Piece(object):
	def __init__(self, dMerge, nRank, sVal, sSuffix):
		self.merge = dMerge    # the flag's entry or the parameter's, None when not merged
		self.rank = nRank      # the flag's place among the parameter's flags
		self.val = sVal        # prefix then element(s)
		self.suffix = sSuffix  # what closes the piece once every element is in

class _Param(object):
	def __init__(self, sName):
		self.name = sName
		self.val = None        # plain value, None when only pieces
		self.flagSep = None
		self.repeat = False    # pieces are separate pairs, not one joined value
		self.pieces = []

	def join(self):
		sSep = ' ' if self.flagSep is None else self.flagSep
		s = self.val or ''
		for piece in self.pieces:
			if len(s) > 0: s += sSep
			s += piece.val + (piece.suffix or '')
		return s

class _Out(object):
	def __init__(self):
		self.params = []

	def find(self, sName):
		for prm in self.params:
			if prm.name == sName: return prm
		return None

	def get(self, sName):
		prm = self.find(sName)
		if prm is None:
			prm = _Param(sName)
			self.params.append(prm)
		return prm

	def set(self, sName, sVal):
		prm = self.get(sName)
		prm.val = sVal
		prm.pieces = []
		prm.repeat = False

	def addFlag(self, sName, sFlagSep, dFlag, nRank, sPrefix, sSuffix, sSubSep, sElem):
		"""Send a flag.  With sSubSep, a second element for the same flag
		joins the first piece instead of starting another."""
		prm = self.get(sName)
		if sFlagSep is not None: prm.flagSep = sFlagSep

		if sSubSep is not None:
			for piece in prm.pieces:
				if piece.merge is dFlag:
					piece.val = "%s%s%s"%(piece.val, sSubSep, sElem)
					return

		# after every piece of the same or an earlier flag
		nAt = len(prm.pieces)
		while (nAt > 0) and (prm.pieces[nAt - 1].rank > nRank): nAt -= 1
		prm.pieces.insert(nAt, _Piece(
			dFlag if (sSubSep is not None) else None, nRank, (sPrefix or '') + sElem, sSuffix
		))

def _inProtoEnum(dTarget, sVal):
	"""The protocol's own list of what may follow a flag's prefix, or be the
	value of a parameter.  Compared as text and exactly, the server will.
	An entry with no list takes anything."""
	lVals = dTarget.get('enum')
	if not isinstance(lVals, list): return True
	return any(_scalar(v) == sVal for v in lVals)

def _notInProtoEnum(p, sVal, sFlag):
	if sFlag:
		s = "%s would send '%s', which flag '%s' under protocol parameter %s does not " \
		    "list in its enum"%(_propSays(p), sVal, sFlag, p.param)
	else:
		s = "%s would send '%s', which protocol parameter %s does not list in its " \
		    "enum"%(_propSays(p), sVal, p.param)
	if p.enum: s += ", the node is broken"
	return s

def _flagEntry(p, sFlag):
	dFlags = p.dParam.get('flags')
	if not isinstance(dFlags, dict) or not isinstance(dFlags.get(sFlag), dict): return None
	return dFlags[sFlag]

def _joinTarget(p):
	"""What a control's value is joined into, if anything: the entry of a
	flag with a subSep, or of a parameter of its own with one.

	A joined value is one value as far as the server can tell, '-hfr ABEx'
	or 'read.data=a,b', so its parts are sent together or not at all."""
	dT = p.dParam
	sFlag = _str(p.set, 'flag')
	if sFlag is not None:
		dT = _flagEntry(p, sFlag)
		if dT is None: return None
	if (_str(dT, 'subSep') is None) or (dT.get('repeat') is True): return None
	return dT

def _translateOne(p, sVal, out):
	"""One control's value to protocol parameters, by its set block.
	Returns None, or why it could not be done."""
	dSet = p.set
	sFlag = _str(dSet, 'flag') or ''
	sPVal = _scalar(dSet.get('pval'))
	bSlot = (sFlag != '') and (p.type != 'bool')

	if isinstance(dSet.get('enum'), list):
		for item in dSet['enum']:
			dItem = item if isinstance(item, dict) else {}
			sItem = _scalar(dItem.get('value') if isinstance(item, dict) else item)
			if (sItem is None) or not _strieq(sItem, sVal): continue
			if _scalar(dItem.get('pval')) is not None: sPVal = _scalar(dItem['pval'])
			elif sPVal is None: sPVal = sItem
			if _str(dItem, 'flag') is not None:
				sFlag = dItem['flag']
				bSlot = False     # the item picked a flag, it's a switch
			break

	elif p.type == 'bool':
		bUser = (_parseBool(sVal) is True)
		trig = dSet.get('value')
		if isinstance(trig, bool) and (bUser != trig): return None
		if (sPVal is None) and (sFlag == ''):
			sPVal = 'true' if bUser else 'false'
		# A fixed string or a flag is sent for one state, and a block that
		# does not say which means on.  Off would otherwise send the very
		# string that means on.
		elif not isinstance(trig, bool) and not bUser: return None

	if sFlag != '':
		dF = _flagEntry(p, sFlag)
		if dF is None:
			return "Flag '%s' for %s is not defined under protocol parameter %s, " \
			       "the node is broken"%(sFlag, _propSays(p), p.param)
		sSubSep = _str(dF, 'subSep')
		bRepeat = (dF.get('repeat') is True)
		if p.multi and bSlot and ((sSubSep is None) == (not bRepeat)):
			# Joined or repeated is a different request to the server, so the
			# node has to say which
			return "%s holds a list, so flag '%s' under protocol parameter %s must have " \
			       "exactly one of subSep and repeat, the node is broken"%(
			       _propSays(p), sFlag, p.param)
		if bRepeat: sSubSep = None

		if bSlot:
			sFVal = sPVal if (sPVal is not None) else sVal
		elif sSubSep is not None:
			# Every switch on the flag would send the same flag value, so the
			# element has to come from the switch
			if sPVal is None:
				return "Flag '%s' under protocol parameter %s joins elements, but %s gives " \
				       "no pval for its element, the node is broken"%(sFlag, p.param, _propSays(p))
			sFVal = sPVal
		else:
			sFVal = _scalar(dF.get('value'))
			if sFVal is None: sFVal = sFlag

		# A plain switch sends the flag's own text, there is nothing to look
		# up; anything that follows a prefix is held to the list
		if (bSlot or (sSubSep is not None)) and not _inProtoEnum(dF, sFVal):
			return _notInProtoEnum(p, sFVal, sFlag)

		sSep = _str(p.dParam, 'flagSep')
		if sSep is None: sSep = ' '
		nRank = list(p.dParam['flags'].keys()).index(sFlag)
		out.addFlag(p.param, sSep, dF, nRank, _str(dF, 'prefix'), _str(dF, 'suffix'), sSubSep, sFVal)
		return None

	# A parameter of its own.  One that says how several values travel
	# collects them, from a list or from any number of controls; without
	# that the last value set is the value.
	sSubSep = _str(p.dParam, 'subSep')
	bRepeat = (p.dParam.get('repeat') is True)
	if p.multi and ((sSubSep is None) == (not bRepeat)):
		return "%s holds a list, so protocol parameter %s must have exactly one of " \
		       "subSep and repeat, the node is broken"%(_propSays(p), p.param)
	sSend = sPVal if (sPVal is not None) else sVal
	if not _inProtoEnum(p.dParam, sSend):
		return _notInProtoEnum(p, sSend, None)

	if bRepeat:
		out.addFlag(p.param, None, None, 0, None, None, None, sSend)
		out.find(p.param).repeat = True
	elif sSubSep is not None:
		out.addFlag(p.param, None, p.dParam, 0, None, None, sSubSep, sSend)
	else:
		out.set(p.param, sSend)
	return None

def _translate(p, sVal, out):
	"""A control's value to protocol parameters.  A list goes one item at a
	time: enumerated items in the node's order, so a selection is sent one
	way however it was picked, others as given."""
	if not p.multi: return _translateOne(p, sVal, out)

	lItems = _split(sVal)
	if p.enum:
		for sEnum in p.enum:
			if not any(_strieq(s, sEnum) for s in lItems): continue
			sWhy = _translateOne(p, sEnum, out)
			if sWhy: return sWhy
	else:
		for sItem in lItems:
			if sItem == '': continue
			sWhy = _translateOne(p, sItem, out)
			if sWhy: return sWhy
	return None

def _valueFor(lOk, dX, p):
	"""The value a requisition gives a property: the last entry for it.  An
	empty one takes back what came before.  None when the requisition
	leaves the property alone.  The toggles of an exclusive set give what
	was settled for the set and not what was said of each."""
	sVal = None
	for (q, s) in lOk:
		if q is p: sVal = None if _noValue(s, p.multi) else s

	bState = dX[p.grp].state
	if (bState is None) or not p.isEnable(): return sVal
	b = _parseBool(sVal if (sVal is not None) else p.value)
	if (b is not None) and (b == bState): return sVal
	return 'true' if bState else 'false'

def _sameAsDefault(p, sVal):
	if p.value is None: return False
	if p.multi: return _sameItems(sVal, p.value)
	if p.type == 'bool':
		(bA, bB) = (_parseBool(sVal), _parseBool(p.value))
		return (bA is not None) and (bB is not None) and (bA == bB)
	return _strieq(sVal, p.value)

def _urlEncode(sVal):
	# das2C leaves these plain so that times stay readable
	return quote(sVal, safe="-._~:/@,=")

def reqUrl(src, lOk, dX, nBase=0):
	"""Entries that passed checkReq() to a URL, as DasSrc_reqUrl() does.

	Returns:
		(sUrl, None) or (None, sWhy)
	"""
	if nBase >= len(src.baseUrls):
		return (None, "This source has %d base URL(s), there is no number %d"%(
			len(src.baseUrls), nBase))

	# Two members of an exclusive set on, which only the node can do
	for (i, g) in enumerate(src.groups):
		if dX[g].state is not True: continue
		for h in src.groups[i+1:]:
			if (dX[h].state is True) and (h.xor == g.xor):
				return (None, "This source has both '%s' and '%s' of the exclusive set '%s' "
				        "on by default, the node is broken"%(g.label(), h.label(), g.xor))

	# Joined values first: which of them does this request send at all?  One
	# is sent when any control feeding it is off its default or is required.
	# Then every control feeding it sends, defaults included.  '-hfr Ew'
	# does not mean "sensor Ew, bands as usual" to a server, it means no
	# bands, so the default bands have to travel with it.
	lLive = []
	lCtrls = [p for p in src.props if (p.set is not None) and not _xorIdle(dX, p)]
	for p in lCtrls:
		dT = _joinTarget(p)
		if dT is None: continue
		sVal = _valueFor(lOk, dX, p)
		if sVal is not None: bSends = p.required or not _sameAsDefault(p, sVal)
		else: bSends = p.required and (p.value is not None)
		if bSends and not any(dT is d for d in lLive): lLive.append(dT)

	out = _Out()
	for p in lCtrls:
		dT = _joinTarget(p)
		bLive = (dT is not None) and any(dT is d for d in lLive)

		sVal = _valueFor(lOk, dX, p)
		bDefault = False
		if sVal is None:
			if (not p.required and not bLive) or (p.value is None): continue
			sVal = p.value
			bDefault = True

		# A required default fills a hole, it does not replace what another
		# control already put in a shared parameter.  Part of a joined value
		# replaces nothing, it adds.
		if bDefault and not bLive and (out.find(p.param) is not None): continue

		# A value equal to the default carries no information unless the
		# server insists on hearing it, or it is part of a joined value that
		# is going out anyway
		if not bDefault and not p.required and not bLive and _sameAsDefault(p, sVal): continue

		# A switch adds its element to a joined value in one state only, on
		# unless its set block says otherwise
		if bLive and (p.type == 'bool'):
			trig = p.set.get('value')
			if (_parseBool(sVal) is True) != (trig if isinstance(trig, bool) else True): continue

		sWhy = _translate(p, sVal, out)
		if sWhy: return (None, sWhy)

	# Protocol parameters the node marks required, whatever supplies them
	for (sName, dParam) in src.params.items():
		if not isinstance(dParam, dict) or (dParam.get('required') is not True): continue
		if out.find(sName) is not None: continue
		lSetBy = [_propSays(p) for p in src.props if p.param == sName]
		if lSetBy:
			return (None, "A value for %s is required"%(' or '.join(lSetBy)))
		return (None, "Required parameter %s is missing and nothing in this source's "
		        "interface sets it, the node is broken"%sName)

	sUrl = src.baseUrls[nBase]
	sJoin = '&' if ('?' in sUrl) else '?'
	for prm in out.params:
		# one pair, or one per piece for a parameter that repeats
		lVals = [piece.val for piece in prm.pieces] if prm.repeat else [prm.join()]
		for sVal in lVals:
			sUrl += "%s%s=%s"%(sJoin, prm.name, _urlEncode(sVal))
			sJoin = '&'
	return (sUrl, None)


#############################################################################
# Forms.  Controls are named for the property they set, so a query string
# is a requisition, and an example's settings written as a query string
# fill in the form.  Names starting with '_' are the form's own:
#
#   _form        This came from the form, so a checkbox that is missing
#                was left unchecked
#   _xor.NAME    The radio buttons of exclusive set NAME, the value is the
#                key of the toggle switched on
#   _baseN       Send the browser to the data, using base URL N
#   _show        Print the data URLs instead

def queryReq(src, lQuery):
	"""The query string of a source page as a requisition"""
	dQuery = {}
	for (sKey, sVal) in lQuery:
		dQuery.setdefault(sKey, []).append(sVal)
	bForm = ('_form' in dQuery)

	lReq = []
	for p in src.props:
		if p.set is None: continue

		if p.key in dQuery:
			# Checkboxes of a list arrive as one pair each
			if p.multi: lReq.append((p.key, ','.join(dQuery[p.key])))
			else: lReq.append((p.key, dQuery[p.key][-1].strip()))

		elif p.isEnable() and (p.grp.xor is not None) and (('_xor.%s'%p.grp.xor) in dQuery):
			if dQuery['_xor.%s'%p.grp.xor][-1] == p.key: lReq.append((p.key, 'true'))

		elif bForm and (p.type == 'bool'):
			lReq.append((p.key, 'false'))

		elif bForm and p.multi:
			lReq.append((p.key, ''))

	# Keys that name nothing, so that a mistyped link is not quietly a
	# request for something else
	for (sKey, sVal) in lQuery:
		if not sKey.startswith('_') and (sKey != 'resolve') and (sKey not in src.byKey):
			lReq.append((sKey, sVal))

	if not bForm: return lReq

	# Without javascript the controls of a format that is not selected are
	# still in the form, and are sent.  A browser with them disabled would
	# not, so they are dropped here.
	dX = _xorStates(src, [(src.byKey.get(sKey), sVal) for (sKey, sVal) in lReq])
	return [
		(sKey, sVal) for (sKey, sVal) in lReq
		if (sKey not in src.byKey) or not _xorIdle(dX, src.byKey[sKey])
	]


class FormState(object):
	"""What each control of a form shows: the node's defaults with a
	requisition laid over them"""

	def __init__(self, src, lReq):
		self.src = src
		lMatch = [(src.byKey.get(sKey), sVal) for (sKey, sVal) in lReq]
		self.dX = _xorStates(src, lMatch)
		self.dVal = {}
		for (p, sVal) in lMatch:
			if p is not None: self.dVal[p] = sVal

	def text(self, p):
		sVal = self.dVal.get(p)
		if (sVal is None) or _noValue(sVal, p.multi): sVal = p.value
		return sVal or ''

	def isOn(self, p):
		if p.isEnable() and (self.dX[p.grp].state is not None):
			return self.dX[p.grp].state
		return _parseBool(self.text(p)) is True

	def items(self, p):
		return [s.lower() for s in _split(self.text(p))]


def _hostSimpleName(sBase):
	sLow = sBase.lower()
	if sLow.startswith('https://'):  sLow = sLow[8:]
	elif sLow.startswith('http://'): sLow = sLow[7:]
	if len(sLow) == 0: return sBase

	sLow = sLow[0].upper() + sLow[1:]

	n = sLow.find('.')
	if n != -1: return sLow[:n]
	n = sLow.find('/')
	if n != -1: return sLow[:n]
	n = sLow.find('?')
	if n != -1: return sLow[:n]
	return sLow

def _propLabel(p):
	if 'label' in p.d: return p.d['label']
	return p.name[0].upper() + p.name[1:]

def _propUnits(p):
	"""The units of a property, or of the group it is a property of"""
	if 'units' in p.d: return p.d['units']
	if p.name.lower() in ('min', 'max'):
		for q in p.grp.props:
			if (q.name == 'units') and q.value: return q.value
	return None

def _propNote(p, bTitle=True):
	"""Text that follows a control: its range and what it is for"""
	lOut = []
	lRange = p.set.get('range')
	if isinstance(lRange, list) and (len(lRange) == 2):
		lOut.append('(%s to %s)'%(esc(lRange[0]), esc(lRange[1])))
	if bTitle and ('title' in p.d):
		lOut.append('- %s'%esc(p.d['title']))
	return ' '.join(lOut)

def _prnCtrl(p, state, bTitle=True):
	"""Print the control for one property"""
	sKey = esc(p.key)
	sLabel = esc(_propLabel(p))
	sUnits = _propUnits(p)
	sTip = ''
	if 'description' in p.d: sTip = ' title="%s"'%esc(p.d['description'])

	if p.isEnable() and (p.grp.xor is not None):
		pout('<label%s><input type="radio" name="_xor.%s" value="%s"%s> <b>%s</b></label>'%(
			sTip, esc(p.grp.xor), sKey, ' checked' if state.isOn(p) else '', esc(p.grp.label())
		))
		if 'title' in p.grp.d: pout('- %s'%esc(p.grp.d['title']))

	elif p.type == 'bool':
		if p.isEnable():   # Output this variable, or not
			sLabel = 'Output <b>%s</b>'%esc(p.grp.label())
			sNote = ('- %s'%esc(p.grp.d['title'])) if ('title' in p.grp.d) else ''
		else:
			sLabel = '<b>%s</b>'%sLabel
			sNote = _propNote(p, bTitle)
		pout('<label%s><input type="checkbox" name="%s" value="true"%s> %s</label> %s'%(
			sTip, sKey, ' checked' if state.isOn(p) else '', sLabel, sNote
		))

	elif (p.type == 'enum') and p.multi:
		pout('<span%s><b>%s</b> %s</span><br>'%(sTip, sLabel, _propNote(p, bTitle)))
		lOn = state.items(p)
		for (sItem, dItem) in zip(p.enum, p.items):
			sItemTip = ''
			if 'title' in dItem: sItemTip = ' title="%s"'%esc(dItem['title'])
			pout('<label%s> &nbsp; <input type="checkbox" name="%s" value="%s"%s> %s</label>'%(
				sItemTip, sKey, esc(sItem), ' checked' if (sItem.lower() in lOn) else '',
				esc(dItem.get('label', sItem))
			))

	elif p.type == 'enum':
		pout('<label%s><b>%s</b>'%(sTip, sLabel))
		pout('<select name="%s">'%sKey)
		sCur = state.text(p).lower()
		# Something that sends nothing: no choice made, or a default the
		# list does not have
		if sCur not in [s.lower() for s in p.enum]:
			pout('   <option value="" selected>%s</option>'%esc(state.text(p)))
		elif (p.value is None) and not p.required:
			pout('   <option value=""></option>')
		for (sItem, dItem) in zip(p.enum, p.items):
			sText = dItem.get('label', sItem)
			if ('title' in dItem) and ('label' not in dItem):
				sText = "%s - %s"%(sItem, dItem['title'])
			pout('   <option value="%s"%s>%s</option>'%(
				esc(sItem), ' selected' if (sItem.lower() == sCur) else '', esc(sText)
			))
		pout('</select></label> %s'%_propNote(p, bTitle))

	else:
		sCur = state.text(p)
		nSize = 8
		if p.type == 'time': nSize = 18
		elif p.multi or (p.type == 'text'): nSize = 24
		nSize = min(max(nSize, len(sCur) + 2), 75)
		if sUnits and (sUnits.lower() != 'utc'): sLabel = '%s (%s)'%(sLabel, esc(sUnits))

		# The browser can hold a form back for an empty box, which is only
		# right if the box counts in every request the form can make
		sReq = ''
		if p.required and (p.value is None) and (p.grp.xor is None): sReq = ' required'

		pout('<label%s>%s <input type="text" name="%s" size="%d" value="%s"%s></label> %s'%(
			sTip, sLabel, sKey, nSize, esc(sCur), sReq, _propNote(p, bTitle)
		))

def _prnGroupForm(grp, state):
	"""Print the controls of one group.  Returns the number printed."""
	lCtrls = [p for p in grp.props if p.set is not None]
	if len(lCtrls) == 0: return 0

	if grp.sec == 'options':
		for p in lCtrls:
			pout('<p>')
			_prnCtrl(p, state)
			pout('</p>')
		return len(lCtrls)

	# Variables and formats.  The toggle leads, or the group's name does.
	# Range properties share the first line, in the usual order.
	tOneLiner = ('min', 'max', 'res', 'inter')
	lFirst = [p for sName in tOneLiner for p in lCtrls if p.name == sName]
	lRest = [p for p in lCtrls if (p not in lFirst) and not p.isEnable()]

	pout('<p>')
	if (grp.enable is not None) and (grp.enable.set is not None):
		_prnCtrl(grp.enable, state)
	else:
		pout('<b>%s:</b> &nbsp;'%esc(grp.label()))
	for p in lFirst:
		_prnCtrl(p, state, False)
	for p in lRest:
		pout('<br> &nbsp; ')
		_prnCtrl(p, state)
	pout('</p>')
	return len(lCtrls)


def _prnContacts(dNode, sKind, sMsg):
	"""Print the names of the contacts of one kind"""
	lNames = []
	lContacts = dNode.get('contacts')
	if isinstance(lContacts, list):
		for d in lContacts:
			if isinstance(d, dict) and (d.get('type') == sKind) and ('name' in d):
				lNames.append(d['name'].strip())
	if len(lNames) > 0:
		pout("<p>%s <b>%s</b>.</p>"%(sMsg, esc(", ".join(lNames))))


def prnHttpSource(dSrc, lQuery=None, bSubSec=False):
	""" Print an http source: what it is, its examples and a form that
	requests data from it.

	Args:
		dSrc: The node, with '_url' and '_path' added

		lQuery: The (name, value) pairs of the page's query string.  Settings
			among them fill in the form.

		bSubSec: True if this source is one part of a larger page
	"""

	sSrcUrl = dSrc['_url']
	if lQuery is None: lQuery = []
	dQuery = dict(lQuery)

	# A node read by its URL has no page of its own to come back to, the
	# resolver has to find it again
	bWalked = (len(dSrc['_path']) > 0)
	sAction = catPathToBrowseUrl(dSrc['_path']) if bWalked else scriptUrl()

	if bSubSec:
		if bWalked:
			pout('<a href="%s">View this source only</a>'%esc(sAction))
	elif 'title' in dSrc:
		pout("<h3>%s</h3>"%esc(dSrc['title']))

	if not bSubSec and ('description' in dSrc):
		pout("<p>%s</p>"%esc(dSrc['description']))

	_prnContacts(dSrc, 'technical',
		"Technical problems using this data source should be directed to:")

	dProto = dSrc.get('protocol')
	if not isinstance(dProto, dict):
		return _missingKeyError('protocol', sSrcUrl)

	if 'baseUrls' not in dProto:
		if 'base_urls' in dProto:
			pout('<p class="error">This node is written in the layout used before '
			     'HttpStreamSrc version 0.7, which this browser no longer reads.  '
			     'The node itself is <a href="%s">here</a>.</p>'%esc(sSrcUrl))
			return None
		return _missingKeyError('protocol:baseUrls', sSrcUrl)

	if not isinstance(dSrc.get('interface'), dict):
		return _missingKeyError('interface', sSrcUrl)

	dAuth = dProto.get('authorization')
	if isinstance(dAuth, dict) and (dAuth.get('required') is True):
		pout('<p><i><span class="error">Resticted data source</span>.</i>')
		if 'realm' in dAuth:
			pout('You will be asked to authenticate to the realm "'
			     '<b>%s</b>" on download.</p>'%esc(dAuth['realm']))
		else:
			pout("You will be asked to authenticate on download.</p>")

	src = Source(dSrc)
	lReq = queryReq(src, lQuery)
	state = FormState(src, lReq)

	# They asked for data, or for the URL of it.  If the settings made a URL
	# and the browser is still here, then it is to be shown.
	lBaseKeys = [s for s in dQuery if s.startswith('_base')]
	if ('_show' in dQuery) or lBaseKeys:
		(lOk, lWhy, dX) = checkReq(src, lReq)
		lUrls = []
		if not lWhy:
			for i in range(len(src.baseUrls)):
				(sUrl, sWhy) = reqUrl(src, lOk, dX, i)
				if sWhy:
					lWhy.append(sWhy)
					break
				lUrls.append(sUrl)
		if lWhy:
			pout('<p class="error">No request was made:</p>\n<ul>')
			for sWhy in lWhy: pout('<li class="error">%s</li>'%esc(sWhy))
			pout('</ul>')
		else:
			pout('<p>These settings request:</p>\n<ul>')
			for sUrl in lUrls: pout('<li><a href="%s">%s</a></li>'%(esc(sUrl), esc(sUrl)))
			pout('</ul>')

	# Print the examples.  Each fills in the form, so that what it asks for
	# can be seen, and changed, before anything is downloaded.
	if len(src.examples) > 0:
		pout("<p>Example queries:")
		for dExample in src.examples:
			if not isinstance(dExample, dict): continue
			lExReq = exampleReq(dExample)
			if not bWalked: lExReq = [('resolve', sSrcUrl)] + lExReq
			sTmp = dExample.get('label') or dExample.get('title') or 'Example'
			sTip = ''
			if 'title' in dExample: sTip = ' title="%s"'%esc(dExample['title'])
			pout('<a href="%s?%s"%s>%s</a> &nbsp;'%(
				esc(sAction), esc(urlencode(lExReq)), sTip, esc(sTmp)))
		pout("</p>")

	pout('<form action="%s" method="get">'%esc(sAction))
	pout('<input type="hidden" name="_form" value="1">')
	if not bWalked:
		pout('<input type="hidden" name="resolve" value="%s">'%esc(sSrcUrl))

	for (sSec, sLegend) in (
		('coords', 'Coordinate Options'), ('data', 'Data Options'),
		('formats', 'Output Format'), ('options', 'Additional Options')
	):
		lGroups = [g for g in src.section(sSec) if any(p.set is not None for p in g.props)]
		if len(lGroups) == 0: continue

		pout('<fieldset><legend><b>%s:</b></legend>'%sLegend)
		nCtrls = sum(len([p for p in g.props if p.set is not None]) for g in lGroups)
		pout('<div %s>'%('class="srcopts_scroll_div"' if (nCtrls > 12) else ''))
		for grp in lGroups:
			_prnGroupForm(grp, state)
		pout('</div>')
		pout('</fieldset>')

	# What comes back
	lFormats = []
	for grp in src.section('formats'):
		if state.dX[grp].state is False: continue
		if (grp.enable is not None) and (grp.xor is None) and not state.isOn(grp.enable): continue
		lMime = grp.d.get('mimeTypes')
		if isinstance(lMime, list) and (len(lMime) > 0):
			lFormats.append('%s (<tt>%s</tt>)'%(esc(grp.label()), esc(lMime[0])))
	if len(lFormats) == 1:
		pout("<p>Output will be a %s unless changed via format options</p>"%lFormats[0])

	# One submit button per mirror.  A node that was not reached through
	# the catalog gets none: this script would then send browsers wherever
	# a file anyone can write says to.
	if bWalked:
		for i in range(len(src.baseUrls)):
			pout('<input type="submit" name="_base%d" value="Get from %s">'%(
				i, esc(_hostSimpleName(src.baseUrls[i]))))
	pout('<input type="submit" name="_show" value="Show URL">')
	pout('</form>')

	prnIdentifiers(dSrc, False)

	pout('<hr class="datasrc_sep">')


def sourceRedirect(dSrc, lQuery):
	"""If a source page's query asks for data, and the settings are good,
	return the URL to send the browser to.  None if a page is to be shown
	instead, which is where problems with the settings are reported."""
	lBase = [sKey for (sKey, sVal) in lQuery if sKey.startswith('_base')]
	if (len(lBase) == 0) or (len(dSrc['_path']) == 0): return None
	try:
		nBase = int(lBase[0][len('_base'):])
	except ValueError:
		return None

	dProto = dSrc.get('protocol')
	if not isinstance(dProto, dict) or not isinstance(dSrc.get('interface'), dict):
		return None

	src = Source(dSrc)
	(lOk, lWhy, dX) = checkReq(src, queryReq(src, lQuery))
	if lWhy: return None
	(sUrl, sWhy) = reqUrl(src, lOk, dX, nBase)
	if sUrl is None: return None

	# It is about to be a header line
	if not sUrl.lower().startswith(('http://', 'https://')): return None
	if any((ord(c) < 0x21) or (ord(c) > 0x7e) for c in sUrl): return None
	return sUrl


#############################################################################

def prnSourceSet(dNode):
	"""Print a SourceSet, a dataset and the ways to get it.  The Collection
	nodes of 2018 are printed by this as well, as far as they go."""

	if 'title' in dNode:
		pout("<h3>%s</h3>"%esc(dNode['title']))

	if 'description' in dNode:
		pout("<p>%s<br><br></p>"%esc(dNode['description']))

	dUsage = dNode.get('usage')
	if isinstance(dUsage, dict):
		pout("<p>\n")
		if 'policy' in dUsage:
			pout('Usage Policy: <b class="error">%s</b> <br>'%esc(dUsage['policy']))
		if 'extern' in dUsage:
			pout('Please read <a href="%s">%s</a> before using these data.\n'%(
			     esc(dUsage['extern']), esc(dUsage['extern'])))
		pout("</p>\n")

	_prnContacts(dNode, 'scientific',
		"Questions about the nature and usefulness of this data set should be directed to:")

	for (sSec, sMsg) in (
		('coords', 'Coordinates for these data include:'),
		('data', 'Data items in this collection include:')
	):
		dVars = dNode.get(sSec)
		if not isinstance(dVars, dict) or (len(dVars) == 0): continue

		pout("<p>%s"%sMsg)
		sStyle = "indent30_div"
		if len(dVars) > 12: sStyle = "indent30_scroll_div"
		pout('<div class="%s">'%sStyle)

		lVars = list(dVars.keys())
		if 'time' in lVars:    # Make sure time is first
			lVars.remove('time')
			lVars = ['time'] + lVars

		for sVar in lVars:
			dVar = dVars[sVar]
			if not isinstance(dVar, dict): continue
			sOut = "<b>%s</b>"%esc(dVar.get('label') or dVar.get('name') or sVar)
			if isinstance(dVar.get('units'), str): sOut += " (%s)"%esc(dVar['units'])

			lRange = dVar.get('validRange')
			if isinstance(lRange, list) and (len(lRange) == 2):
				sOut += " from <b>%s</b> to <b>%s</b>"%(esc(lRange[0]), esc(lRange[1]))

			if 'title' in dVar:
				sOut += " - %s"%esc(dVar['title'])

			pout("%s<br>"%sOut)
		pout('</div></p>')

	if isinstance(dNode.get('EPNcore'), dict):
		pout('<h4 class="obscore"> EPN-Core Metadata</h4>')
		pout('<p class="obscore">')
		l = list(dNode['EPNcore'].keys())
		l.sort()
		for s in l:
			pout('<span class="obscore">%s:&nbsp;<b>%s</b></span> &nbsp; &nbsp; &nbsp; '%(
			     esc(s), esc(dNode['EPNcore'][s])))
		pout('</p>')

	# The ways to get the data.  Each is listed here by the SourceSet, with
	# a label for the kind of access it is.  Only the kinds this script has
	# a form for are read.
	sSubKey = _subKey(dNode)
	dEntries = dNode[sSubKey] if sSubKey else {}
	dSubs = getDirectSubs(dNode, sSubKey, ('HttpStreamSrc',)) if sSubKey else {}

	if len(dEntries) == 0:
		pout("<p>Unfortunately, no sources are listed for this data collection</p>")
		return

	for sKey in dEntries:
		dEnt = dEntries[sKey]
		if not isinstance(dEnt, dict): continue
		sType = dEnt.get('type') or 'unknown'
		sTmp = dEnt.get('label') or dEnt.get('name')
		if not sTmp and (sKey in dSubs): sTmp = dSubs[sKey].get('name')

		pout('<div class="datasrc_div">')
		pout("<h3><span>Access via %s</span></h3>"%esc(sTmp or sType))
		if 'description' in dEnt:
			pout("<p>%s</p>"%esc(dEnt['description']))

		if sKey in dSubs:
			prnHttpSource(dSubs[sKey], None, True)
		else:
			if sType == 'HttpStreamSrc':
				pout('<p class="error">The node for this source could not be read.</p>')
			else:
				pout("<p>This browser has no form for sources of type <b>%s</b>.</p>"%esc(sType))
			lUrls = dEnt.get('urls')
			if isinstance(lUrls, list) and (len(lUrls) > 0):
				pout('<div class="identifers">Listed at: ')
				for sUrl in lUrls:
					pout('<a href="%s">%s</a> &nbsp; '%(esc(sUrl), esc(sUrl)))
				pout('</div>')
			pout('<hr class="datasrc_sep">')
		pout("</div>")

	prnIdentifiers(dNode)

	pout('<hr class="code_sep">')


#############################################################################
def prnCodeScript():
	# small chunk of java script to make code examples collapse
	pout('''
<script>
var acc = document.getElementsByClassName("accordian");
var i;

for (i = 0; i < acc.length; i++) {
    acc[i].addEventListener("click", function() {
        this.classList.toggle("active");
        var panel = this.nextElementSibling;
        if (panel.style.display === "block") {
            panel.style.display = "none";
        } else {
            panel.style.display = "block";
        }
    });
}
</script>
''')

#############################################################################
def prnFooter():
	# The signature is the web server's own text, already HTML
	pout('''
<div class="footer">
  <div>More information about das2 can be found at:
  <a href="http://das2.org/">http://das2.org/</a>.</div>
  <div>%s</div>
  <div><a href="https://github.com/das-developers/das-cat">
  Download the code for this catalog client</a></div>
</div>'''%(os.getenv('SERVER_SIGNATURE') or '')
	)
	pout("</body>\n</html>")

#############################################################################
# Main

def main(lQuery):
	"""Build the page in g_lOut.

	Args:
		lQuery: The query string as (name, value) pairs, in order

	Returns:
		None for a page, or the URL to redirect the browser to.
	"""

	sScript = scriptUrl()
	if sScript.startswith("https"):
		sProto = "https"
	else:
		sProto = "http"

	sTree = g_sTree[0].upper() + g_sTree[1:]

	# What ID do they want to know about, can be given as a query id or as
	# path info, or just a direct URL that skips the whole resolution stage
	sPath = dict(lQuery).get('resolve', '').strip()

	if len(sPath) > 0:
		# We can get direct urls via the resolver, so check for that
		if sPath.lower().startswith('http'):
			(dNode, lPathTo, lTried) = getNode(sPath)
		else:
			sPath = sPath.lower()
			if not sPath.startswith('tag:'):
				sPath = "%s:/%s"%(g_sDefDas2SiteTag, sPath)

			(dNode, lPathTo, lTried) = getNode(sPath)
	else:
		sPathInfo = ''
		if os.getenv("PATH_INFO"):
			sPathInfo = os.getenv("PATH_INFO")
		sPath = pathInfoToCatId(sPathInfo)

		(dNode, lPathTo, lTried) = getNode(sPath)

	# A form on a source page that worked out sends the browser on its way
	if (dNode != None) and (dNode['type'] == 'HttpStreamSrc'):
		sUrl = sourceRedirect(dNode, lQuery)
		if sUrl != None:
			return sUrl

	pout("""
<head>
	<title>Das2 %s Catalog</title>
	<link rel="stylesheet" type="text/css" media="screen" href="%s%s" />
</head>
"""%(sTree, sProto, g_sStyleSheet))

	pout('''
<body>
<div class="header">
	<div class="hdr_left">
		<a href="%s">
		<img src="%s%s" alt="Das2" width="80" height="80">
		</a>
	</div>
	<div class="hdr_center">
	<h2>%s Catalog Browser</h2>
	</div>
	<div class="hdr_right">
'''%(esc(scriptUrl()), sProto, g_sLogo, sTree))

	if g_sTree == 'site':
		pout('''
	   <a href="http://vespa.obspm.fr"><h3 class="hdr_right">VESPA Search</h3></a>
		<a href="http://space.physics.uiowa.edu/das/testcat">
		<h4 class="yellow">Test Catalog</h4></a>
''')
	else:
		pout('<a href="http://das2.org/browse"><h3 class="yellow">Main Catalog</h3></a>')
	pout('''
	</div>
</div>
''')

	pout('''
<form action="%s" >
<div class="resolver">
  <label for="resolve_text">Catalog Path or URL</label>
  <input type="text" id="resolve_text" name="resolve" value="%s" autofocus>
  <input type="submit" value="Resolve" >
</div>
</form>
'''%(esc(scriptUrl()), esc(sPath)))

	pout('<div class="main">')

	if dNode == None:
		pout("<p>Catalog node <b>%s</b> doesn't exist</p>"%esc(sPath))
		pout("<p>Lookup path follows:</p>\n<ul>")

		for i in range(0, len(lTried)):
			sUrl = esc(lTried[i])
			if i == (len(lTried) - 1):
				pout('<li><a href="%s">%s</a> &lt;-- trail ends here</li>'%(sUrl, sUrl))
			else:
				pout('<li><a href="%s">%s</a></li>'%(sUrl, sUrl))

		pout("</ul>")
		pout("</div>")
		prnFooter()
		return None

	prnBrowseBar(lPathTo, dNode)

	if dNode['type'] in ('SourceSet', 'Collection'):
		prnSourceSet(dNode)
	elif (dNode['type'] == 'Catalog') and isinstance(dNode.get('catalog'), dict):
		prnCatalog(dNode)
	elif dNode['type'] == 'HttpStreamSrc':
		prnHttpSource(dNode, lQuery)
	else:
		pout("<h2>Unknown node type %s</h2>"%esc(dNode['type']))
		pout("<p>Raw catalog entry displayed below</p>")
		pout("<pre>")
		sOut = json.dumps(dNode, ensure_ascii=False, indent="  ", sort_keys=True)
		pout(esc(sOut))
		pout("</pre>")

	pout("</div>")

	prnCodeScript()

	prnFooter()

	return None

##############################################################################
# Stub main for cgi.  The page is built whole and then sent, because a
# source page may turn out to be a redirect.  The price is that a failure
# has to be caught here to be seen at all.

def cgiMain():
	sHdr = "Content-Type: text/html; charset=utf-8\r\n\r\n<!DOCTYPE html>\n<html>\n"
	try:
		lQuery = parse_qsl(os.getenv('QUERY_STRING') or '', keep_blank_values=True)
		sUrl = main(lQuery)
		if sUrl != None:
			sOut = "Status: 302 Found\r\nLocation: %s\r\n\r\n"%sUrl
		else:
			sOut = sHdr + ''.join(g_lOut)
	except Exception as e:
		perr(traceback.format_exc())
		sOut = "Status: 500 Internal Server Error\r\n%s" \
		       "<body><h2>The catalog browser failed</h2>\n<p>%s: %s</p>\n" \
		       "<p>The server's error log has the details.</p></body>\n</html>\n"%(
		       sHdr, esc(type(e).__name__), esc(e))

	sys.stdout.buffer.write(sOut.encode('utf-8'))
	return 0

# Return values don't matter in CGI programming.  That's unfortunate
if __name__ == '__main__':
	cgiMain()
