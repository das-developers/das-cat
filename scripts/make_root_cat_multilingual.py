#!/usr/bin/env python3

import sys
import json

#Das3 uses the "tag:" URI scheme.  Here's and article on it:
#
#  https://www.ibm.com/developerworks/library/x-mxd6/index.html

##############################################################################
# Das2.org Root

g_dDasRoot = {
	"head":{ 
		"uri":"tag:das2.org,2017:/",
		"name":{"_":"das2.org Catalog Root","fr_FR":"das2.org Catalogue de Base",
		       "ja":"ベースカタログ"},
		"type":"DasCatalog", 
		"desc":{
		
			"_": " ".join( """Das2 Catalogs may exist in independent roots, but your site is
			welcome to be linked into this one.  Contact Larry Granroth at the
			University of Iowa to attach your top level das2 node to this catalog 
			set.""".split() ),
	
			"fr_FR": " ".join("""Les catalogues Das2 peuvent exister dans des racines 
			indépendantes, mais pour faciliter l'accès des utilisateurs à vos jeux
			de données, votre site vous permet d'avoir votre catalogue de niveau 
			supérieur lié à celui-ci.  Contactez Larry Granroth à l'Université de 
			l'Iowa pour joindre votre catalogue Das2 au niveau supérieur à ce 
			service.""".split() ),
			
			"ja": " ".join("""Das2 カタログは独立したルーツに存在するかもしれませんが、あなたのサイトは
			これにリンクされることを歓迎します。 Larry Granroth に連絡する University of Iowa
			でトップレベルのdas2ノードをこのカタログセットに添付します。
			""".split() )
		}
	},
	
	"body":{
		
		"PS":{ 
			"head":{
				"uri":"tag:das2.org,2017:/PS/",
				"type":"DasCatalog"	,		
				"name":{"_":"Planetary Sciences Catalog", 
				       "fr_FR":"Catalogue des Sciences Planétaires",
				       "ja":"惑星科学カタログ"},
			},
			#"ptr":["http://das2.org/catalog/PS/"]
			"body":{
				"PPI":{
					"head":{
						"uri":"tag:das2.org,2017:/PS/PPI/",
						"type":"DasCatalog",
						"name": {"_":"Planetary Plasma Interactions",
		                  "fr_FR":"Interactions plasmatiques plasmatiques",
		                  "ja":"惑星プラズマ相互作用"}
					},
					
					"body":{
						"uiowa.edu":{
							"head":{
								"type":"DasCatalog",
								"uri":"tag:das2.org,2017:/PS/PPI/uiowa.edu/",
								"name":{"_":"University of Iowa Space-based Radio Frequency Observations",
								       "fr_FR":"Observations radio fréquences basées sur l'université de l'Iowa",
								       "ja":"アイオワ大学宇宙ベースの電波観測" },
							},
							"ptr":["http://das2.org/catalog/uiowa.json"]
						}
					}
				}
			}
		}
	}
}

##############################################################################
# Namespaces

g_dNamespaces = {
	"head": { 
		"type":"list", 
		"desc":"Root Namespace List",
		"uri":"tag:das2.org,2017:__namespaces__",
		"mod":"2017-08-23T18:35"
	},
	
	"body": {
		"tag:das2.org,2017:": {
			"head":{
				"type":"NameSpace",
				"uri":"tag:das2.org,2017:__namespace__", 
				"name":"Das2 URI Namespace",
				"desc":{
					"_":' '.join('''The Das2 namespace uses paths similar posix
                   filesystem paths.  There is one root for the path tree,
						 it is designated by the empty string.  The '/' character is
						 used to designate separate path nodes.  Borrowing from 
						 common HTTP idioms, the '#' character (fragment identifer)
						 is used to separate sub-components within a node from 
						 node navigation itself.'''.split())
				},
			},
			"body":{
				"pathSep":"/",
				"fragSep":"#",
				"roots":{
			
					"":{
						"head": {
							"uri":g_dDasRoot["head"]["uri"],
							"type":g_dDasRoot["head"]["type"],
							"name":g_dDasRoot["head"]["name"],
							"desc":"Root node for das2 namespace is just the empty string"
						},
						
						'ptr':['http://das2.org/catalog/das.json']
					}
				}
			}
		},
		
		"tag:spase-group.org,2017:" : {
			"head":{
				"type":"NameSpace",
				"uri":"tag:spase-group.org,2017:__namespace__",
				"name":"Spase Metadata Registry", 
				"desc":{"en_US": ' '.join('''The Space Physics Archive Search and 
				Extract (SPASE) effort is a Heliophysics community-based project with 
				the goal of facilitating data search and retrieval across the Space and
				Solar Physics data environment with a common metadata language'''.split())
				}
			},
			"body":{
				'pathSep':'/',
				"fragSep":"#",
				"roots":{
					"spase:/":{
						"head":{
							"uri":"tag:spase-group.org,2017:", 
					      "name":"Spase Metadata Registry", 
					      "type":"SpaseResponse"
					   },
						'ptr':[{'mime':'text/xml', 
						       'url':'http://spase-group.org/registry/resolver?t=yes'
						}]
					}
				}
			}
		},
		
		"tag:cdaweb.sci.gsfc.nasa.gov,2017:" : {
			"head":{
				"type":'NameSpace',
				'uri':'tag:cdaweb.sci.gsfc.nasa.gov,2017:_namespace_',
				'name': 'NASA Goddard Public Data',
				'desc': 'Goddard Spaceflight Center Data Sites'
			},
			'body':{
				'pathSep':';',
				'fragSep':'#',
				'roots':{
					'CDAWeb_FTP':{
						'head':{
							'uri':'tag:cdaweb.sci.gsfc.nasa.gov,2017:CDAWeb_FTP',
							'name':{'_':'Coordinated Data Analysis Web'},
							'desc':{'_':'Data storage for CDAWeb FTP'},
							'type':'SpdfMasterCat'
						},
						'ptr':[{
							'mime':'text/xml', 
							'url':'https://cdaweb.sci.gsfc.nasa.gov/pub/catalogs/all.xml'
						}]					
					},
					'SPDF_FTP':{
						'head':{
							'uri':'tag:cdaweb.sci.gsfc.nasa.gov,2017:CDAWeb_FTP',
							'name':{'_':'Space Physics Data Facility'},
							'desc':{'_':'Data storage for SPDF FTP'},
							'type':'SpdfMasterCat'
						},
						'ptr':[{
							'mime':'text/xml', 
							'url':'https://cdaweb.sci.gsfc.nasa.gov/pub/catalogs/all.xml'
						}]					
					}
				}
			}
		}
	},
	
#	"tag:pds.nasa.gov,2017:" : {
#		'head':{
#			'type':'NameSpace',
#			'uri':'tag:pds.nasa.gov,2017:_namespace_',
#			'name':
#		
#		}
#	
#	
#	}
}
##############################################################################
def main(argv):

	d = None
	if len(argv) < 1:
		d = prnRootLocs()
	else:
		sItem = argv[1]
		if sItem.lower() == "ns":
			d = g_dNamespaces
		elif sItem.lower()	== "das":
			d = g_dDasRoot
		else:
			sys.stderr.write("ERROR: Unknown catalog selected: '%s'\n"%sItem)
			return 4
		
	s = json.dumps(d, ensure_ascii=False, indent="  ", sort_keys=True)
	print(s)

	return 0	

##############################################################################
if __name__ == "__main__":
	sys.exit(main(sys.argv))


