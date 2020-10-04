#!/usr/bin/python3

# Copyright 2018 Chris Piker
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

# Independent CGI script das2 catalog client, does not depend on other das2
# libraries.

import sys
from os.path import basename as bname

def pout(thing):
	s = "%s\n"%thing
	sys.stdout.buffer.write(s.encode('utf-8'))


def perr(thing):
	s = "%s\n"%thing
	sys.stderr.buffer.write(s.encode('utf-8'))


# Get header out the door before anything can go wrong
pout("Content-type: text/html; charset=utf-8\r\n\r")
pout("<!DOCTYPE html>")
pout("<html>")

import os
import cgi
import cgitb

cgitb.enable()

import requests
import json

# Toggle the hierarchy we wish to show with this copy of the browse tool
#g_sTree = 'test'
g_sTree = 'site'

#############################################################################
# Builtin defaults (update for your site)

# Prefer http, it uses less overhead and this is public information anyway
g_lCatRoots = [
	"http://das2.org/catalog",
	"https://raw.githubusercontent.com/das-developers/das-cat/master/cat/index.json"
	#"http://das2.org/cat_test/index.json"
	# alternate root catalog mirror sites for reliablilty go here
]

g_sDefDas2SiteTag = 'tag:das2.org,2012:%s'%g_sTree

# prepend the same protocol (http or https) as the script was called under
g_sStyleSheet = "://das2.org/cat_resource/style.css"
g_sLogo       = "://das2.org/cat_resource/das2logo_rv.png"


#############################################################################
def _missingKeyError(sKey, sUrl):
	pout(
'''<p class="error">Format error in node from <a href="%s">%s</a>, 
key <b>%s</b> is missing.</p>
'''%(sKey, sUrl))
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

	if (sProto == 'http://' and nPort != 80) or (sProto == 'https//' and nPort != 443):
		sPort = ':%d' % nPort

	g_sScriptUrl = "%s%s%s%s"%(sProto, os.getenv('SERVER_NAME'), sPort,
	                           os.getenv('SCRIPT_NAME'))
	return g_sScriptUrl

#############################################################################
def _isTrue(d, key):
	if key not in d: return False

	if d[key] == True: return True
	if d[key] == False: return False

	if d[key].lower() in ('true','1','yes'):
		return True
	return False


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
# Get Node definition and path information by Id

def _getNode(lAttempted, lPathTo, sUrl, sPath, sWanted):
	
	if sUrl not in lAttempted:
		lAttempted.append(sUrl)
	else:
		# We have a loop, break it here
		pout("Loop detected in catalog, at %s, needs to be fixed<br><br>"%sUrl)
		return None

	try:
		res = requests.get(sUrl)
		if res.status_code != requests.codes.ok:
			return None
		dNode = json.loads(res.text)
	except Exception as e:
		#pout("Failed to get %s, reason: %s<br><br>\n"%(sUrl, str(e)))
		return None


	# Slide in the catalog path and the source URL so it stays attached
	dNode['_url'] = sUrl
	dNode['_path'] = sPath	

	#pout("<p>Looking for '%s', I am at '%s'</p>"%(sWanted, lPathTo))
	#return None
	
	if (sPath == sWanted) or (sPath[:-1] == sWanted) or (sPath == sWanted[:-1]):
		# This is the node you're looking for, note that the root catalog's
		# _path is None, so setting None for the sWanted will match the root
		return dNode

	# See if I match up to a '/'
	if not sWanted.startswith(sPath):
		# This isn't the node you looking for and I don't know how you got here
		return None

	# This is an ancester of the node you're looking for check the catalog
	sCatElement = 'catalog'
	if dNode['type'] == 'Collection':
		sCatElement = 'sources'

	if not sCatElement in dNode:
		return None   # Don't have a catalog

	dCat = dNode[sCatElement]

	sSep = '/'
	if 'separator' in dNode:
		sSep = dNode['separator']
		if sSep == None:
			sSep = ""

	# For each sub item append it's path to mine and see if the requested
	# path starts with total child string
	for sKey in dCat:
		sSubPath = "%s%s%s"%(sPath, sSep, sKey)

		#pout("<p>Looking for %s, testing %s</p>\n"%(sWanted, sSubPath))
		if not sWanted.startswith(sSubPath):
			continue

		dCatEnt = dCat[sKey]        # This is the one, try all the urls
		if not 'urls' in dCatEnt:
			continue

		for sUrl in dCatEnt['urls']:
			# Going for a sub node, add in my information so that they can get
			# back to me rapidly, but only if I'm part of the site hierarchy,
			# other hierarchies aren't the focus of this browse tool
			if sPath.startswith(g_sDefDas2SiteTag):
				lPathTo.append(
					(dNode['name'], dNode['title'], catPathToBrowseUrl(sPath) )
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
# libdas2 does this automatically

def getNode(sWanted):
	"""Get a catalog node item and return items along the path to it.
	
	The basic resolution is that: 
	
	   1. Each node that is loaded is supplied with it's name by it's parent.
		
		2. To form child nodes the separator is combined with the calalog entry
		   and passed to the sub-node loader.
	
	
	arguments:
		sWanted - The virtual path that is desired, these look like 
		          "tag:das2.org,2012:site:/uiowa" (or test:/) or a direct
                          URL to a JSON file, for ex:
                             file:///home/janed/source.json, http://... 
	returns:
		(dNode, lPathTo, lUrls )

		dNode - The final node, or None if it couldn't be reached

		lPathTo - A list of Names, Titles and Browse tool URLs for items
		          leading to this location, last item (dNode) is not included
					 Each element of the path to list is (Name, Title, Browse_URL)

		lUrls - A list of Catalog URLs used to arrive at this infomation, mostly
		        for diagnostic purposes
	"""
	#pout("<p>Getting ID: %s</p>"%sWanted)
	lAttempted = []
	lPathTo = []

	sLow = sWanted.lower()
	if sLow.startswith('http') or sLow.startswith('https'):
		lAttempted.append(sWanted)

		# just go get it, path information will be empty
		try:
			res = requests.get(sWanted)
			if res.status_code != requests.codes.ok:
				return (None, [], lAttempted)
			dNode = json.loads(res.text)
			dNode['_url'] = sWanted
			dNode['_path'] = ""           # I did not walk a catalog to get here
			                              # path information not available
													
			return (dNode, lPathTo, lAttempted)

		except Exception as e:
			#pout("Failed to get %s, reason: %s<br><br>\n"%(sUrl, str(e)))
			pass

	else:
		sPath = "" 
		for sUrl in g_lCatRoots:
			dNode = _getNode(lAttempted, lPathTo, sUrl, sPath, sWanted)
			if dNode != None:
				#pout("<p>Path is %s</p>"%lPathTo)
				return (dNode, lPathTo, lAttempted)

	return (None, [], lAttempted)

############################################################################

def getDirectSubs(dNode, sListKey):
	"""Get sub-nodes of a node.  Not used at part of normal getNode traversal.

	Args:
		dNode - The node for which sub-items are desired
		sListKey - The key to the json object that lists the sub-nodes
	returns:
		A dictionary of direct sub-nodes which may be empty if no sub-nodes are
		present
	"""
	dRet = {}
	if sListKey not in dNode: return dRet

	dSubs = dNode[sListKey]

	for sKey in dSubs:
		dCatEnt = dSubs[sKey]

		for sUrl in dCatEnt['urls']:
			try:
				res = requests.get(sUrl)
				if res.status_code != requests.codes.ok:
					continue
				dSubNode = json.loads(res.text)
			except Exception as e:
				pass   # Complain here?

			# Slide in the source URL and path we took so it stays attached
			dSubNode['_url'] = sUrl
			sSep = '/'
			if 'separator' in dNode:
				sSep = dNode['separator']
			if sSep == None:
				sSep = ""
				
			dSubNode['_path'] = "%s%s%s"%(dNode['_path'], sSep, sKey)
			dRet[sKey] = dSubNode
			break

	return dRet


#############################################################################
def prnBrowseBar(lPathTo, dNode):
	"""lPathTo a list of (Name, Title, Browse_URL) triplets leading to dNode
	"""
	if len(lPathTo) == 0:
		#pout('<p class="error">lPathTo is empty</p>')
		return

	pout('  <ul id="catnav">')
	for i in range(0, len(lPathTo)):
		sName = lPathTo[i][0].rstrip('/')
		if i == 0:
			pout('  <li><a href="%s">%s</a></li>'%(lPathTo[i][2], sName))
		else:
			pout('  <li>&gt; <a href="%s">%s</a></li>'%(lPathTo[i][2], sName))

	pout('  <li> &gt; %s</li>'%dNode['name'])
	pout('</ul>')

#############################################################################
def prnCatalog(dNode):

	dSub = dNode['catalog']
	
	sSep = "/"
	if 'separator' in dNode:
		sSep = dNode['separator']
		if sSep == None: 	sSep = ""

	if 'title' in dNode:
		pout("<h3>%s</h3>"%dNode['title'])
		
	if 'description' in dNode:
		pout("<p>%s<br><br></p>"%dNode['description'])

	lKeys = list(dSub.keys())
	lKeys.sort()
	#pout('<div id="indent30_div">')
	pout('<ul>')
	for sKey in lKeys:
		sSubUrl = catPathToBrowseUrl(dNode['_path'] + sSep + sKey)
		if 'name' in dSub[sKey]:
			sName = dSub[sKey]['name']
		else:
			sName = sKey
		if len(sName) < 2:
			sName = " &nbsp; %s &nbsp;"%sName

		if 'title' in dSub[sKey]:
			sTitle = dSub[sKey]['title']
		else:
			sTitle = "An untitled %s"%dSub[sKey]['type']

		sClass = "cat_cat"
		if dSub[sKey]['type'] == 'Collection':
			sClass = "type_stream"

		pout('<li class="%s"><a href="%s">%s</a> - %s<br></li>'%(sClass, sSubUrl, sName, sTitle))

	pout('</ul>')
	#pout('</div>')

	pout('<div class="identifers">')
	sResolve = "%s?resolve=%s"%(scriptUrl(), dNode['_path'])
	pout('<br><br>Catalog Path: <a href="%s">%s</a> &nbsp; <br>Read From: <a href="%s">%s</a></a>'%(
	     sResolve, dNode['_path'], dNode['_url'], dNode['_url']))
	pout('</div>')

	pout('<hr class="code_sep">')

	sURI = dNode['_path']
	sURI = sURI.replace('tag:das2.org,2012:','')

	if ('catalog' in dNode) and (len(list(dNode['catalog'].keys())) > 0):
		lKeys = list(dNode['catalog'].keys())
		lKeys.sort()
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
'''%(sURI,sSubNode))
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
'''%dNode['_path'])
	pout('</div>')

