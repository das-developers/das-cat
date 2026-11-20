#! /usr/bin/env python3

""" Access a remote das2 server and read it's dsdf info and make catalog
entries.
"""

import sys
import os
import os.path
from os.path import join as pjoin
from os.path import basename as bname
from os.path import dirname as dname

import json
import argparse
import gettext
import logging
import requests
import re
import hashlib

# Modules that moved from python2 to python3
try:
	from urllib import quote_plus
	from HTMLParser import HTMLParser
except ImportError:
	from urllib.parse import quote_plus
	from html.parser import HTMLParser


import das2  # Don't want to add a non-standard dependency but the DasTime
             # class saves a lot of work in determining default resolutions
				 # for 

##############################################################################
# DSDF keys to convert to obscore blocks if found

g_lObsCoreCollection = [
	'dataproduct_type', 'measurement_type', 'processing_level',
	'target_name','target_class','target_region','feature_name'
]

# Translations for various obscore names to official names
g_lObsCoreCollectionTrans = {
	'dataproductType':'dataproduct_type',
	'measurementType':'measurement_type',
	'targetClass':'target_class',
	'targetName':'target_name',
	'targetRegion':'target_region',
	'featureName':'feature_name'
}

g_lObsCoreSource = [
	'time_min','time_max', 'time_sampling_step_min',
	'spectral_sampling_step_max','spectral_resolution_min',
	'spectral_resolution_max'
]

g_lObsCoreSourceTrans = {

}

##############################################################################
g_lRmDirs = [] # Global list of directories to cleanup after a no-op


##############################################################################
# This is used so much, just give it a variable
sV="value"
sT="title"

##############################################################################
# A generic version reporting block

def stripSVNkey(s):
	if s.find(':') == -1:
		return s.strip(" $") + ": unknown"
	else:
		return s.strip(' $')

g_sRev = stripSVNkey("$Rev: 10041 $")
g_sURL = stripSVNkey("$URL: https://saturn.physics.uiowa.edu/svn/das2/clients/devel/libdas2client/scripts/das2_lookup.py $")
g_sWho = stripSVNkey("$LastChangedBy: cwp $")
g_sWhen = stripSVNkey("$LastChangedDate: 2017-08-28 00:57:28 -0500 (Mon, 28 Aug 2017) $")



##############################################################################
def setupLogger(sLogLevel, sName, sFile=None):
	"""Utility to setup standard python logger.
	sLogLevel - Logging level, starts with one of: C,c,E,e,W,w,I,i,D,d
	           [critical,error,warning,info,debug]
	"""
	sLevel = sLogLevel.lower()
	nLevel = logging.WARNING

	sDateFmt = '%Y-%m-%d %H:%M:%S'
	sFileFmt = '%(asctime)s %(levelname)-8s: %(message)s'
	sConFmt = '%(levelname)-8s: %(message)s'

	if sLevel.startswith("c"):
		nLevel = logging.CRITICAL
	elif sLevel.startswith("e"):
		nLevel = logging.ERROR
	elif sLevel.startswith("i"):
		nLevel = logging.INFO
	elif sLevel.startswith("d"):
		nLevel = logging.DEBUG
		sFileFmt = '%(asctime)s %(name)-12s %(levelname)-8s: %(message)s'
		sConFmt = '%(name)-12s %(levelname)-8s: %(message)s'

	#Logging options:  Console,File|File|Console|None(acually console force crit)
	logger = logging.getLogger(sName)
	logger.setLevel(nLevel)

	conHdlr = logging.StreamHandler(sys.stderr)
	formatter = logging.Formatter(sConFmt, sDateFmt)
	conHdlr.setFormatter(formatter)
	logger.addHandler(conHdlr)

	return logger

##############################################################################

def _atOrUnder(lTestPath, lTargPath):
	"""Does the front part of the lTestPath match the lTargPath"""

	# Test is too short to be at or under target
	if len(lTestPath) < len(lTargPath): return False

	for i in range(0, len(lTargPath)):
		if lTestPath[i] != lTargPath[i]:
			return False

	return True


def _leadsTo(lTestPath, lTargPath):
	"""Does the test path lead to the target path, any empty test path is
	assumed to lead to everything """

	# /a/b  (targ)

	# /     (test: true)
	# /a    (test: true)
	# /a/b  (test: false)

	if len(lTestPath) >= len(lTargPath): return False

	for i in range(0, len(lTestPath)):
		if lTestPath[i] != lTargPath[i]:
			return False

	return True

def _getDict(d, key):
	if key not in d: d[key] = {}
	return d[key]

def _getList(d, key):
	if key not in d: d[key] = []
	return d[key]
	
def _isTrue(d, key):
	if key not in d: return False
	if d[key].lower() in ('true','1','yes'):
		return True
	return False

def _isPropTrue(dProps, key):
	if key not in dProps: return False
	
	dSub = dProps[key]
	if '00' not in dSub: return False
	
	if dSub['00'].lower() in ('true','1','yes'):
		return True
	
	return False

##############################################################################
def parseDas22SrcProps(log, sUrl, sStr):
	"""Find and parse the big <properites> element into a more useful data
	structure.  Returns None if fails.
	"""

	iStart = sStr.find('<properties')
	if iStart == -1:
		log.error("Couldn't find start of stream properties from '%s'"%sUrl)
		return None

	iEnd = sStr.rfind(' />')
	if iEnd == -1:
		log.error("Couldn't find end of stream properties from '%s'"%sUrl)
		return None

	sProps = sStr[iStart + len('<properties') : iEnd].strip()

	# tokenize the input
	h = HTMLParser()
	lPairs = []
	for t in re.findall(r'([a-zA-Z][0-9a-zA-Z_]+)(\s*=\s*)(".*?")', sProps):
		sKey = t[0]
		sVal = t[2].strip('"').strip()
		sVal = h.unescape(sVal)
		sVal = sVal.strip('"').strip()
		lPairs.append((sKey, sVal))


	# gather like values into dictionaries
	dProps = {}

	for t in lPairs:

		sKey = t[0]
		sSubKey = '00'

		n = t[0].find('_')
		if n != -1:
			sKey = t[0][:n]

			sSubKey = t[0][n+1:]

			if (not sSubKey.isdigit()) or (len(sSubKey) != 2):
				#Actual _ not list item separater, set the key
				# back the way it was
				sKey = t[0]
			else:
				sSubKey = "%02d"% int(t[0][n+1:], 10)

		elif t[0][-2:].isdigit():
			sKey = t[0][:-2]
			sSubKey = t[0][-2:]


		if sKey not in dProps:
			dProps[sKey] = {}

		dProps[sKey][sSubKey] = t[1]


	return dProps
	
