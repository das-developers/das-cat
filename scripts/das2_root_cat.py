#!/usr/bin/env python3

import sys
from os.path import basename as bname
import json

# Currently our data are identified by URLs which change when data move from
# server to server.  We need some sort of IDs which don't change when data
# sources move around, along with some way to map those IDs to actual data
# load paths.
#
# These catalogs exist to handle the URI to URL mapping.  As for the URIs
# themselves, das2 catalogs use the "tag:" URI scheme that scheme is the 
# easiest to implement.  Here's an article on the tag scheme:
#
#  https://www.ibm.com/developerworks/library/x-mxd6/index.html
#
# Note that many in the space physics community use non-URIs as if they were
# URIs.  Some of the most nortorious are 'urn:nasa', 'spase://', and 'vap+'
# With the tag scheme it's easy to turn these pseudo URIs into real URIs by
# prefixing a valid tag.  That's what these catalogs do.
#
# Each object of TYPE Catalog contains a URI (except for the root), and
# a list of possible extension URIs from that point.

g_sRootUrl = "https://das2.org/catalog"

#g_sRootUrl = "https://das2.org/cat_test"

##############################################################################
# das2.org Site Root, there could be disipline roots in the future, but for
# now this is the only root path

g_dDasSiteCat = {
	"title":"Federated Site Catalog",
	"name": "Sites",
	"type":"Catalog",
	'version':'0.4',

	"description":" ".join( """
		This is the root node of the federated das2 site catalog. 
		
		By convention, each entry at this point anchors the top node of an 
		organization's production das2 catalogs. Organizations with multiple
		independent internal groups using das2 should create a single 
		institutional site catalog and link that here. 
		
		Contact Larry Granroth at the University of Iowa to have your top 
		level site catalog listed here. Das2 catalogs provide an informal 
		Federation. If you have space physics or supporting data to share, 
		your site is welcome to be linked here.
		
	""".split()),

	#"path_uri":"tag:das2.org,2012:site",
	"separator":":/",
	"catalog":{

		"uiowa":{
			"type":"Catalog",
			"name": "U. Iowa",
			"title":"University of Iowa, Department of Physics & Astronomy",
			"urls":["%s/das/site/uiowa.json"%g_sRootUrl],
		},

		"jhuapl":{
			"type":"Catalog",
			"name":"JHU APL",
			"title":"Johns Hopkins University, Applied Physics Laboratory",
			"urls":["%s/das/site/jhuapl.json"%g_sRootUrl],
		},
		
#		"swri":{
#			"type":"Catalog",
#			"name":"SwRI",
#			"title":"Southwest Research Institute",
#			"urls":["%s/das/site/swri.json"%g_sRootUrl],
#		},

		"voparis":{
			"type":"Catalog",
			"name":"VO-Paris",
			"title":"Paris Astronomical Data Centre",
			"urls":["%s/das/site/voparis.json"%g_sRootUrl]
		}
	}
}

##############################################################################

g_dDasTestCat = {
	"title":"Root test Catalog",
	"name": "das2 test sites",
	"type":"Catalog",
	'version':'0.4',

	"description":" ".join( """This is the root node of the federated das2
	   test catalog.  This is an even more informal registry than the das2
		sites catalog.  Data stream sources listed within this three may be
		temporary, may change names often and may not even work, and that's
		okay.

		If you would like to experiment with serving data via das2 streams
		or just with the global das2 catalog system you are welcome to have
		your site listed here.

		Contact Larry Granroth at the University of Iowa to have your top level
		site test catalog linked in at this point.
	""".split()),

	#"path_uri":"tag:das2.org,2012:test",
	"separator":":/",
	"catalog":{

		"uiowa":{
			"type":"Catalog",
			"name": "U. Iowa",
			"title":"University of Iowa, Department of Physics & Astronomy",
			"urls":["%s/das/test/uiowa.json"%g_sRootUrl],
		}
		
#		"swri":{
#			"type":"Catalog",
#			"name":"SwRI",
#			"title":"Southwest Research Institute",
#			"urls":[]
#		},
#		"voparis":{
#			"type":"Catalog",
#			"name":"VO-Paris",
#			"title":"Paris Astronomical Data Centre",
#			"urls":[]
#		}
	}
}