#############################################################################
#

def _hostSimpleName(sBase):
	sLow = sBase.lower()
	if sLow.startswith('https'):  sLow = sLow[8:]
	elif sLow.startswith('http'): sLow = sLow[7:]

	sLow = sLow[0].upper() + sLow[1:]

	n = sLow.find('.')
	if n != -1: return sLow[:n]
	n = sLow.find('/')
	if n != -1: return sLow[:n]
	n = sLow.find('?')
	if n != -1: return sLow[:n]
	return sLow

def _setHidden(dBaseUrls):
	"""Go through the base URLs see if they have any keys already set, if so
		we'll need hidden form parameters to cover those as well
	"""
	dHidden = {}
	for sUrl in dBaseUrls:
		n = sUrl.find('?')
		if n == -1: continue

		lQuery = sUrl[n+1:].split('&')
		for sPair in lQuery:
			lPair = [s.strip() for s in sPair.split("=")]
			if (len(lPair) > 1) and lPair[0] not in dHidden:
				dHidden[lPair[0]] = lPair[1]

	for sKey in dHidden:
		pout('<input type="hidden" name="%s" value="%s">'%(sKey, dHidden[sKey]))


def _inputVarTextAspect(dParams, dVar, sAspect, sCtrlId):
	"""Create a text entry field for a variable aspect such as 'minimum' or 
	'resolution'.  In addition to the given aspect the 'units' aspect is 
	inspected so this function isn't unsable for general options.

	Args:
		dParams: The http_params dictionary.  The control ID will be listed here
			if a control is generated.
		dVar: The dictionary for the overall variable
		sAspect: The dictionary key for the aspect, ex: 'maximum'
		sCtrlId: The id to use for the generated control, if any.

	Returns:
		0 if no control was created, 1 otherwise
	"""
			
	if sAspect not in dVar: return 0
	dAspect = dVar[sAspect]
	
	if 'set' not in dAspect: return 0
	
	dSet = dAspect['set']
				
	if 'units' in dAspect:  sUnits = dAspect['units']
	elif 'units' in dVar:   sUnits = dVar['units']['value']
	sUnitLbl = " (%s)"%sUnits
	sAspectLbl = sAspect[0].upper() + sAspect[1:]

	pout('<label for="%s">%s%s</label>'%(sCtrlId, sAspectLbl, sUnitLbl))
	sReq = ""
	if ('required' in dSet) and dSet['required']: sReq = 'required'
	sValue = ""
	if 'value' in dAspect: sValue = dAspect['value']
	
	# Guess a good input size based off the units
	nSize=8
	if sUnits.lower() == 'utc': nSize=18

	pout('<input size="%d" id="%s" type="text" value="%s" %s>'%(
		nSize, sCtrlId, sValue, sReq)
	)
	
	if 'flag' in dSet:
		dParams[ dSet['param'] ]['flags'][ dSet['flag'] ]['_inCtrlId'] = sCtrlId
	else:
		dParams[ dSet['param'] ]['_inCtrlId'] = sCtrlId
	
	return 1 
	