##############################################################################
def _dumpProps(dProps):
	lProps = list(dProps.keys())
	lProps.sort()
	
	for sProp in dProps:
		print(sProp)
		lItems = list(dProps[sProp].keys())
		lItems.sort()
		
		for sItem in lItems:
			print("  +- %s : %s"%(sItem, dProps[sProp][sItem]))
			

##############################################################################
def arrangeNodes(log, lNodes):
	"""Given a list of nodes output hierarchical dictionary.
	Return value is just the top node
	"""

	if len(lNodes) == 0:
		return None

	# Get the longest and shortest path
	nShortest = 65000
	nLongest = -1
	for dNode in lNodes:
		#print(">>> ", len(dNode['_srvPath']), dNode['_srvPath'])
		
		nLen = len(dNode['_srvPath'])
		if nLen < nShortest: nShortest = nLen
		if nLen > nLongest: nLongest = nLen


	# Tail collapse
	for n in range(nLongest, nShortest, -1):
		lParents = []
		lChildren = []
				
		# Split short and long nodes
		for dNode in lNodes:
			if len(dNode['_srvPath']) == n: lChildren.append(dNode)
			else: lParents.append(dNode)

		#print("----------------------------")
		#print("   lParents:")
		#for d in lParents:  print("      %s"%d['path'])
		#print("   lChildren:")
		#for d in lChildren: print("      %s"%d['path'])
		#print("----------------------------")s


		# Give all the child nodes new homes
		for dChild in lChildren:

			lParPath = dChild['_srvPath'][:-1]

			bMoved = False
			for dParent in lParents:
				if dParent['_srvPath'] == lParPath:

					#sRm = 'tag:das2.org,2012:'

					#print("%s found it's mommy %s"%(
					#	dChild['path'].replace(sRm, ""),
					#	dParent['path'].replace(sRm, ""))
					#)
					if 'subnodes' not in dParent:
						dParent['subnodes'] = {}
					dParent['subnodes'][ dChild['_srvPath'][-1] ] = dChild
					bMoved = True

			if not bMoved:
				log.error("Couldn't find parent for node %s"%dChild['_srvPath'])
				log.error("   lParents:")
				for d in lParents:  log.error("      %s"%d['path'])
				log.error("   lChildren:")
				for d in lChildren: log.error("      %s"%d['path'])
				return None
				

		# Now collapse next level up
		lNodes = lParents


	# The length of lNodes should be 1
	if len(lNodes) != 1:
		log.error("Multiple top-level nodes!")
		return None

	return lNodes[0]

##############################################################################
def writeObj(log, dOut, sFile, bNoOp):
	global g_lRmDirs
	
	# Keep a list of directories we need to delete if this is a no-op
	if not os.path.isdir(dname(sFile)):
		bAbs = (sFile[0] == '/')
		
		lPath = dname(sFile).split('/')
		if bAbs: lPath = lPath[1:]
		
		for i in range(len(lPath)):
			sDir = '/'.join(lPath[:i+1])   # Fails on Windows ??
			if bAbs: sDir = '/'+sDir
			
			if not os.path.isdir(sDir):
				#log.info("Creating directory %s for file %s"%(sDir, sFile))
				os.mkdir(sDir)
	
				if bNoOp: g_lRmDirs.append(sDir)
				

	sOut = json.dumps(dOut, ensure_ascii=False, indent=3, sort_keys=True)
	fOut = open("%s.tmp"%sFile, 'w')
	fOut.write(sOut)

	# Do hash comparison
	hasher = hashlib.md5()
	sOldHash = None
	if os.path.isfile(sFile):
		f = open(sFile, "rb")
		for chunk in iter(lambda: f.read(4096), b""): hasher.update(chunk)
		sOldHash = hasher.hexdigest()
		f.close()
	
	hasher = hashlib.md5()
	f = open("%s.tmp"%sFile, "rb")
	for chunk in iter(lambda: f.read(4096), b""): hasher.update(chunk)
	sNewHash = hasher.hexdigest()
	f.close()
	
	if bNoOp:
		if sNewHash != sOldHash:
			log.info("Would have updated '%s'"%sFile)
		
		os.remove("%s.tmp"%sFile)
	else:
		if sNewHash != sOldHash:
			log.info("Updating %s"%sFile)
			os.rename("%s.tmp"%sFile, sFile)
		else:
			log.info("No updates required for %s"%sFile)
			os.remove("%s.tmp"%sFile)
		
	
	return True

##############################################################################
def _mergeSciContacts(dOut, dProps):
	"""Dsdfs list sci contacts using the following format:
	
	name <email>[ , NEXT_NAME, <NEXT_EMAIL> ] ...
	
	Reformat this into a list of  { 'name', 'EMAIL'} and add to 'SCI_CONTACT'
	"""
	lOut = _getList(dOut, 'sci_contacts')
	
	if 'sciContact' not in dProps: return
	
	lContacts = [ s.strip() for s in dProps['sciContact']['00'].split(',') ]
	
	for sContact in lContacts:
		iTmp = sContact.find('<')
		sWho = sContact
		if iTmp != -1:
			sWho = sContact[:iTmp].strip()
			sEmail = sContact[iTmp + 1:-1].strip()
			if len(sEmail) < 1: sEmail = None
			dContact = {'name':sWho, 'email':sEmail}
		else:
			dContact = {'name':sWho}
		
		if dContact not in lOut: lOut.append( dContact )
	
def _mergeTechContacts(dOut, dProps):
	lOut = _getList(dOut, 'tech_contacts')
	
	if 'techContact' not in dProps: return
	
	lContacts = [ s.strip() for s in dProps['techContact']['00'].split(',') ]
	
	for sContact in lContacts:
		iTmp = sContact.find('<')
		sWho = sContact
		if iTmp != -1:
			sWho = sContact[:iTmp].strip()
			sEmail = sContact[iTmp + 1:-1].strip()
			if len(sEmail) < 1: sEmail = None
			dContact = {'name':sWho, 'email':sEmail} 
		elif len(sWho) > 0:
			dContact = {'name':sWho} 
	
		if dContact not in lOut: lOut.append( dContact )
	