##############################################################################
g_dDasCat = {
	"type":"Catalog",
	"title":"Federated Das2 Catalog",
	"name":"das2",
	'version':'0.4',

	# tag:das2.org,2012: site:/ uiowa/ cassini/ ephemeris/ dione

	"description":' '.join('''The das2 URIs denote paths in a federated catalog
	    that may have nodes leading to many different organizations and servers.
		 Paths start with the Scheme URI, followed by the ROOT designator and
		 then a posix style path that leads to a node.  Sub-node information
		 (infact individual keys) can be indicated by adding a FRAGMENT separator
		 and then the path to the designated object.  Each root defines an
		 organizational scheme.  At present only the 'site:' root designator is
		 used.  Unlike VOTable objects and HAPI nodes, Das2 Catalogs do not
		 provide details of the internals of each dataset.
		 '''.split()),

	#"path_uri":"tag:das2.org,2012:",
	"separator":None,
	"catalog":{
		"site":{
			"type":"Catalog",
			"name" :g_dDasSiteCat["name"],
			"title":g_dDasSiteCat["title"],
			"urls":["%s/das/site.json"%g_sRootUrl]
		},
		"test":{
			"type":"Catalog",
			"name" :g_dDasTestCat["name"],
			"title":g_dDasTestCat["title"],
			"urls":["%s/das/test.json"%g_sRootUrl]
		},
	}
}


##############################################################################
# Since there is no way (that I know of) to get a top level spase record
# make one entry for each SPASE naming authority and then hand this over to
# something that understands the "SpaseRecord" catalog node type