def _inputItemBoolean(dParams, dItem, sMsg, sCtrlId):
	"""Create a boolean checkbox for an item with a boolean value with a 'set'
	member.

	This control generator is useful for both variables and options as it does
	not inspect the contained option group.  Typically this is used with the
	variable 'enable' aspect or for boolean options.

	Args:
		dParams: The 'http_params' dictionary
		dItem: The dictionary describing the boolean property to set
		sMsg: The message to use to lable the check box
		sCtrlId: The control ID to assign if a control is made

	Returns:
		0 if a control was not created, 1 otherwise
	"""

	if 'set' not in dItem: return 0
	
	sChecked = ""
	if ('value' in dItem) and dItem['value'] == True: sChecked = "checked"
	
	pout('<input type="checkbox" id="%s" %s>'%(sCtrlId, sChecked))
	pout('<label for="%s">%s</label>'%(sCtrlId, sMsg))
	
	# If the default is 
	
	dSet = dItem['set']
	if 'flag' in dSet:
		dParams[ dSet['param'] ]['flags'][ dSet['flag'] ]['_inCtrlId'] = sCtrlId
		dParams[ dSet['param'] ]['flags'][ dSet['flag'] ]['_inIfCtrlVal'] = dSet['value']
	else:
		dParams[ dSet['param'] ]['_inCtrlId'] = sCtrlId	
		dParams[ dSet['param'] ]['_inIfCtrlVal'] = dSet['value']
	return 1

		
def _inputItemEnum(dParams, dItem, sMsg, sCtrlId):
	"""Create a select list control for an enum item with a 'set' member.
	
	This control generator is useful for both variables and options as it does
	not inspect the contained option group.  One example where this is useful is
	selecting the output units for the Voyager Spectrum Analyzer data.

	Args:
		dParms: The 'http_params' dictionary
		dItem: The dictionary describing the item to set.  The set method for
			this item must have an 'enum' sub-member.
	
	The flag to set cascades.  If it's in the root of 'set', then all entries
	in the enum set the same flag.  If it's in an individual item listing then
	each selection can set a different flag.

	"""
	if 'set' not in dItem: return 0
	dSet = dItem['set']
	if 'enum' not in dSet: return 0

	# We save the field ID in the value but display the new value.  
	# Case example follows from voyager.
	#
	# The input option control selects among different flag values.
	#
	# "units" : {
	#   "value": "V/m",
	#   "set": {
	#      "param":"params",
	#      "enum":[
	#          {"value":"raw", "flag":"00"},
	#          {"value":"V**2 m**-2 Hz**-1", "flag":"01"},
	#          /* or if setting whole value */
	#          {"value":"V**2 m**-2 Hz**-1", "pval":"SD"},
	#      ]
	#   }
	# }
	#
	# The input option control puts a value directly in the flag,
	# so _inIfCtrlVal is not set.  Instead _inIfNotCtrlVal is set.
	# 
	# "channel" : {
	#			"title": "Spectrum analyzer channel to output",
	#			"value": "all",
	#			"set" : { 
	#				"param":"params", 
	#				"flag":"07",
	#				"enum" : [
	#					{"value":"10.0Hz"},
	#					{"value":"17.8Hz"},
	#					{"value":"31.1Hz"},
	#					{"value":"56.2Hz"},
	#					{"value":"100Hz"},
	#					{"value":"178Hz"},
	#					{"value":"311Hz"},
	#					{"value":"562Hz"},
	#					{"value":"1.00kHz"},
	#					{"value":"1.78kHz"},
	#					{"value":"3.11kHz"},
	#					{"value":"5.62kHz"},
	#					{"value":"10.0kHz"},
	#					{"value":"17.8kHz"},
	#					{"value":"31.1kHz"},
	#					{"value":"56.2kHz"}
	#				]
	#			}
	#		}
   #   }
	
	pout(sMsg)
	pout('<select id=%s>'%sCtrlId)
	
	
	# If the current value is not in the enum, put it here without mapping 
	# information so it can't be sent
	bAddDefault = True
	for dMap in dSet['enum']:
		if dMap['value'] == dItem['value']: 
			bAddDefault = False
			break
	
	if bAddDefault:
		sCtrlVal = dItem['value']
		if 'name' in dItem:  sCtrlVal = dItem['name']
		pout('   <option value="" selected>%s</option>'%sCtrlVal)
		
	for dMap in dSet['enum']:
	
		sSelected = ""
		if dMap['value'] == dItem['value']: sSelected = "selected"
		if 'pval' in dMap: sVal = dMap['pval']
		elif 'flag' in dMap: sVal = dMap['flag']
		else: sVal = dMap['value']

		sCtrlVal = dMap['value']
		if 'name' in dMap:  sCtrlVal = dMap['name']

		pout('   <option value="%s" %s>%s</option>'%(sVal, sSelected, sCtrlVal))

		if 'param' in dMap: sParam = dMap['param']
		elif 'param' in dSet: sParam = dSet['param']
		
		# Save the control id's in the flag_set, but since we are saving the same
		# control id in multiple members also as an '_ifCtrlVal' item as well.	
		if 'flag' in dMap:
			dParams[ dSet['param'] ]['flags'][ dMap['flag'] ]['_inCtrlId'] = sCtrlId
			dParams[ dSet['param'] ]['flags'][ dMap['flag'] ]['_inIfCtrlVal'] = sVal
		elif 'flag' in dItem:
			dParams[ dSet['param'] ]['flags'][ dItem['flag'] ]['_inCtrlId'] = sCtrlId
		else:
			dParams[ dSet['param'] ]['_inCtrlId'] = sCtrlId
			dParams[ dSet['param'] ]['_inIfCtrlVal'] = sVal


	pout('</select>')
	
	