def _mergeColCoordInfo(dOut, dProps):
	dCoords = _getDict(dOut, 'coordinates')
	
	# By default das2/2.2 servers only know that there is a time coordinate
	# so set that one up.  
	dTime = _getDict(dCoords, 'time')
	
	if 'name' not in dTime: dTime['name']  = 'Time'
		
	if 'validRange' in dProps:
		lRng = [ s.strip() for s in dProps['validRange']['00'].split('to') ]
		if len(lRng) > 1:
			dTime['valid_min'] = lRng[0]
			dTime['valid_max'] = lRng[1]

				
	# See if any other coordinates are mentioned, if so give them a 
	# token entry assume the values are 'name','description','units'
	if 'coord' in dProps:
		for sNum in dProps['coord']:
			lItem = [s.strip() for s in dProps['coord'][sNum].split('|')]
			if lItem[0].lower() == 'time':
				if len(lItem) > 1:  dTime['title'] = lItem[1]
			else:
				dVar = _getDict(dCoords, lItem[0])
				dVar['name'] = lItem[0][0].upper() + lItem[0][1:]
				if len(lItem) > 1: dVar['title'] = lItem[1]
				if len(lItem) > 2: dVar['units'] = lItem[2]
	

def _mergeSrcCoordInfo(dOut, dProps):
	"""Add COORDs info to the output dictionary.  There are two styles,
	complete - used for actual HttpStreamSrc entries
	overview - used for collection entries
	"""
	dIface  = _getDict(dOut, 'interface')
	dCoords = _getDict(dIface, 'coordinates')
	
	# By default das2/2.2 servers only know that there is a time coordinate
	# so set that one up.  
	dTime = _getDict(dCoords, 'time')
	
	if 'name' not in dTime: dTime['name']  = 'Time'

	# Use the lowest numbered example for the default range, interval
	dTime['minimum'] = {sV:None}
	dTime['maximum'] = {sV:None}
	
	dTime['units'] = {'value':'UTC'}
		
	if 'requiresInterval' in dProps:
		dTime['interval'] = {sV:None}
	else:
		dTime['resolution'] = {sV:None, "units":"s"}
	
	sNum = None
	if 'exampleRange' in dProps:
		lNums = list(dProps['exampleRange'].keys())
		lNums.sort()
		sNum = lNums[0]
	
		lTmp = [s.strip() for s in dProps['exampleRange'][sNum].split('|')]
		lTmp = [s.strip() for s in lTmp[0].split('to')]
		dTime['minimum'][sV] = lTmp[0]		
		if len(lTmp) > 1:
			dTime['maximum'][sV] = lTmp[1].replace('UTC','').strip()
	
	if 'exampleInterval' in dProps:
		lNums = list(dProps['exampleRange'].keys())
		if not sNum or (not (sNum in lNums)):
			lNums.sort()
			sNum = lNums[0]
		if 'interval' not in dTime:
			print("Error updating from %s"%dOut['path'])
			
		dTime['interval'][sV] = dProps['exampleInterval'][sNum]
	else:	
		# Default to 1/2000th of the range, here's where we need the
		# das2 module.
		if dTime['minimum'][sV] and dTime['maximum'][sV]:
			dtBeg = das2.DasTime(dTime['minimum'][sV])
			dtEnd = das2.DasTime(dTime['maximum'][sV])
			dTime['resolution'][sV] = (dtEnd - dtBeg) / 2000.0
				
	# Set up the alteration rules
	dTime['minimum']['set'] = {'param':'start_time', 'required':True}
	dTime['maximum']['set'] = {'param':'end_time', 'required':True}
	
	if 'validRange' in dProps:
		lTimeRng = [ s.strip() for s in dProps['validRange']['00'].split('to') ]
		if len(lTimeRng) > 1:
			dTime['minimum']['set']['range'] = lTimeRng
			dTime['maximum']['set']['range'] = lTimeRng
	
	if 'interval' in dTime:
		dTime['interval']['set'] = {'param':'interval', 'required':True}
	else:
		dTime['resolution']['set'] = {'param':'resolution', 'required':False}
		
	
	# See if any other coordinates are mentioned, if so give them a 
	# token entry assume the values are 'name','description','units'
	if 'coord' in dProps:
		for sNum in dProps['coord']:
			lItem = [s.strip() for s in dProps['coord'][sNum].split('|')]
			if lItem[0].lower() == 'time':
				if len(lItem) > 1:  dTime['title'] = lItem[1]
			else:
				dVar = _getDict(dCoords, lItem[0])
				dVar['name'] = lItem[0][0].upper() + lItem[0][1:]
				if len(lItem) > 1: dVar['title'] = lItem[1]
				if len(lItem) > 2: dVar['units'] = {'value':lItem[2]}


def _mergeColDataInfo(dOut, dProps):

	if ('item' not in dProps) and ('data' not in dProps): return
	
	# Make minimal entries for the data items
	dData = _getDict(dOut, 'data')
	if 'item' in dProps:
		for sNum in dProps['item']:
			lItem = [s.strip() for s in dProps['item'][sNum].split('|')]
			
			dVar = _getDict(dData, lItem[0])
			dVar['name'] = lItem[0][0].upper() + lItem[0][1:]
			if len(lItem) > 1: dVar['title'] = lItem[1]
			if len(lItem) > 2: dVar['units'] = {'value':lItem[2]}
		
	if 'data' in dProps:
		for sNum in dProps['data']:
			lItem = [s.strip() for s in dProps['data'][sNum].split('|')]
		
			dVar = _getDict(dData, lItem[0])
			dVar['name'] = lItem[0][0].upper() + lItem[0][1:]
			if len(lItem) > 1: dVar['title'] = lItem[1]
			if len(lItem) > 2: dVar['units'] = {'value':lItem[2]}
	

def _mergeSrcDataInfo(dOut, dProps):

	if ('item' not in dProps) and ('data' not in dProps): return
	
	# Make minimal entries for the data items
	dIface  = _getDict(dOut, 'interface')
	dData = _getDict(dIface, 'data')
	if 'item' in dProps:
		for sNum in dProps['item']:
			lItem = [s.strip() for s in dProps['item'][sNum].split('|')]
			
			dVar = _getDict(dData, lItem[0])
			dVar['name'] = lItem[0][0].upper() + lItem[0][1:]
			if len(lItem) > 1: dVar['title'] = lItem[1]
			if len(lItem) > 2: dVar['units'] = lItem[2]
		
	if 'data' in dProps:
		for sNum in dProps['data']:
			lItem = [s.strip() for s in dProps['data'][sNum].split('|')]
		
			dVar = _getDict(dData, lItem[0])
			dVar['name'] = lItem[0][0].upper() + lItem[0][1:]
			if len(lItem) > 1: dVar['title'] = lItem[1]
			if len(lItem) > 2: dVar['units'] = lItem[2]