g_dSpaseCat = {
	"type":"Catalog",
	'version':'0.4',
	"name": "SPASE",
	"title":"Space Physics Archive Search and Extract (SPASE) Metadata Registry",

	"description":' '.join('''The Space Physics Archive Search and
	Extract (SPASE) effort is a Heliophysics community-based project with
	the goal of facilitating data search and retrieval across the Space and
	Solar Physics data environment with a common metadata language'''.split()),

	#"path_uri":"tag:space-group.org,2018:spase",
	"separator":"://",
	"catalog":{
"ASWS":{
	"name": "ASWS",
	"title": "Australian Space Weather Services (ASWS)",
	"description": ' '.join('''Assigns resource IDs for data registered
	in the Australian Space Weather Services.'''.split() ),
	"reference_urls" : [
		"https://www.sws.bom.gov.au/World_Data_Centre",
		"https://github.com/hpde/ASWS"
	],
	"type": "SpaseRecord",
	"urls": ["https://spase-group.org/registry/resolver?t=yes&i=spase://ASWS"]
},
"CCMC":{
	"name": "CCMC",
	"title":"Community Coordinated Modeling Center (CCMC)",
	"description":' '.join('''Assigns resource IDs for data available from
	 the Community Coordinated Modeling Center'''.split()),
	"reference_urls": ["https://ccmc.gsfc.nasa.gov/","https://github.com/hpde/CCMC"],
	"type": "SpaseRecord",
	"urls": ["https://spase-group.org/registry/resolver?t=yes&i=spase://CCMC"]
},
"CSSDP":{
	"name": "CSSDP",
	"title": "Canadian Space Science Data Portal (CSSDP)",
	"description": ' '.join("""Assigns resource IDs for data registered in the Canadian
	Space Science Data Portal""".split()),
	"reference_urls": ["https://www.cssdp.ca/","https://github.com/hpde/CSSDP"],
	"type": "SpaseRecord",
	"urls": ["https://spase-group.org/registry/resolver?t=yes&i=spase://CSSDP"]
},
"ESA":{
	"name": "ESA",
	"title": "European Space Agency (ESA)",
	"description": ' '.join("""Assigns resource IDs for data available from the European
	Space Agency""".split()),
	"reference_urls": ["https://www.esa.int/ESA","https://github.com/hpde/ESA"],
	"type": "SpaseRecord",
	"urls": ["https://spase-group.org/registry/resolver?t=yes&i=spase://ESA"]
},
"ISWI":{
	"name": "ISWI",
	"title": "International Space Weather Initiative (ISWI)",
	"description": ' '.join("""Assigns resource IDs for data available from the
	International Space Weather Initiative""".split()),
	"reference_urls": ["https://www.iswi-secretariat.org/","https://github.com/hpde/ISWI"],
	"type": "SpaseRecord",
	"urls": ["https://spase-group.org/registry/resolver?t=yes&i=spase://ISWI"]
},
"GBO":{
	"name": "GBO",
	"title": "Ground Based Observatories",
	"description": ' '.join("""Assigns resource IDs for data available from the ground
	based observatories""".split()),
	"reference_urls": ["https://vspo.gsfc.nasa.gov","https://github.com/hpde/GBO"],
	"type": "SpaseRecord",
	"urls": ["https://spase-group.org/registry/resolver?t=yes&i=spase://GBO"]
},
"JAXA":{
	"name": "JAXA",
	"title": "Japan Aerospace Exploration Agency (JAXA)",
	"description": ' '.join("""Assigns resource IDs for data available from the Japan
	Aerospace Exploration Agency""".split()),
	"reference_urls": ["https://global.jaxa.jp/","https://github.com/hpde/JAXA"],
	"type": "SpaseRecord",
	"urls": ["https://spase-group.org/registry/resolver?t=yes&i=spase://JAXA"]
},
"NOAA":{
	"name": "NOAA",
	"title": "National Oceanic and Atmospheric Administration (NOAA)",
	"description": ' '.join("""Assigns resource IDs for data registered in National
	Oceanic and Atmospheric Administration (NOAA) data systems.""".split()),
	"reference_urls": ["https://www.nesdis.noaa.gov/","https://github.com/hpde/NOAA"],
	"type": "SpaseRecord",
	"urls": ["https://spase-group.org/registry/resolver?t=yes&i=spase://NOAA"]
},
"NFS":{
	"name": "NFS",
	"title": "National Science Foundation (NSF)",
	"description": ' '.join("""Assigns resource IDs for data available from the National
	Science Foundation (NSF)""".split()),
	"reference_urls": ["https://www.nsf.gov/","https://github.com/hpde/NFS"],
	"type": "SpaseRecord",
	"urls": ["https://spase-group.org/registry/resolver?t=yes&i=spase://NFS"]
},
"SMWG":{
	"name": "SMWG",
	"title": "SPASE Metadata Working Group (SMWG)",
	"description": ' '.join("""The community location for entities such as persons,
	observatories, instruments, repositories, registries and services.""".split()),
	"reference_urls": ["https://www.spase-group.org/registry","https://github.com/hpde/spase-SMWG"],
	"type": "SpaseRecord",
	"urls": ["https://spase-group.org/registry/resolver?t=yes&i=spase://SMWG"]
},
"VSPO":{
	"name":  "VSPO",
	"title": "Virtual Space Physics Observatory (VSPO)",
	"description": ' '.join("""
	""".split()),
	"reference_urls": ["https://vspo.gsfc.nasa.gov","https://github.com/hpde/spase-VSPO"],
	"type": "SpaseRecord",
	"urls": ["https://spase-group.org/registry/resolver?t=yes&i=spase://VSPO"]
}
	}

}