def _prnVarForm(sCtrlPre, dParams, sVarId, dVar):
	"""Output non-submittable HTML form controls for the configurable aspects
	of a variable and record the control IDs alongside the http get params
	they modify.

	Args:
		sCtrlPre: A prefix to add to all generated control IDs

		dParams:  The 'http_params' dictionary from the HttpStreamSrc catalog 
			object.  Control IDs will be inserted into parameter dictionaries
			under the key 'ctrl_id'.  Note that parameters with the type 'enum'
			or 'flag_set' will have 'ctrl_id' added into the individual flags
			or items.
		
		sVarId: The object id for this variable in the 'coordinates' or 'data'
			dictionaries

		dVar: The variable dictionary

	Returns:
		The number of non-sumbittable controls created.
	"""
	nCtrls = 0

	if 'title' in dVar:  sTitle = dVar['title']
	elif 'name' in dVar: sTitle = dVar['name']
	
	if 'name' in dVar: sName = dVar['name']
	else: sName = sVarId[0].upper() + sVarId[1:]
	
	# If this variable has text aspects, label them up front
	lAspects = ('minimum', 'maximum', 'resolution', 'interval')
	bLabelRow = False
	for sAspect in lAspects:
		if (sAspect in dVar) and ('set' in dVar[sAspect]):
			bLabelRow = True
			break

	if bLabelRow: pout("<p><b>%s: &nbsp;</b>"%sName)
	else: pout('<p>')
	
	# Right now I'm assuming the type of field for each aspect, should look
	# at the 'set' statement to get this info
	
	for i in range(len(lAspects)):
		sCtrlId = "%s_%s_%s"%(sCtrlPre, sVarId, lAspects[i])
		nCtrls += _inputVarTextAspect(dParams, dVar, lAspects[i], sCtrlId)

	if 'enabled' in dVar:
		sCtrlId = "%s_%s_enabled"%(sCtrlPre, sVarId)
		sMsg = "Enable <b>%s</b>"%sName
		if 'title' in dVar: sMsg = "%s - %s"%(sMsg, dVar['title'])
		_inputItemBoolean(dParams, dVar['enabled'], sMsg, sCtrlId)
		
	if 'units' in dVar:
		sCtrlId = "%s_%s_units"%(sCtrlPre, sVarId)
		_inputItemEnum(dParams, dVar['units'], "Set %s Units"%sName, sCtrlId)
	
	pout("</p>")

	return nCtrls

def prnOptGroupForm(sCtrlPre, dParams, sGroup, dGroup, sSrcUrl, bVar=False):
	"""Run through all the options in a group making output controls for each
	settable property

	Args:
		sCtrlPre (str): The prefix to assign to control IDs
		
		dParams (str): The 'http_params' dictionary
		
		sGroup (str): The name of the group
		
		dGroup (dict): The group dictionary
		
		bVar (bool): This group represents the options for a single coordinate or
			data variable.  Certian display options are enable for variable 
			groups, such a putting mix,max,resolution in a single line and looking
			around for units strings.
	"""
	nCtrls = 0
	
	lProps = list(dGroup.keys())
	lProps.sort()

	# Get the group name
	sGrpName = sGroup
	if 'name' in dGroup: sGrpName = dGroup['name']
	
	# Any option name can be used, but some are recognized as having particular 
	# meanings, especially in the context of a variable.  If this is a variable
	# make sure min,max,res,int are presented in that order.
	tOneLiner = ('minimum','maximum','resolution','interval')
	sGrpUnits = None
	if bVar:
		lFirst = []
		lRest = []
		for sKey in tOneLiner:
			if sKey in lProps: lFirst.append(sKey)
		for sKey in lFirst: lProps.remove(sKey)	
		lProps = lFirst + lProps
		
		if 'units' in lProps: sGrpUnits = dGroup['units']['value']
	
	# Weed out all the props that aren't settable
	lSettable = []
	for sProp in lProps:
		if 'set' in dGroup[sProp]: lSettable.append(sProp)
	lProps = lSettable

	for iProp in range(len(lProps)):
		sProp = lProps[iProp]
		dProp = dGroup[sProp]
		curval = None
		
		sPropUnits = None
		if 'units' in dProp: sPropUnits = dProp['units']
		elif sGrpUnits: sPropUnits = sGrpUnits
		
		# Note: The type of curval is unknown at this point
		if 'value' in dProp: curval = dProp['value']
		else:
			_missingKeyError('%s:%s:value'%(sGroup, sProp), sSrcUrl)
			return 0
		
		if 'set' not in dProp:
			#pout("%s: %s &nbsp"%(sProp, curval))
			continue
			
		# make a row prefix
		if not bVar:
			if iProp == 0: pout("<p>")
			else: pout("</p>\n<p>")
		else:
			if iProp == 0: pout("<p><b>%s: &nbsp;</b>"%sGrpName)
			
			# if this isn't a classical one-liner, start a new row 
			if sProp not in tOneLiner: pout("<br> &nbsp; ")
			
		dSet = dProp['set']
			
		if 'name' in dProp: sName = dProp['name']
		else: sName = sProp[0].upper() + sProp[1:]
			

		sCtrlId = "%s_%s_%s"%(sCtrlPre, sGroup, sProp)
		
		if 'flag' in dSet: sCtrlVal = dSet['flag']
		elif 'pval' in dSet: sCtrlVal = dSet['pval']
		else: sCtrlVal = "%s"%curval
		
		# There are three basic types of controls: 
		#
		#     check boxes, text boxes, select boxes.  
		# 
		# Determine what kind to make here.  Instances where there are only two
		# values that can be selected (the initial value, and the set) use
		# select boxes.
		
		sType = 'unk'
		if isinstance(curval, bool): sType = 'bool'
		elif 'enum' in dSet:  sType = 'select'
		elif 'value' in dSet: sType = 'select'
		else: sType = 'text'
		
		if sType == 'bool':
			sInfo = sProp
			if bVar and (sProp == "enabled"):
				sName = "Output"
				if 'title' in dGroup: sInfo = dGroup['title']
				elif 'name' in dGroup: sInfo = dGroup['name']
				else: sInfo = sGroup
			else:
				if 'title' in dProp: sInfo = dProp['title']
				elif 'name' in dProp: sInfo = dProp['name']
			
			sChecked = ""
			if curval == True: sChecked = "checked"
				
			pout('<input type="checkbox" id="%s" value="%s" %s><b>%s</b> - %s'%(
			     sCtrlId, sCtrlVal, sChecked, sName, sInfo)
			)
			
			# Save off the control information
			if 'flag' in dSet:
				dParams[ dSet['param'] ]['flags'][ dSet['flag'] ]['_inCtrlId'] = sCtrlId
			else:
				dParams[ dSet['param'] ]['_inCtrlId'] = sCtrlId
	
			
		elif sType == 'select':
			if 'title'  in dProp:  sMsg = dProp['title']
			elif 'name' in dProp: sMsg = dProp['name']
			else:                 sMsg = sProp[0].upper() + sProp[1:]
			
			if 'enum' in dSet:  # True enums... 
				_inputItemEnum(dParams, dProp, sMsg, sCtrlId)
				
			else:
				# Effective enum, binary choice
				pout(sMsg)
				pout('<select id=%s>'%sCtrlId)
				pout('  <option value="" selected>%s</option>'%curval)
				
				if 'pval' in dSet: sVal = dSet['pval']
				elif 'flag' in dSet: sVal = dSet['flag']
				else: sVal = dSet['value']
				
				pout('  <option value="%s">%s</option>'%(sVal, dSet['value']))
				pout('</select>')
				
				# Save off the control information, with an if check for the
				# select value
				if 'flag' in dSet:
					dParams[ dSet['param'] ]['flags'][ dSet['flag'] ]['_inCtrlId'] = sCtrlId
					dParams[ dSet['param'] ]['flags'][ dSet['flag'] ]['_inIfCtrlVal'] = sVal
				else:
					dParams[ dSet['param'] ]['_inCtrlId'] = sCtrlId
					dParams[ dSet['param'] ]['_inIfCtrlVal'] = sVal
								
		else:		
			if bVar:
				if sPropUnits: pout('%s (%s)'%(sName, sPropUnits))
				else: pout('%s '%sName)
			else:
				pout('<b>%s</b>: '%sName)
			
			
			if 'title' in dProp:
				pout('<label for="%s">%s</label>'%(sCtrlId, dProp['title']))
				
			if 'description' in dProp:
				lDesc = dProp['description'].split('\n')
				sDesc = '<br>\n'.join(lDesc)
				pout('<p>%s</p>'%sDesc)
				
			nSize = 8
			if sPropUnits and sPropUnits.lower() == 'utc': nSize = 16
			elif len(sCtrlVal) > 90: nSize = 75
			else: nSize = int( len(sCtrlVal)*0.7)
			
			sReq = ""
			if ('required' in dSet) and dSet['required']: sReq = 'required'
			
			pout('<input type="text" id="%s" size="%d" value="%s" %s>'%(
				sCtrlId, nSize, sCtrlVal, sReq))
			
			# Save off the control information
			if 'flag' in dSet:
				dParams[ dSet['param'] ]['flags'][ dSet['flag'] ]['_inCtrlId'] = sCtrlId
			else:
				dParams[ dSet['param'] ]['_inCtrlId'] = sCtrlId
			
		nCtrls += 1
		
	
	pout("</p>")
	
	return nCtrls