# handle general configuration options
def _mergeFormat(dOut, dProps):
	"""
	The options section could have all the params stuff as well, but that
	should be done by hand since the meaning of each option is specific to
	each data source.  Here only the generic option of setting the format 
	is added.
	
	interface: {
	  options: {
		  text: { 
		    value: false
			 title: "Output stream as text (utf-8) format"
			 type: "boolean"
			 set: {
			   param: "ascii",
				value: "true"
			 }
        }
      }
	}
	"""
	
	# First the format
	
	dFmt = _getDict(dOut, "format")
	if 'das2Stream' in dProps:
		dFmt['default'] = {
			'name':'Das2 Stream', 'mime':'application/vnd.das2.das2stream'
		}
	elif 'qstream' in dProps:
		dFmt['default'] = {
			'name':'QStream', 'mime':'application/vnd.das2.qstream'
		}
	else:
		dFmt['default'] = {
			'name':'Das1 Stream', 'mime':'application/binary'
		}
	
	# Todo: Add this in when hapi conversion is allowed for general streams
	#if _isTrue(dProps, 'hapi'):
	#	dFmt['available'] = [
	#		'name':'hapi stream', 'mime':'application/vnd.hapi.hapistream'
	#	]
	
	
	# Add an option for insuring ascii streams
	if dFmt['default']['name'] == 'Das2 Stream':
		
		dIface = _getDict(dOut, 'interface')
		dOpts = _getDict(dIface, 'options')
		dDas2 = _getDict(dOpts, 'text')
		
		dDas2['title'] = 'Convert output to text (utf-8) format'
		dDas2['value'] = False
		dDas2['set'] = { 'value':True, 'param':'ascii','pval':'true'}
		

def _mergeDas2Params(dOut, dProps):
	"""Merge in params.  This is a das 2.2 thing.  Any option that is needs
	to be handled by the reader and is not a time parameter is crammed into
	params, seriously overloading that one setting.  
	
	Arguments
	  dOut - A dictionary representing the entire JSON output document
	  dProps - The parsed DSDF properties as output by parseDas22SrcProps
	
	We'll classify this object as a string or a flag-set.  If the dsdf
	props provides keys that look like this:
	
	  param_00 = 'thing | description of thing'
	  param_01 = 'other | description of other'
	  ...
	  
	Then set this up as a flagset, otherwise use a generic string option.
	
	Though the final file will likely be hand edited make an Reader Options
	entry as a courtesy.
	"""
	
	bAnyParams = False
	bFlagSet = False
	if 'param' in dProps:
		bAnyParams = True
		bFlagSet = True
		for sNum in dProps['param']:
			lParam = [s.strip() for s in dProps['param'][sNum].split('|') ]
			if len(lParam) != 2:
				bFlagSet = False
				break
	
	# Some readers have no options at all
	if not bAnyParams: return
	
	dProto = _getDict(dOut, 'protocol')
	dGet = dProto['http_params']
	
	lNums = list(dProps['param'])
	lNums.sort()
	
	if bFlagSet:
		dFlags = {}
		dGet['params'] = {
			'type':'flag_set',
			'required':False,
			'title': 'Optional reader arguments',
			'flag_sep': ' ',
			'flags': dFlags
		}
		
		for sNum in lNums:
			lParam = [s.strip() for s in dProps['param'][sNum].split('|') ]
			if lParam[0].lower() == 'integer':
				dFlags[sNum] = {'type':'integer', 'name':lParam[0], 'title':lParam[1] }
			elif lParam[0].lower() == 'real':
				dFlags[sNum] = {'type':'real', 'name':lParam[0], 'title':lParam[1] }
			else:
				dFlags[sNum] = {'value':lParam[0], 'name':lParam[0], 'title':lParam[1] }
	
	else:
		# For readers that don't have FLAGSET make a description that preserves
		# new lines
		lLines = [ dProps['param'][sNum] for sNum in lNums]

		dGet['params'] = {
			'type':'string', 
			'required':False, 
			'title':'Optional reader arguments',
			'description' : '\n'.join(lLines), 		
			'name':'Reader Parameters'
		}
	
	
	dIface = _getDict(dOut, 'interface')
	dOpts = _getDict(dIface, 'options')
	
	# If the params element is handled as a string then just output a single
	# text option.
	
	if dGet['params']['type'] == 'string':
		dOpt = _getDict(dOpts, 'extra')
		dOpt['value'] = ''
		
		if 'exampleParams' in dProps:
			for sNum in lNums:
				if sNum in dProps['exampleParams']:
					dOpt['value'] = dProps['exampleParams'][sNum]
				break # Only take the first one since that's what's used for the
				      # example time.  We want the entire example to hang together
				
		dOpt['set'] = {'param':'params'}
		dOpt['name'] = 'Extra Reader Parameters'
		if 'description' in dGet['params']:
			dOpt['description'] = dGet['params']['description']
		
	# If it's a flag_set, output one option per flag.  Be on the lookout
	# for flags that have type 'integer' and 'real'  These should became
	# text options not booleans
	else:
		for sFlag in dFlags:
			dFlag = dFlags[sFlag]
			sOptName = dFlag['name'].strip('-').strip().lower()
			dOpt = _getDict(dOpts, sOptName)
			dOpt['title'] = dFlag['title']
			
			if ('type' in dFlag) and (dFlag['type'] in ('real','integer')):
				dOpt['value'] = None
				dOpt['set'] = {'param':'params', 'flag':sFlag}
						
			else:
				dOpt['type'] = 'boolean'
				dOpt['value'] = False
				dOpt['set'] = {'value':True, 'param':'params', 'flag':sFlag}
				
	# If we want to do this as an enum this it would look like:
	#
	#    "units":{
	#    "value":"V/m",
	#    "set":{
	#    	"param":"params",
	#    	"map":[
	#    		{"value":"raw", "flag":"--units=DN"},
	#    		{"value":"V**2 m**-2 Hz**-1", "flag":"--units=SD"},
	#    		{"value":"W m**-2 Hz**-1", "flag":"--units=PF"}
	#    	]
	#    }	
						
	