##############################################################################
g_dCdaWebCat = {
	"type":'Catalog',
	'version':'0.4',
	"name": 'CDAWeb',
	"title":'NASA Goddard Spaceflight Center Data Sites',

	#"path_uri":'tag:cdaweb.sci.gsfc.nasa.gov,2018:',
	"separator":None,
	"catalog":{
		'/':{
			"name" :'CDAWeb_SPDF',
			"title":'CDAWeb and Space Physics Data Facility (SPDF) catalog',
			"type":'SpdfMasterCat',
			'MIME':'text/xml',
			"urls":['https://cdaweb.sci.gsfc.nasa.gov/pub/catalogs/all.xml'	]
		}
	}
}


##############################################################################
g_dRootCat = {
	"title":"Root Path List",
	"name": "Root",
	"type":"Catalog",
	'version':'0.4',
	"description":' '.join('''
		This the root das2 catalog.  All paths below here are assumed to be valid
		URIs.  According to RFC 3986 strings starting with "pds:", "spase:",
		"vap+", "das:" etc. are niether URIs nor URNs as these have not been
		registered in accordance with RFC 7595 or RFC 8254.  This is easy to fix,
		all that's required is to prefix these schemes with any valid tag URI.
		Since it seems presumuous to use tag:das2.org,2012: for items that are
		clearly owned by others, this root catalog contains a global list of URI
		prefixes to be used a seed paths.
		'''.split()),

	#"path_uri":None,
	"separator":None,
	"catalog": {
		"tag:das2.org,2012:": {
			"type":"Catalog",
			"name": g_dDasCat["name"],
			"title":g_dDasCat["title"],
			"urls":["%s/das.json"%g_sRootUrl]
		},

		"tag:spase-group.org,2018:spase://": {
			"type":"Catalog",
			"name": g_dSpaseCat["name"],
			"title":g_dSpaseCat["title"],
			"urls":["%s/spase.json"%g_sRootUrl]
		},

		"tag:cdaweb.sci.gsfc.nasa.gov,2018:": {
			"type":"Catalog",
			"name": g_dCdaWebCat["name"],
			"title": g_dCdaWebCat["title"],
			"urls":["%s/cdaweb.json"%g_sRootUrl]
		}
	}

#	"tag:pds.nasa.gov,2018:" : {
#		"type":'NameSpace',
#		'URI':'tag:pds.nasa.gov,2017:_namespace_',
#		"title":
#
#
#
#
#	}
}

##############################################################################
def help(sProg):
	perr = sys.stderr.write
	perr("Generate standard root das2 catalogs on standard output\n")
	perr("this program does not read a database, it merely exists as\n")
	perr("a convienent way to output fixed JSON data\n")
	perr("\n")
	perr("  Usage %s [root | das | spase | cdaweb | das_site | das_test]\n"%sProg )
	perr("\n")
	perr("Outputs one of the given catalogs to standard output, you\n")
	perr("must redirect it to files on your own.\n")


##############################################################################
def main(argv):

	if len(argv) == 1:
		help(bname(argv[0]))
		return 13

	for s in argv:
		if (s == '-h') or (s == '--help'):
			help(bname(argv[0]))
			return 0


	d = None
	if len(argv) < 1:
		d = prnRootLocs()
	else:
		sItem = argv[1]
		if sItem.lower() == "root":
			d = g_dRootCat
		elif sItem.lower() == "das":
			d = g_dDasCat
		elif sItem.lower() == "cdaweb":
			d = g_dCdaWebCat
		elif sItem.lower() == "spase":
			d = g_dSpaseCat
		elif sItem.lower()	== "das_site":
			d = g_dDasSiteCat
		elif sItem.lower()	== "das_test":
			d = g_dDasTestCat
		else:
			sys.stderr.write("ERROR: Unknown catalog selected: '%s'\n"%sItem)
			return 4

	s = json.dumps(d, ensure_ascii=False, indent="  ", sort_keys=True)
	print(s)

	return 0

##############################################################################
if __name__ == "__main__":
	sys.exit(main(sys.argv))