def _getAction(sBase):
	"""Get action from base url.  Basically return the URL with no GET params"""
	n = sBase.find('?')
	if n != -1: return sBase[:n]
	else: return sBase


def prnHttpSource(dSrc, bSubSec=False):
	""" Print an http source, this is complicated

	Handling input forms.
	
	This would be reativily straight forward, except we need form controls that
	generate partial get values.  (I'm looking at you das2 'params' and hapi
	'parameters'.)  To make life even *more* fun, sometimes servers screw up if
	an empty parameter is sent (I'm looking at you das2 'resolution' and hapi 
	'parameters').  So in addition we have to have a way to remove the 'name'
	attribute from parameters that otherwise would get kicked out the door.
	
	If these protocols (and others) were created in the spirit of HTML this
	wouldn't be needed, but alas, not everyone wants to make life easy for
	browser client developers, so here's the plan...
	
	Basic form handling works like this

	1. 'coordinates', 'data', and 'options' are parsed.  All controls are
	   generated without a name so they cannot be transmitted.
	
	2. All controls are generated with an ID, that has the form:
	  
	   basename(_path) + "_" + [coord|data|opt ] + "_" + [varID|optCat] + 
	                       "_" + [var_aspect|opt_setting ]
	
	   This insures all controls have a unique ID even if multiple http get
	   sources are combined into a single page.
	
	3. As each control is created it adds it's control ID to the relavent 
	   parameter in 'http_params'.  If the parameter is a FLAG_SET, or ENUM
	   then the control ID is added to the flag entry instead of the top level. 
	
	4. After all fake controls are generated, 'http_params' is parsed and all
	   'http_params' with a control ID attached are created as hidden text 
	   entry forms that are themselves fake (have no name).  The 
	   to-potentially-be-submitted controls are created with the following
	   ids:
	
     	basename(_path) + http_params name
	
	5. An onSubmit function and is generated for the form with the following 
	   name:
	
	     basename(_path) + "_OnSubmit"
	
	   and the http_parmas element is added as a variable.  When called 
	   onSubmit inspects the controls registered in 'http_params' and sets
	   new control values.  Finnally the output controls that have data 
	   values are given a name so that they can be submitted.
	"""
	
	sSrcUrl = dSrc['_url']

	if bSubSec:
		pout('<a href="%s">View this source only</a>'%catPathToBrowseUrl(dSrc['_path']))

	if 'tech_contacts' in dSrc:
		pout("<p>Technical problems using this data source should be "
		     "directed to: <b>")
		lTmp = [d['name'].strip() for d in dSrc['tech_contacts']]
		pout(", ".join(lTmp))
		pout("</b>.</p>")

	if 'protocol' not in dSrc:
		return _missingKeyError('protocol', sSrcUrl)
	else:
		dProto = dSrc['protocol']

	if 'authentication' in dProto:
		if _isTrue(dProto['authentication'], 'required'):
			pout('<p><i><span class="error">Resticted data source</span>.</i>')
			if 'REALM' in dProto['authentication']:
				 pout('You will be asked to authentication to the realm "' +\
				      '<b>%s</b>" on submit.</p>'%dProto['authentication']['realm'])
			else:
				pout("You will be asked to authentication on submit.</p>")

	# Print the examples
	if 'examples' in dProto:
		pout("<p>Example queries:")
		lExamples = list(dProto['examples'].keys())
		lExamples.sort()
		for sExample in lExamples:
			dExample = dProto['examples'][sExample]
			sTmp = sExample
			if 'name' in dExample:	sTmp = dExample['name']
			if 'title' in dExample: sTmp = dExample['title']
			pout('<a href="%s">%s</a> &nbsp;'%(dExample['url'], sTmp))
		pout("</p>")

	# Leave the form action blank, we'll set it depending on which submit
	# button is used.
	sBaseUri = bname(dSrc['_path'])
	sFormId = "%s_download"%sBaseUri
	pout('<form id="%s">'%sFormId)

	# Go through the base URLs see if they have any keys already set, if so
	# we'll need hidden form parameters to cover those as well
	if 'base_urls' not in dProto:
		return _missingKeyError('protocol:base_urls', dSrc['_url'])
	
	_setHidden(dProto['base_urls'])

	dParams = None
	if 'http_params' in dProto: dParams = dProto['http_params']
	nSettables = 0
	
	if 'interface' not in dSrc:
		return _missingKeyError('interface', dSrc['_url'])
	else:
		dIface = dSrc['interface']
	
	# Handle setting coord options, always do time first if it's present
	if dParams and ('coordinates' in dIface):
		# Find out if any coordinates provide subselect
		dCoords = dIface['coordinates']
		bSubSet = False
		bEnable = False
		lMod = []
		
		# Gather all settable coordinates
		for sCoord in dCoords:
			for sAspect in dCoords[sCoord]:
				if sAspect in ('name','title','description'): continue
				for sKey in dCoords[sCoord][sAspect]:
					if sKey.startswith('set'):
						if sCoord not in lMod: lMod.append(sCoord)
							
		# If the data are sub-settable by at least one property make the fieldset
		# indicate that
		if len(lMod) > 0:
			pout('<fieldset><legend><b>Coordinate Options:</b></legend>')
			
			sStyle = ''
			if len(lMod) > 12: sStyle = 'class="srcopts_scroll_div"'
			pout('<div %s>'%sStyle)

			lMod.sort()
			if 'time' in lMod:
				lMod.remove('time')
				lMod.sort()
				lMod = ['time'] + lMod
			for sCoord in lMod:
				# Function below writes control IDs into dParams
				nSettables += prnOptGroupForm(
					sBaseUri, dParams, sCoord, dCoords[sCoord], sSrcUrl, True
				)

			pout("</div>")
			pout('</fieldset>')
	
	# Handle setting data options.  There's no limit to these, but try to 
	# inteligently group them.  If a particular data var has a lot of 
	# options then group by data var.  Otherwise throw everything in one
	# group.
	
	if dParams and ('data' in dIface):
		dData = dIface['data']
		bEnable = False
		bUnits = False
		lMod = []
		
		# See if the any of the data items have settable parameters
		nDatOpts = 0
		lModVars = []
		for sVar in dData:
			for sAspect in dData[sVar]:
				for sKey in dData[sVar][sAspect]:
					if sKey.startswith('set'):
						if sVar not in lModVars: lModVars.append(sVar)
						nDatOpts += 1
						break
				
		if nDatOpts > 0:
			pout('<fieldset><legend><b>Data Options:</b></legend>')
			
			sStyle = ''
			if nDatOpts > 12: sStyle = 'class="srcopts_scroll_div"'
			pout('<div %s>'%sStyle)
			
			lModVars.sort()
			for sVar in lModVars:
				nSettables += prnOptGroupForm(
					sBaseUri, dParams, sVar, dData[sVar], sSrcUrl, True
				)

			pout("</div>")
			pout("</fieldset>")

		
		#for sData in dData:
		#	for sAspect in ('units','enabled'):
		#		if sAspect in dData[sData]:
		#			for sKey in dData[sData][sAspect]:
		#				if sKey.startswith('set'):
		#					if sAspect == 'enabled':	bEnable = True
		#					else: bUnits = True
		#					if sData not in lMod: lMod.append(sData)
		#			
		#if bEnable or bUnits:
		#
		#	if bEnable:
		#		pout('<fieldset><legend><b>Toggle Data Output:</b></legend>')
		#	else:
		#		pout('<fieldset><legend><b>Set Data Units:</b></legend>')
		#	
		#	sStyle = ''
		#	if len(lMod) > 12: sStyle = 'class="srcopts_scroll_div"'
		#	pout('<div %s>'%sStyle)
		#
		#	# Probably need to return id's to use in javascript here
		#	lMod.sort()
		#	for sData in lMod:
		#		nSettables += _prnVarForm(sBaseUri, dParams, sData, dData[sData])
		#		
		#	pout("</div>")
		#	pout("</fieldset>")
	
	# Handle setting general options
	if dParams and ('options' in dIface):
		dOptions = dIface['options']

		lOptions = list(dOptions.keys())
		
		lMod = []
		for sProperty in lOptions:
			if 'set' in dOptions[sProperty]:
				if sProperty not in lMod: lMod.append(sProperty)

		if len(lMod) > 0:				
			pout("<fieldset><legend><b>Additional Options:</b></legend>")
				
			nSettables += prnOptGroupForm(
				sBaseUri, dParams, 'options', dOptions, sSrcUrl
			)
	
			pout("</fieldset>")

	# Stage 4, inspect http_params and output hidden controls with no name.
	if dParams and (nSettables > 0):
		nSettables = 0
		for sParam in dParams:
			dParam = dParams[sParam]
			if 'type' not in dParam: continue

			bOut = False
			if dParam['type'] == 'flag_set':
				if 'flags' not in dParam: continue
				
				for sFlag in dParam['flags']:
					dFlag = dParam['flags'][sFlag]
					if '_inCtrlId' in dFlag:
						bOut = True
						break
			elif dParam['type'] == 'enum':
				if 'items' not in dParam: continue
				
				for sItem in dParam['items']:
					dItem = dParam['items'][sItem]
					if '_inCtrlId' in dItem:
						bOut = True
						break
			else:
				if '_inCtrlId' in dParam: bOut = True

			if bOut:
				sCtrlId = "%s_%s"%(sBaseUri, sParam)
				pout('<input type="hidden" id="%s">'%sCtrlId)
				dParam['_outCtrlId'] = sCtrlId


		# Stage 5, write the javascript that will be used on submit
		sFuncName = "%s_onSubmit"%sBaseUri
		sJson = json.dumps(dParams, ensure_ascii=False, indent=2, sort_keys=True)
		sNamePrefix = "%s_"%sBaseUri
		pout("""
<script>
function %s(sActionUrl) {
	var dParams = %s;
	
	// Strip this from outgoing control id's, to get the output control
	// name.  It was added to keep out controls from different forms separate.
	var sNamePre = "%s";

	for(var sParam in dParams){
		dParam = dParams[sParam]
		
		if(!("_outCtrlId" in dParam)) continue;
		var ctrlOut = document.getElementById(dParam["_outCtrlId"]);
		var sOutName = dParam["_outCtrlId"].replace(sNamePre, "");
		
		// Flagset parameters, the most complicated ones
		if( ('type' in dParam) && (dParam['type'] == 'flag_set')){
		
			if( !('flags' in dParam) ) continue;
			
			var dFlags = dParams[sParam]['flags'];
			var sOutVal = "";
			var sOutSep = " ";
			if( 'flag_sep' in dParam) sOutSep = dParam['flag_sep'];
			
			for(var sFlag in dFlags){
				var dFlag = dFlags[sFlag];
				if( !('_inCtrlId' in dFlag) ) continue;
				
				var ctrlIn = document.getElementById(dFlag["_inCtrlId"]);
				
				// Check to see if we only add the output flag when the input
				// has a certian value
				if( '_inIfCtrlVal' in dFlag ){
					if(ctrlIn.type == 'checkbox'){
					
						// If the state of the checkbox matches the send state then add the
						// parameter.  This might mean than NOT checked sends a value.
						if(dFlag['_inIfCtrlVal'] ==  ctrlIn.checked){
							if((sOutSep.length > 0)&&(sOutVal.length > 0)) sOutVal += sOutSep;
							sOutVal += dFlag['value'];
						}
					}
					else{
						if( ctrlIn.value == dFlag['_inIfCtrlVal']){
							if((sOutSep.length > 0)&&(sOutVal.length > 0)) sOutVal += sOutSep;
							sOutVal += dFlag['value'];
						}
					}
				}
				else{
					// So the input sets the whole flag only set the output if something
					// has changed.
					if(ctrlIn.type == 'checkbox'){
						if( ctrlIn.checked == true){
							if((sOutSep.length > 0)&&(sOutVal.length > 0)) sOutVal += sOutSep;
							if('prefix' in dFlag) sOutVal += dFlag['prefix'];
							sOutVal += dFlag['value'];
						}
					}
					else{
						if( ctrlIn.value.length > 0){
							if((sOutSep.length > 0)&&(sOutVal.length > 0)) sOutVal += sOutSep;
							if('prefix' in dFlag) sOutVal += dFlag['prefix'];
							sOutVal += ctrlIn.value;					
						} 
					}
				}
			}
			
			// Set control name and value if value changed
			if(sOutVal.length > 0){
				ctrlOut.name = sOutName;
				ctrlOut.value = sOutVal;
			}
		}
		
		// TODO: Enum parameters
		//else if ('type' in dParam) and (dParam['type'] == 'enum')){
		//
		//
		//
		//}
		
		// Generic parameters
		else {
			
			if(!("_inCtrlId" in dParam)) continue;
			var ctrlIn = document.getElementById(dParam["_inCtrlId"]);
			
			// Check boxes...
			if(ctrlIn.getAttribute("type") == "checkbox"){
				if(ctrlIn.checked == true){
					// Text fields
					ctrlOut.value = ctrlIn.value;
					ctrlOut.name = sOutName;
				}
			} 
			else {
				if(ctrlIn.value.length > 0){
					// Text fields
					ctrlOut.value = ctrlIn.value;
					ctrlOut.name = sOutName;
				}
			}
		}
	}

	document.getElementById("%s").action = sActionUrl;
}
</script>
	"""%(sFuncName, sJson, sNamePrefix, sFormId))

		# Make one submit function per base url
		if ('format' in dSrc) and ('default' in dSrc['format']) and \
		   ('mime' in dSrc['format']['default']):
			sMime = dSrc['format']['default']['mime']
			pout("<p>Output will be <tt>%s</tt> unless changed via format options</p>"%(sMime))
			
		for sBase in dProto['base_urls']:
			pout('<input type="submit" value="Get from %s"'%_hostSimpleName(sBase) +\
		     	' onclick=\'%s("%s");\'>'%(sFuncName, _getAction(sBase) ))

	pout('</form>')

	pout('<div class="identifers">')
	pout('<br><br>Catalog Path: %s &nbsp; <br>Read From: &nbsp; <a href="%s">%s</a></a>'%(
	     dSrc['_path'], dSrc['_url'], dSrc['_url']))
	
	if 'uris' in dSrc and len(dSrc['uris']) > 0:
		pout('<br>Permanent IDs:')
		dSrc['uris'].sort()
		for sUri in dSrc['uris']: pout(" &nbsp; <i>%s</i>"%sUri)
	
	pout('</div>')	
		  
	pout('<hr class="datasrc_sep">')