def _mergeExamples(dOut, dProps, sBaseUrl):
	# A das 2.1 example looks like:
	#
	#   "QUERY":{
	#      "end_time":   (required)
	#      "params":     (optional)
	#      "resolution": (present if interval missing)
	#      "interval":   (optional)
	#      "start_time": (required)
	#   }
	#   "name": (required)
	#   "title" (optional)
	#   "URL":  (required)
	
	# Match up the example range with example params and example interval
	# Stuff like this is annoying and why we should have moved to a
	# structured config file long ago
	lRange = []
	lParams = []
	lInterval = []
	
	if 'exampleRange' in dProps:
		lRange = list(dProps['exampleRange'].keys())
		lRange.sort()
		
	if 'exampleParams' in dProps:
		lParams = list(dProps['exampleParams'].keys())
		
	if 'exampleInterval' in dProps:
		lInterval = list(dProps['exampleInterval'].keys())
	
	if len(lRange) == 0: return   # No examples provided
	
	dExamples = {}
	for sNum in lRange:
		bKeep = True
		dQuery = {}
		dExample = {"http_params":dQuery}
		sId = "example_%s"%sNum
		dExample['name'] = "Example %s"%sNum
			
		lTmp = [s.strip() for s in dProps['exampleRange'][sNum].split('|')]
		if len(lTmp) > 1:
			dExample['title'] = lTmp[1]
			
		lTmp = [s.strip() for s in lTmp[0].split('to')]
		
		if len(lTmp) < 2: continue  # Invalid range string
			
		sBeg = lTmp[0]
		sEnd = lTmp[1].replace('UTC','').strip()
		dQuery['start_time'] = sBeg
		dQuery['end_time']   = sEnd
			
		# See if we need resolution or interval
		if sNum in lInterval:
			dQuery['interval'] = dProps['exampleInterval'][sNum]
		else:
			# Default to 1/2000th of the range, here's where we need the
			# das2 module.
			dtBeg = das2.DasTime(sBeg)
			dtEnd = das2.DasTime(sEnd)
			dQuery['resolution'] = (dtEnd - dtBeg) / 2000.0
			
		if sNum in lParams:
			dQuery['params'] = dProps['exampleParams'][sNum]
		
		lQuery = [
			"%s=%s"%(sKey, quote_plus(str(dQuery[sKey])))
			for sKey in dQuery
		]
		
		dExample['url'] = "%s&%s"%(sBaseUrl, '&'.join(lQuery))
		
		# TODO: Merge in examples from the DSDFs with hand entered ones
		dExamples[sId] = dExample
		
	if len(dExamples) > 0:
		dProto = _getDict(dOut, 'protocol')
		dProto['examples'] = dExamples
	
	
##############################################################################
def updateSource(log, dNode, sIdRoot, bNoOp):
	"""log - logger object
	   dNode - The source node to write 

		bNoOp - Do everything but write the final files.  Temporary files are
		        written to check for changes but then deleted.
				  
		Returns: the new version of dNode that matches the on disk version or
		         none if an error occurred
	"""
	# Here's the layout
	#  
	#  name, title, type, path, tech_contact
	#
	#  coordinates = {
	#     Coordinate vars and thier properties and prop alterations
	#     
	#  }
	#
	#  data   = {
	#    Data vars and thier properties and prop alterations
	#    
	#  }
	#
	#  configuration = {
	#     Other configurable items 
	#  }
	#
	#
	#	convention   = 'das2/2.2'
	#  base_urls = []
	#  authentication   = {'required':'yes/no/range', 'realm':''}
	#
	#  http_params = {     
	#     # 1 entry per get parameter for the source
	#  }
	# 
	#  examples = []
	
	
	# Most of the information for a stream source comes from the properties
	# if I don't have this don't write anything
	if 'props' not in dNode:
		log.error("das2 dsdf properties missing, can't write stream source"
		          " catalog entry, %s", dNode['path'])
		return None
	
	dProps = dNode['props']

	dOut = {}
	if os.path.isfile(dNode['filename']):
		fIn = open(dNode['filename'])
		dOut = json.load(fIn)
		fIn.close()

	# The disk entries may have been hand edited.  Don't override the name and
	# title, go ahead and smash the type and path
	if 'name' not in dOut: dOut['name'] = dNode['name']
	if 'title' not in dOut: dOut["title"] = dNode['title']
	dOut['type'] = 'HttpStreamSrc'
	dOut['version'] = "0.6"
	dProto = _getDict(dOut, 'protocol')
	dProto['convention'] = 'das2/2.2'

	
	# make an ID for the datasource if requested
	if sIdRoot:
		sSrvPath = '.'.join(dNode['_srvPath'])
		sUid = sIdRoot + sSrvPath.lower().replace(' ','_')
		if 'uris' in dNode:
			if sUid not in dNode['uris']:
				dNode['uris'].append(sUid)
		else:
			dNode['uris'] = [sUid]
	if 'uris' in dNode:
		dOut['uris'] = dNode['uris']
		
		
	_mergeTechContacts(dOut, dProps)
	
	_mergeSrcCoordInfo(dOut, dProps)
	
	_mergeSrcDataInfo(dOut, dProps)
	
	_mergeFormat(dOut, dProps)   # Just the format for now, but hand edited
	                                # items could be in there
	
	# Make sure this base url is included
	lUrls = _getList(dProto, 'base_urls')
	
	sFmt = "%s?server=dataset&dataset=%s"
	if 'server' in dProps: 
		sBaseUrl = sFmt%(dProps['server']['00'], dNode['dataset'])
	else:
		sBaseUrl = sFmt%(dNode['server'], dNode['dataset'])
	if sBaseUrl not in lUrls:  lUrls.append(sBaseUrl)
		
	if 'securityRealm' in dProps:
		dProto['authentication'] = {
			'required':True, 'realm':dProps['securityRealm']['00']
		}
	else:
		dProto['authentication'] = {'required':False}
	
	dGet = {}
	dProto['http_params'] = dGet
	
	dGet['start_time'] = {
		'required':True, 'type':'isotime',
		'name':'Min Time', 'title':'Minimum time value to stream',
	}
		
	dGet['end_time'] = {
		'required':True, 'type':'isotime',
		'name':'Max Time', 'title':'Maximum Time Value to stream',
	}
	
	dGet['ascii'] = {
		'required':False, 'type':'boolean', 'name':'UTF-8',
		'title':'Insure stream output is readable as UTF-8 text'
	}
	
	# See if requires interval is set, if not
	if _isPropTrue(dProps, 'requiresInterval'):
		dGet['interval'] = {
			'required':True, 'type':'real', 'units':'s',
			'name':'Interval', 
			'title':'Time interval between model calculations/interpolations',
			'description': 'This parameter is used with data generated from models '
			        'or table interpolations such as SPICE Ephemerides and '
					  'magnetic field models',
		}

	else:
		dGet['resolution'] = {
			'required':False, 'type':'real', 'units':'s',
			'name':'Resolution', 
			'title':'Maximum resolution between output time points',
			'description':'The server will return data at or better than the given '
                'resolution if possible.  Leave un-specified to get data '
			       'at intrinsic resolution without server side averages',
		}

		
	# See if there is any sign of this source supporting extra parameters
	# this could come from having a param or exampleParams
	_mergeDas2Params(dOut, dProps)
		
	# Could ask server if text output is supported, old servers don't 
	# have a way to do this.
	_mergeExamples(dOut, dProps, sBaseUrl)
	
	#if dOut['path'].find('ephemeris') != -1:
	#	_dumpProps(dProps)
	#	sys.exit(117)
	
	
	if not writeObj(log, dOut, dNode['filename'], bNoOp):
		return None

	return dOut
	
##############################################################################
def updateCollection(log, dNode, sNodeUrl, sIdRoot, bNoOp):
	"""log - logger object
	   dNode - The collection node to write 
		sNodeUrl - The url that refers to this collection node, used to generate
		           sub urls
		bNoOp - Do everything but write the final files.  Temporary files are
		        written to check for changes but then deleted.
				  
		Returns: the new version of dNode that matches the on disk version or
		         none if an error occurred
	"""

	# Read the disk file, it may have stuff we want to merge in
	dOut = {}
	if dNode['filename'] and os.path.isfile(dNode['filename']):
		fIn = open(dNode['filename'])
		dOut = json.load(fIn)
		fIn.close()

	# The disk entries may have been hand edited.  Don't override the name and
	# title, go ahead and smash the type and path
	if 'name' not in dOut: dOut['name'] = dNode['name']
	if 'title' not in dOut: dOut["title"] = dNode['title']
	dOut['type'] = dNode['type']
	dOut['version'] = "0.6"
	
	# Unlike catalogs, collections can pull in some information directly
	# from the dsdfs
	dProps = None
	if len(dNode['subnodes']) != 0:
		# Try for a das2/2.2 node
		for sChild in dNode['subnodes']:
			dChild = dNode['subnodes'][sChild]
						
			if 'convention' in dChild['protocol']:
				if dChild['protocol']['convention'] == 'das2/2.2':
					if 'props' in dChild:
						dProps = dChild['props']
						break

	# If we have a properties item, pull up obscore, sci contact and data elements	
	if dProps:
		for sProp in dProps:
			if sProp in g_lObsCoreCollection:
				dObsCore = _getDict(dOut, 'EPNcore')
				dObsCore[sProp] = dProps[sProp]['00']
			elif sProp in g_lObsCoreCollectionTrans:
				dObsCore = _getDict(dOut, 'EPNcore')
				dObsCore[ g_lObsCoreCollectionTrans[sProp] ] = dProps[sProp]['00']
	
		_mergeSciContacts(dOut, dProps)
		_mergeColDataInfo(dOut, dProps)
		_mergeColCoordInfo(dOut, dProps)
	else:
		log.warning("Properties not found for collection %s"%dNode['path'])
		
	
	# Merge in new data sources, NOTE: We have to do this bottom up because
	# names and other elements can bubble up into higher level catalog entries
	dEntries = _getDict(dOut, 'sources')
	
	for sChild in dNode['subnodes']:

		dChild = dNode['subnodes'][sChild]
		sKey = dChild['_srvPath'][-1].lower()

		# NOTE: dChild override occurs here.  Returned dChild may have
		#       different values that were brought up from existing disk files
		if dChild['type'] == 'HttpStreamSrc':
			dChild = updateSource(log, dChild, sIdRoot, bNoOp)
			if dChild == None:
				# Collection can still be useful even if no das2 src is available
				# since we should have file aggregations in the future
				continue
		else:
			log.error("Unknown catalog entry type '%s' for item '%s'"%(
				dChild['type'], dChild['path']))
			return None

		dEntry = _getDict(dEntries, sKey)
		for sTmp in 'type', 'name':
			dEntry[sTmp] = dChild[sTmp]
		dEntry['purpose'] = 'primary-stream'
		if 'protocol' in dChild:
			if 'convention' in dChild['protocol']:
				dEntry['convention'] = dChild['protocol']['convention']
				
		#if 'format' in dChild:
		#	if 'default' in dChild['format']:
		#		if 'mime' in dChild['format']['default']:
		#			dEntry['formats'] = [ dChild['format']['default']['mime'] ]


		# Set at leat one URL (don't delete exiting urls)
		sSubUrl = "%s/%s.json"%(sNodeUrl.replace('.json', ''), sKey)
		if 'urls' not in dEntry:
			dEntry['urls'] = []
		if sSubUrl not in dEntry['urls']:
			dEntry['urls'].append(sSubUrl)

	if dNode['filename']:
		if not writeObj(log, dOut, dNode['filename'], bNoOp):
			return None

	return dOut


##############################################################################
def updateCatalog(log, dNode, sNodeUrl, sIdRoot, bNoOp):
	"""log - logger object
	   dNode - The catalog node to write (Can't be a collection or source)
		sNodeUrl - The url that refers to this catalog node, used to generate
		           sub urls
		bNoOp - Do everything but write the final files.  Temporary files are
		        written to check for changes but then deleted.
		Returns: the new version of dNode that matches the on disk version or
		         none if an error occurred
	"""

	#dEntries = {}

	# Read the disk file, it may have stuff we want to merge in
	dOut = {}
	if dNode['filename'] and os.path.isfile(dNode['filename']):
		fIn = open(dNode['filename'])
		dOut = json.load(fIn)
		fIn.close()

	# The disk entries may have been hand edited.  Don't override the name and
	# title, go ahead and smash the type, version and  path
	if 'name' not in dOut: dOut['name'] = dNode['name']
	if 'title' not in dOut: dOut["title"] = dNode['title']
	dOut['type'] = dNode['type']
	dOut['version'] = "0.6"

	# Merge in new catalog entries, NOTE: We have to do this bottom up because
	# names can bubble up into higher level catalog entries
	dEntries = _getDict(dOut, 'catalog')
	
	# Some or all of the subnodes may over-ride our current catalog contents
	# read and replace
	
	for sChild in dNode['subnodes']:

		dChild = dNode['subnodes'][sChild]
		sKey = dChild['_srvPath'][-1].lower()
		sSubUrl = "%s/%s.json"%(sNodeUrl.replace('.json', ''), sKey)

		# NOTE: dChild override occurs here.  Returned dChild may have
		#       different values that were brought up from existing disk files
		if dChild['type'] == 'Catalog':
			dChild = updateCatalog(log, dChild, sSubUrl, sIdRoot, bNoOp)
			if dChild == None:
				return None
		elif dChild['type'] == 'Collection':
			dChild = updateCollection(log, dChild, sSubUrl, sIdRoot, bNoOp)
			if dChild == None:
				return None
		else:
			log.error("Unknown catalog entry type '%s' for item '%s'"%(
				dChild['type'], dChild['path']))
			return None

		if dChild == None:
			return None          # Error out, don't write to disk. (change?)

		if sKey in dEntries:
			dEntry = dEntries[sKey]
		else:
			dEntry = {}
			dEntries[sKey] = dEntry

		for sTmp in 'type', 'name', 'title':
			dEntry[sTmp] = dChild[sTmp]

		# Set at least one URL (don't delete exiting urls)
		lUrls = _getList(dEntry, 'urls')
		if sSubUrl not in dEntry['urls']:
			lUrls.append(sSubUrl)

	if dNode['filename']:
		if not writeObj(log, dOut, dNode['filename'], bNoOp):
			return None

	return dOut