#############################################################################
def prnFileAgg(dNode):
	pout("<h2>I'm a file aggregation</h2>")
	pout("<pre>")
	sOut = json.dumps(dNode, ensure_ascii=False, indent="  ", sort_keys=True)
	pout(sOut)
	pout("</pre>")



#############################################################################

g_lSrcOrder = ['das2/2.3', 'das2/2.2', 'votable', 'hapi']

def _srcSortKeyFunc(dSrc):
	if 'convention' in dSrc:
		for i in range(len(g_lSrcOrder)):
			if dSrc['convention'].lower().startswith(g_lSrcOrder[i]):
				return i
	return len(g_lSrcOrder)

def prnCollection(dNode):

	if 'title' in dNode:
		pout("<h3>Collection: %s</h3>"%dNode['title'])

	if 'description' in dNode:
		pout("<p>%s<br><br></p>"%dNode['description'])
		
	if 'usage' in dNode:
		pout("<p>\n")
		if 'policy' in dNode['usage']:
			pout('Usage Policy: <b class="error">%s</b> <br>'%dNode['usage']['policy'])
		if 'extern' in dNode['usage']:
			pout('Please read <a href="%s">%s<a> before using these data.\n'%(
			     dNode['usage']['extern'], dNode['usage']['extern']))
		pout("</p>\n")

	if 'sci_contacts' in dNode:
		pout("<p>Questions about the nature and usefulness of this data set "
		     "should be directed to: <b>")
		lTmp = [d['name'].strip() for d in dNode['sci_contacts']]
		pout(", ".join(lTmp))
		pout("</b>.</p>")

	
	if 'coordinates' in dNode:
		pout("<p>Coordinates for these data include:")

		sStyle = "indent30_div"
		if len(dNode['coordinates']) > 12: sStyle = "indent30_scroll_div"

		pout('<div class="%s">'%sStyle)
		
		lCoords = list(dNode['coordinates'].keys())
		#Make sure time is first
		if 'time' in lCoords:
			lCoords.remove('time')
			lCoords.sort()
			lCoords = ['time'] + lCoords
		
		for sCoord in lCoords:
			dCoord = dNode['coordinates'][sCoord]
			if 'name' in dCoord:
				sOut = "<b>%s</b>"%dCoord['name']
			else:
				sOut = "<b>%s</b>"%sCoord

			if 'units' in dCoord: sOut += " (%s)"%dCoord['units']
			if ('valid_min' in dCoord) and dCoord['valid_min']:
				sOut += " from <b>%s</b>"%dCoord['valid_min']
			if ('valid_max' in dCoord) and dCoord['valid_max']:
				if ('valid_min' in dCoord) and dCoord['valid_min']:
					sOut += " to "
				else:
					sOut += "up to "
				sOut += "<b>%s</b>"%dCoord['valid_max']

			if 'title' in dCoord:
				sOut += " - %s"%dCoord['title']

			pout("%s<br>"%sOut)
		pout('</div></p>')

	if 'data' in dNode:
		pout("<p>Data items in this collection include:")
		sStyle = "indent30_div"
		if len(dNode['data']) > 12: sStyle = "indent30_scroll_div"
		pout('<div class="%s">'%sStyle)

		lData = list(dNode['data'].keys())
		lData.sort()
		for sData in lData:
			dData = dNode['data'][sData]
			if 'name' in dData:
				sOut = "<b>%s</b>"%dData['name']
			else:
				sOut = "<b>%s</b>"%sData
			if 'units' in dData: sOut += " (%s)"%dData['units']
			if ('minimum' in dData) and dData['minimum']:
				sOut += " from <b>%s</b>"%dData['minimum']
			if ('maximum' in dData) and dData['maximum']:
				if ('minimum' in dData) and dData['minimum']:
					sOut += " to "
				else:
					sOut += "up to "
				sOut += "<b>%s</b>"%dData['maximum']

			if 'title' in dData:
				sOut += " - %s"%dData['title']

			pout("%s<br>"%sOut)
		pout('</div></p>')

	if 'EPNcore' in dNode:
		pout('<h4 class="obscore"> EPN-Core Metadata</h3>')
		pout('<p class="obscore">')
		l = list(dNode['EPNcore'].keys())
		l.sort()
		for s in l:
			pout('<span class="obscore">%s:&nbsp;<b>%s</b></span> &nbsp; &nbsp; &nbsp; '%(
			     s, dNode['EPNcore'][s]))
		pout('</p>')


	dSubs = getDirectSubs(dNode, "sources")

	if len(dSubs) == 0:
		pout("<p>Unfortunately, no sources are listed for this data collection</p>")
		return

	# Provide access source methods, in the following order:
	#   HttpStreamSrc:
	#     das2/2.3 das2/2.2, votables, hapi, das1 then anything else
	#   FileAggreation:

	lSrcs = []
	for sSrc in dSubs: lSrcs.append(dSubs[sSrc])
	lSrcs.sort(key=_srcSortKeyFunc)

	for dSrc in lSrcs:
		sTmp = dSrc['type']
		if 'convention' in dSrc: sTmp = dSrc['convention']
		elif 'name' in dSrc: sTmp = dSrc['name']

		pout('<div class="datasrc_div">')
		pout("<h3><span>Access via %s</span></h3>"%sTmp)

		if dSrc['type'] == 'HttpStreamSrc':
			prnHttpSource(dSrc, True)
		elif dSrc['type'] == 'FileAggregation':
			prnFileAgg(dSrc)
		else:
			pout("""
<p>Data source type <b>%s</b> is unknown.  If this is a useful source type and
not just a catalog error contact the maintainer of this das2 catalog browse
client to request an upgrade.</p>
"""%dSrc['type'] )
		pout("</div>")

	
	pout('<div class="identifers">')
	sResolve = "%s?resolve=%s"%(scriptUrl(), dNode['_path'])
	pout('<br><br>Catalog Path: <i><a href="%s">%s</a></i> &nbsp; <br>Read From: <a href="%s">%s</a></a>'%(
	     sResolve, dNode['_path'], dNode['_url'], dNode['_url']))
	pout('</div>')
	
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
	pout('''
<div class="footer">
  <div>More information about das2 can be found at:
  <a href="http://das2.org/">http://das2.org/</a>.</div>
  <div>%s</div>
  <div><a href="https://saturn.physics.uiowa.edu/svn/das2/clients/devel/browse">
  Download the code for this catalog client</a></div>
</div>'''%os.getenv('SERVER_SIGNATURE')
	)
	pout("</body>\n</html>")

#############################################################################
# Main

def main(form):

	sScript = scriptUrl()
	if sScript.startswith("https"):
		sProto = "https"
	else:
		sProto = "http"

	sTree = g_sTree[0].upper() + g_sTree[1:]

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
'''%(scriptUrl(), sProto, g_sLogo, sTree))

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


	# What ID do they want to know about, can be given as a query id or as
	# path info, or just a direct URL that skips the whole resolution stage
	sPath = form.getfirst('resolve', '').strip()
	sPath = sPath.lower()

	if len(sPath) > 0:
		# We can get direct urls via the resolver, so check for that
		if sPath.startswith('http'):
			(dNode, lPathTo, lTried) = getNode(sPath)

			if dNode != None:
				sPath = dNode['_path']
			else:
				sPath = None
		else:
			if not sPath.startswith('tag:'):
				sPath = "%s:/%s"%(g_sDefDas2SiteTag, sPath)

			(dNode, lPathTo, lTried) = getNode(sPath)
	else:
		sPathInfo = ''
		if os.getenv("PATH_INFO"):
			sPathInfo = os.getenv("PATH_INFO")
		sPath = pathInfoToCatId(sPathInfo)

		(dNode, lPathTo, lTried) = getNode(sPath)


	pout('''
<form action="%s" >
<div class="resolver">
  <label for="resolve_text">Catalog Path or URL</label>
  <input type="text" id="resolve_text" name="resolve" value="%s" autofocus>
  <input type="submit" value="Resolve" >