##############################################################################

def prnCatalog(log, dNode, nLevel):

	sPre = " "*(nLevel*3)

	if 'subnodes' in dNode:
		print("%s -> %s"%(dNode['name'], dNode['subnodes'].keys()))
		for sKey in dNode['subnodes']:
			prnCatalog(log, dNode['subnodes'][sKey], nLevel + 1)



##############################################################################

def main(argv):
	global g_lRmDirs

	perr = sys.stderr.write

	gettext.install('das2_cat_import')

	sDesc = _("Contact a remote das2 server and import it's dsdfs.")

	psr = argparse.ArgumentParser( prog=bname(argv[0]), description=sDesc)

	add_arg = psr.add_argument

	add_arg('-v', '--version', action='version',
	        version=" \n".join( [g_sRev, g_sWho, g_sWhen, g_sURL] ))

	#add_arg('-H', '--helio', action="store", dest="bHelio", default=False,
	#        help=_("Check for and make entries for any heliophysics streams"
	#		         "available from the server"))

	add_arg('-l', "--log-level", dest="sLevel", metavar="LOG_LEVEL",
           help=_("Logging level one of [critical, error, warning, "
	        "info, debug].  The default is warning, ONLY set the level "
	        "lower than this for testing, not production."),
	        action="store", default="info")

	add_arg("-t", "--title", action='store', dest="sTitle", metavar="title",
	        help=_("Since the top level item '/', never has a description "
			  "line provide one here with this option.  Will be set as the "
			  "title for the output catalog"), default=None )

	add_arg("-n", "--no-op", action='store_true', dest="bNoOp", default=False,
	        help=_("Don't actually write anything permanent.  Temporary files "
			  "are written to check for changes but then deleted."))

	add_arg("-e", "--exclude", action='append', dest="lExclude",
	        metavar="SRV_PATH", help=_("Specify a dataset path to exclude."
			  " All items under the given location will be ignored.  May be "
			  "given multiple times"), default=[])

	add_arg("-i", "--ids", dest="sIdRoot", default=None,
	        metavar="ID_ROOT", help=_("Make URIs for the data sources.  These"
			  " are handy for finding sources after a catalog re-organization. "
			  "IDs will be created by removing by: ID_ROOT + DSDF_ID.lower(), "
			  "in addition any whitespace will be converted and '/' chars become '.' "
			  "chars.  Ex: -i tag:physics.uiowa.edu,2018:das. "))

	add_arg('SRV_URL', nargs=1, help=_("The top level URL of the das 2.2"
				"server to contact, ex: "
				"http://voparis-maser-das.obspm.fr/das2/server"))

	add_arg('SRV_PATH', nargs=1, help=_("The top level dataset (or directory) "
	        "to read.  Any proceeding '/' characters are removed as all paths "
			  "are relative to the server root"))
			  
	add_arg('CAT_PATH', nargs=1, help=_("The catalog path that corresponds "
	        'to the root of the server.  Example: "site:/uiowa/" is the base '
			  'URI for datasets from planet.physics.uiowa.edu.  Multiple '
			  "servers can map to the same root.  For example the 'planet' "
			  "'jupiter' and 'emphsis' servers at uiowa.edu all serve datasets "
			  "for a 'site:/uiowa' namespace.  As usual, 'tag:das2.org,2012:' "
			  "will be prepended to the given URI if it's missing "))

	add_arg('ROOT_URL', nargs=1,  help=_('The URL that provides a catalog file'
	        'corresponding to the root namespace for this server.  Multiple '
			  'servers may map to the same root URL.  This value should end in '
			  "'.json' and is used to build catalog sub-references.  Example: "
			  'http://das2.org/catalog/das/site/uiowa.json'))

	add_arg('OUT_DIR', nargs=1, help=_('The output directory, can be a '
	        'relative or absolute path.  The SRV_PATH item will be written '
			  'or updated in this directory.  Sub items will appear/update in sub '
			  'directories.'))

	args = psr.parse_args()

	# More input argument initialization
	lPathInc = []
	if args.SRV_PATH[0] != '/':
		l = args.SRV_PATH[0].split('/')
		for s in l:
			if s != '': lPathInc.append(s)

	log = setupLogger(args.sLevel, bname(argv[0]))

	sDas2Server = args.SRV_URL[0]

	if not args.CAT_PATH[0].startswith('tag:das2.org,2012:'):
		sCatNodeUri = 'tag:das2.org,2012:%s'%args.CAT_PATH[0].lower()
	else:
		sCatNodeUri = args.CAT_PATH[0].lower()

	if sCatNodeUri[-1] == '/':
		sCatNodeUri = sCatNodeUri[:-1]

	sOutDir = args.OUT_DIR[0]

	sCatNodeUrl = args.ROOT_URL[0]
	if not sCatNodeUrl.endswith('.json'):
		log.error("Catalog URL (arg 4) must end in '.json'")
		return 13

	log.info("Getting das2.2 list from %s"%sDas2Server)
	sURL = '%s?server=list'%sDas2Server
	res = requests.get(sURL)
	if res.status_code != requests.codes.ok:
		log.error("Couldn't get das 2.2 dataset list from %s"%sURL)
		return 17
		
	sDsdfs = res.text


	for sExclude in args.lExclude:
		sTmp = sExclude
		if sTmp[0] == '/': sTmp = sExclude[1:]
		log.info("Skipping all datasets in path %s"%sTmp)


	# Break the list down into ( [_srvPath/list/], type, description ) tuples
	# to make it easier to sort and parse.  Create an artifical DSDF for
	# the server top node.
	sName = sCatNodeUri[sCatNodeUri.rfind('/') + 1: ]
	if args.sTitle:
		sTitle = args.sTitle
	else:
		log.info("Getting das2.2 id from   %s"%sDas2Server)
		sURL = '%s?server=id'%sDas2Server
		res = requests.get(sURL)
		if res.status_code != requests.codes.ok:
			log.error("Couldn't get das 2.2 server id from %s"%sURL)
			return 17
		sTitle = res.text.strip()

	lDsdfs = [ {'_srvPath':[], 'type':'Catalog', 'name':sName, 'title':sTitle} ]

	for sLine in sDsdfs.split('\n'):
		lTmp = [ s.strip() for s in sLine.split('|') ]

		if len(lTmp) < 1:
			continue

		sSrvNode = lTmp[0].strip().replace('.dsdf','')

		if len(sSrvNode) < 2:continue

		if len(lTmp) > 1:
			sTitle = lTmp[1]
		else:
			sTitle = None

		if sSrvNode.lower().find('/test/') != -1: continue
		if sSrvNode.lower().find('/testing/') != -1: continue

		# Check to make sure this dataset doesn't start with one of
		# the exclude patterns
		bIgnore = False
		for sExclude in args.lExclude:
			sTmp = sExclude
			if sExclude[0] == '/': sTmp = sExclude[1:]
			if sSrvNode.startswith(sTmp):
				bIgnore = True
				break

		if bIgnore: continue

		sType = "Collection"
		if sSrvNode[-1] == '/':
			sType = "Catalog"

		lPath = lTmp[0].split('/')
		if lPath[-1] == "": lPath.pop(-1)

		sDesc = None
		if (len(lTmp) > 1) and len(lTmp[1]) > 0:
			sDesc = lTmp[1]

		lDsdfs.append( {'_srvPath':lPath, 'type':sType, 'title':sDesc,
		                'name': lPath[-1].replace('_',' ') } )

	lDsdfs.sort(key=lambda a: a['_srvPath'])


	# go through the list removing items that don't match the requested include
	# _srvPath.  Or do not lead to the requested include _srvPath. 
	lNodes = []
	nDownload = 0
	nWrite = 0

	for dNode in lDsdfs:
		log.debug("Checking node _srvPath %s against %s"%(dNode['_srvPath'], lPathInc))
		sSrvDir = bname(sCatNodeUrl).lower().replace('.json','')
		
		if _atOrUnder(dNode['_srvPath'], lPathInc):
			
			lFullPathInc = [sSrvDir] + lPathInc
			
			if len(dNode['_srvPath']) == 0:
				dNode['filename'] =  "%s/%s"%(sOutDir, bname(sCatNodeUrl).lower())
				
			else:
				lFullPathTarg = [sSrvDir] + dNode['_srvPath']
				sPartialPath = '/'.join(lFullPathTarg[ len(lFullPathInc) - 1 : ] )
				
				dNode['filename'] = "%s/%s.json"%(sOutDir,sPartialPath)
				dNode['filename'] = dNode['filename'].lower()	
				
			lNodes.append(dNode)
			
			if dNode['type'] == 'Collection':
				nDownload += 1
				lPath = dNode['_srvPath'] + ['das2']
				dProtocol = {'convention':'das2/2.2'}
				dStreamNode = {'type':'HttpStreamSrc', 'protocol':dProtocol,
				               '_srvPath':lPath, 'title': dNode['title'],
									'name':'Das2/2.2 Source'}
				
				lFullPathTarg = [sSrvDir] + dStreamNode['_srvPath']
				
				sPartialPath = '/'.join(lFullPathTarg[ len(lFullPathInc) - 1 : ] )
				dStreamNode['filename'] = "%s/%s.json"%(sOutDir,sPartialPath)
				dStreamNode['filename'] = dStreamNode['filename'].lower()
				
				lNodes.append(dStreamNode)
				
			nWrite += 1

		elif _leadsTo(dNode['_srvPath'], lPathInc):
			lNodes.append(dNode)
			dNode['filename'] = None  # I'm not writing to this item, it's above
			                          # the requested output level
											  

	# If there's nothing in the direct update list, just exit
	if nWrite == 0:
		log.error("No datasets on server '%s' match id '%s'"%(sDas2Server,
		          args.SRV_PATH[0]))
		return 0

	# Setup the URI's, these are always based off the server root uri no matter
	# branch we are writting 
	for dNode in lNodes:
		sPathDir = '/'.join([ s.lower() for s in dNode['_srvPath'] ])
		if len(sPathDir) > 0:
			dNode['path'] = "%s/%s"%(sCatNodeUri, sPathDir)
		else:
			dNode['path'] = sCatNodeUri
	
	#for dNode in lNodes:
	#	print("%s -> %s"%(dNode['path'],dNode['filename']))
	#sys.exit(117)
	

	# go though all the items and get the dsdf info for datasets to update
	log.info("Gathering %d dataset definitions"%nDownload)

	for dNode in lNodes:
		if dNode['type'] != 'HttpStreamSrc': continue

		sDataSet = '/'.join(dNode['_srvPath'][:-1])

		log.info("Getting das 2.2 definition for %s"%sDataSet)
		sDsdfUrl = '%s?server=dsdf&dataset=%s'%(sDas2Server, sDataSet)
		res = requests.get(sDsdfUrl)
		if res.status_code != requests.codes.ok:
			log.error("Couldn't get das 2.2 dataset definition from %s"%sDsdfUrl)
			continue

		sStream = res.text

		# Parse the stream into a reasonable data structure. i.e.
		# coord_00, cord_01 become coord{ '00': , '01':, ... }
		dDas2Props = parseDas22SrcProps(log, sDsdfUrl, sStream)
				
		dNode['server'] = sDas2Server
		dNode['dataset'] = sDataSet
		dNode['props'] = dDas2Props
		

	dTop = arrangeNodes(log, lNodes)
	if dTop == None:
		return 17

	dNewTop = updateCatalog(log, dTop, sCatNodeUrl, args.sIdRoot, args.bNoOp)
	
	# Cleanup directories on no-op runs
	if args.bNoOp:
		for sDir in reversed(g_lRmDirs): os.rmdir()
	
	
	if dNewTop == None:
		return 13
	return 0

##############################################################################
if __name__ == "__main__":
	sys.exit(main(sys.argv))