</div>
</form>
'''%(scriptUrl(), sPath))

	pout('<div class="main">')

	if dNode == None:
		pout("<p>Catalog node <b>%s</b> doesn't exist</p>"%sPath)
		pout("<p>Lookup path follows:</p>\n<ul>")

		for i in range(0, len(lTried)):
			sUrl = lTried[i]
			if i == (len(lTried) - 1):
				pout('<li><a href="%s">%s</a> &lt;-- trail ends here</li>'%(sUrl, sUrl))
			else:
				pout('<li><a href="%s">%s</a></li>'%(sUrl, sUrl))

		pout("</ul>")
		pout("</div>")
		prnFooter()
		return 13

	prnBrowseBar(lPathTo, dNode)

	if dNode['type'] == 'Catalog':
		prnCatalog(dNode)
	elif dNode['type'] == 'Collection':
		prnCollection(dNode)
	elif dNode['type'] == 'HttpStreamSrc':
		prnHttpSource(dNode)
	else:
		pout("<h2>Unknown node type %s</h2>"%dNode['type'])
		pout("<p>Raw catalog entry displayed below</p>")
		pout("<pre>")
		sOut = json.dumps(dNode, ensure_ascii=False, indent="  ", sort_keys=True)
		pout(sOut)
		pout("</pre>")

	pout("</div>")

	prnCodeScript()

	prnFooter()

	return 0

##############################################################################
# Stub main for cgi

form = cgi.FieldStorage()

# Return values don't matter in CGI programming.  That's unfortunate
main(form)
