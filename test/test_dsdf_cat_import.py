#!/usr/bin/env python3

"""Unit tests for src/scripts/dsdf_cat_import and cat_override.py.

No network: DSDF text is inline and the one end to end test answers the
importer's HTTP requests from a dict.  Run from anywhere:

   python3 test/test_dsdf_cat_import.py [-v]
"""

import sys
import os
import json
import copy
import types
import shutil
import logging
import tempfile
import unittest

from importlib.machinery import SourceFileLoader

g_sRepo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
imp = SourceFileLoader('dsdf_cat_import', os.path.join(
	g_sRepo, 'src', 'scripts', 'dsdf_cat_import')).load_module()
ovr = imp.cat_override

class Catch(logging.Handler):
	"""Keeps log records so tests can ask what was warned about"""
	def __init__(self):
		logging.Handler.__init__(self)
		self.lMsg = []
	def emit(self, rec):
		self.lMsg.append((rec.levelname, rec.getMessage()))
	def has(self, sLevel, sPart):
		return any((l == sLevel) and (sPart in m) for (l, m) in self.lMsg)

def newLog():
	log = logging.getLogger('test_import')
	log.setLevel(logging.DEBUG)
	log.propagate = False
	for h in list(log.handlers): log.removeHandler(h)
	hdlr = Catch()
	log.addHandler(hdlr)
	return (log, hdlr)

def dsdf(**dKw):
	"""A server=dsdf reply from key=value pairs, escaped as servers do"""
	l = ['[00]000000<stream>\n  <properties']
	for (k, v) in dKw.items():
		v = v.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
		l.append('    %s="%s"'%(k, v))
	l.append(' />\n</stream>')
	return '\n'.join(l)

# The shape of Cassini/RPWS/Survey, cut down
g_dSurvey = dict(
	description='Survey like test source',
	das2Stream='1',
	techContact='T. Tech <tech@example.org>',
	sciContact='S. One <one@example.org>, S. Two',
	validRange='1997-01-03T03:15 to 2017-09-15T10:35',
	coord_00='time | Spacecraft Event Time | UTC',
	coord_01='frequency | Channel Center Frequency | Hz',
	coordRange_01='1 to 16e6 Hz',
	data_00='specdens | Electric Spectral Density | V**2 m**-2 Hz**-1',
	param_00='res_cor | Correct for the antenna resonance | -a',
	param_01='bg_div | Background division | -b @ | range: 1 100',
	param_02='lfdr | LFDR sensors | -lfdr @ | set: NONE Ex Ew',
	paramInfo_02='Choosing sensors replaces the default set',
	paramValInfo_02='Ex: Dipole | Ew: Monopole',
	param_03='mfr | MFR bands and sensors | -mfr @ | set: NONE 1 2 3 Ex Ew',
	param_04='nix | Data to remove | -n @ | set: SPACE bad_data hf1pwr fake_data',
	param_05='no_antlen | Do not apply the antenna length | -n antlen',
	param_06='dft | DFT method | @ | option: fft512 fft3x512',
	paramValInfo_06='fft512: Three DFTs | fft3x512: The average of three',
	param_07='fan | Fans | fan=@ | set: , 090 180 270',
	exampleRange_00='2016-001 to 2016-002 | Standard',
	exampleRange_01='2016-001 to 2016-002 | Everything',
	exampleParams_01='-a -b 5 -lfdr EwEx -mfr 12Ex -n hf1pwr bad_data fft512 -n antlen fan=270,090',
)

g_logQuiet = logging.getLogger('test_import_quiet')
g_logQuiet.propagate = False
g_logQuiet.addHandler(logging.NullHandler())

def props(d):
	"""Parsed DSDF properties, with a logger of its own so a test's
	handler only sees what the function under test says"""
	return imp.parseDsdfProps(g_logQuiet, 'test', dsdf(**d))

##############################################################################

class TestDsdfProps(unittest.TestCase):

	def test_bare_is_00(self):
		(log, hdlr) = newLog()
		d = imp.parseDsdfProps(log, 'u', dsdf(exampleRange='a to b', param_3='x | y', param02='p | q'))
		self.assertEqual(d['exampleRange'], {'00':'a to b'})
		self.assertEqual(d['param'], {'03':'x | y', '02':'p | q'})

	def test_numbered_wins(self):
		(log, hdlr) = newLog()
		d = imp.parseDsdfProps(log, 'u', dsdf(exampleRange='old', exampleRange_00='new'))
		self.assertEqual(d['exampleRange']['00'], 'new')
		self.assertTrue(hdlr.has('WARNING', 'differ'))
		# the same value twice is not worth a warning
		(log, hdlr) = newLog()
		imp.parseDsdfProps(log, 'u', dsdf(exampleRange='same', exampleRange_00='same'))
		self.assertFalse(hdlr.has('WARNING', 'differ'))

	def test_unescape_and_quotes(self):
		(log, hdlr) = newLog()
		d = imp.parseDsdfProps(log, 'u', dsdf(techContact='A <a@b.c>', description='"Quoted"'))
		self.assertEqual(d['techContact']['00'], 'A <a@b.c>')
		self.assertTrue(hdlr.has('WARNING', 'description'))

	def test_same_number_twice(self):
		(log, hdlr) = newLog()
		d = imp.parseDsdfProps(log, 'u', dsdf(param_1='a | A', param_01='b | B'))
		self.assertEqual(d['param'], {'01':'b | B'})
		self.assertTrue(hdlr.has('WARNING', 'given twice'))

	def test_not_a_reply(self):
		(log, hdlr) = newLog()
		self.assertIsNone(imp.parseDsdfProps(log, 'u', 'No such dataset'))
		self.assertTrue(hdlr.has('ERROR', 'start of stream properties'))

class TestParseParam(unittest.TestCase):

	def test_forms(self):
		d = imp.parseParam('00', 'B | Magnetic')
		self.assertEqual((d['kind'], d['sent']), ('switch', 'B'))
		d = imp.parseParam('00', 'p12v | +12V supply | 12.0')
		self.assertEqual((d['kind'], d['sent']), ('switch', '12.0'))
		d = imp.parseParam('00', 'notch | Frequencies | @')
		self.assertEqual((d['kind'], d['prefix']), ('text', ''))
		d = imp.parseParam('00', 'bg | Division | -b @ | range: 1 100')
		self.assertEqual((d['kind'], d['prefix'], d['range']), ('range', '-b ', ('integer', 1, 100)))
		d = imp.parseParam('00', 'f | Freq | f=@ | range: 0 14.4')
		self.assertEqual(d['range'], ('real', 0.0, 14.4))
		d = imp.parseParam('00', 'type | Kind | @ | option: B BINT')
		self.assertEqual((d['kind'], d['elems']), ('enum', ['B', 'BINT']))
		d = imp.parseParam('00', 'lfdr | Sensors | -lfdr @ | set: NONE Ex Ew')
		self.assertEqual((d['kind'], d['subSep'], d['elems']), ('set', '', ['Ex', 'Ew']))
		d = imp.parseParam('00', 'nix | Remove | -n @ | set: SPACE a b')
		self.assertEqual(d['subSep'], ' ')
		d = imp.parseParam('00', 'fan | Fans | fan=@ | set: , 090 180')
		self.assertEqual(d['subSep'], ',')
		d = imp.parseParam('00', 'a | Has a \\| bar | x')
		self.assertEqual(d['title'], 'Has a | bar')

	def test_suffix(self):
		# text after the '@' follows the value; blanks beside the '@' are
		# kept on both sides, as they always were before it
		d = imp.parseParam('00', 'win | Window | --win=@s | range: 0 60')
		self.assertEqual((d['kind'], d['prefix'], d['suffix']), ('range', '--win=', 's'))
		d = imp.parseParam('00', 'pair | Pair | --x @ --y')
		self.assertEqual((d['kind'], d['prefix'], d['suffix']), ('text', '--x ', ' --y'))
		d = imp.parseParam('00', 'bw | Bandwidth | @Hz | option: 10 20')
		self.assertEqual((d['prefix'], d['suffix'], d['elems']), ('', 'Hz', ['10', '20']))
		self.assertEqual(imp.parseParam('00', 'b | Background | -b @')['suffix'], '')

	def test_refused(self):
		for s in (
			'only_token',                               # no title
			'1bad | Title',                             # illegal token
			'a-b | Title',
			'tok |  | x',                               # empty title
			'tok | Title | x | y | z',                  # too many fields
			'tok | Title | -x | option: a b',           # constraint without @
			'tok | Title | @ @',                        # one value per flag
			'tok | Title | --from @ --to @',
			'tok | Title | @ | list: a b',              # unknown constraint
			'tok | Title | @ | a b',                    # no constraint type
			'tok | Title | @ | range: 1',
			'tok | Title | @ | range: a b',
			'tok | Title | @ | option:',
			'tok | Title | @ | option: a a',
			'tok | Title | @ | set: NONE',
			'tok | Title | @ | set: NONE a a',
			'tok | Title | @ | set: SPACE a,b c',       # a comma can't be typed in a list
		):
			with self.assertRaises(imp.DsdfError, msg=s): imp.parseParam('07', s)

class TestParseParams(unittest.TestCase):

	def test_no_params(self):
		(log, hdlr) = newLog()
		self.assertEqual(imp.parseParams(log, 'ds', {}), (None, {}, []))

	def test_survey_like(self):
		(log, hdlr) = newLog()
		(dHttp, dOpts, lDefs) = imp.parseParams(log, 'ds', props(g_dSurvey))
		self.assertEqual(dHttp['type'], 'FlagSet')
		self.assertEqual(dHttp['flagSep'], ' ')
		dF = dHttp['flags']
		self.assertEqual(list(dF), ['res_cor', 'bg_div', 'lfdr', 'mfr', 'nix', 'no_antlen', 'dft', 'fan'])
		self.assertEqual(dF['res_cor'], {'value':'-a', 'comment':'Correct for the antenna resonance'})
		self.assertEqual(dF['bg_div'], {'prefix':'-b ', 'comment':'Background division'})
		# the protocol lists every string the reader is known to take
		# ... and a note for whoever reads that section alone: the DSDF's
		# title and paramInfo, not the per value text
		self.assertEqual(dF['lfdr'], {'prefix':'-lfdr ', 'subSep':'', 'enum':['Ex', 'Ew'],
			'comment':'LFDR sensors.  Choosing sensors replaces the default set'})
		self.assertEqual(dF['mfr']['enum'], ['1', '2', '3', 'Ex', 'Ew'])
		self.assertEqual(dF['nix']['prefix'], '-n ')
		self.assertEqual(dF['nix']['subSep'], ' ')
		self.assertEqual((dF['dft']['prefix'], dF['dft']['enum']), ('', ['fft512', 'fft3x512']))
		self.assertEqual((dF['fan']['prefix'], dF['fan']['subSep'], dF['fan']['enum']), ('fan=', ',', ['090', '180', '270']))
		# user strings are in the interface only
		for d in dF.values():
			self.assertFalse(set(d) - set(('value', 'prefix', 'subSep', 'enum', 'comment')))
			self.assertEqual(list(d)[-1], 'comment')

		# one property per param, a set: is a list
		self.assertEqual(list(dOpts), ['res_cor', 'bg_div', 'lfdr', 'mfr', 'nix', 'no_antlen', 'dft', 'fan'])
		d = dOpts['lfdr']
		self.assertEqual((d['type'], d['multi'], d['value']), ('enum', True, []))
		self.assertEqual(d['set'], {'param':'params', 'flag':'lfdr', 'enum':[
			{'value':'Ex', 'title':'Dipole'}, {'value':'Ew', 'title':'Monopole'}]})
		self.assertEqual(d['description'], 'Choosing sensors replaces the default set')
		self.assertEqual([e['value'] for e in dOpts['mfr']['set']['enum']], ['1', '2', '3', 'Ex', 'Ew'])
		self.assertEqual(dOpts['bg_div']['type'], 'integer')
		self.assertEqual(dOpts['bg_div']['set']['range'], [1, 100])
		# a pick one enum is not a list
		self.assertNotIn('multi', dOpts['dft'])
		self.assertEqual(dOpts['dft']['set']['enum'],
			[{'value':'fft512', 'title':'Three DFTs'}, {'value':'fft3x512', 'title':'The average of three'}])

	def test_option_looking_values(self):
		(log, hdlr) = newLog()
		# reader arguments stay in the protocol, people pick a plain name
		(dHttp, dOpts, lDefs) = imp.parseParams(log, 'ds', props(dict(
			param_00='rate | Sample rate | @ | option: --10khz --80khz',
			paramValInfo_00='--10khz: Low | --80khz: High')))
		self.assertEqual(dHttp['flags']['rate'], {'prefix':'', 'enum':['--10khz', '--80khz'], 'comment':'Sample rate'})
		self.assertEqual(dOpts['rate']['set']['enum'], [
			{'value':'10khz', 'pval':'--10khz', 'title':'Low'},
			{'value':'80khz', 'pval':'--80khz', 'title':'High'}])
		self.assertFalse(hdlr.has('WARNING', ''))
		# an example gives the name, not the argument
		self.assertEqual(imp.splitExampleParams(lDefs, ' ', '--80khz'),
		                 ({'options/props/rate':'80khz'}, ''))

		# only the ones with dashes change
		(dHttp, dOpts, lDefs) = imp.parseParams(log, 'ds', props(dict(
			param_00='mode | Mode | @ | option: all --fast')))
		self.assertEqual(dOpts['mode']['set']['enum'], [{'value':'all'}, {'value':'fast', 'pval':'--fast'}])

		# minus signs are not dashes
		(dHttp, dOpts, lDefs) = imp.parseParams(log, 'ds', props(dict(
			param_00='off | Offset | -o @ | option: -1 0 1')))
		self.assertEqual(dOpts['off']['set']['enum'], [{'value':'-1'}, {'value':'0'}, {'value':'1'}])
		self.assertFalse(hdlr.has('WARNING', ''))

		# names that would collide, or be empty, are left alone and said so
		for sList in ('-a --a', '-- x', '--A -a'):
			(log, hdlr) = newLog()
			(dHttp, dOpts, lDefs) = imp.parseParams(log, 'ds', props(dict(
				param_00='odd | Odd | @ | option: %s'%sList)))
			self.assertEqual([d['value'] for d in dOpts['odd']['set']['enum']], sList.split(), sList)
			self.assertNotIn('pval', dOpts['odd']['set']['enum'][0])
			self.assertTrue(hdlr.has('WARNING', 'look like command line options'), sList)

	def test_refused_and_warned(self):
		(log, hdlr) = newLog()
		with self.assertRaises(imp.DsdfError):     # token twice
			imp.parseParams(log, 'ds', props(dict(param_00='a | A', param_01='a | B')))
		# an element is not part of a property name, so nothing collides
		imp.parseParams(log, 'ds', props(dict(
			param_00='s | S | @ | set: NONE x y', param_01='s_x | No collision')))
		with self.assertRaises(imp.DsdfError):     # value info on a param with no list
			imp.parseParams(log, 'ds', props(dict(param_00='a | A', paramValInfo_00='a: text')))
		with self.assertRaises(imp.DsdfError):     # value info entry with no element
			imp.parseParams(log, 'ds', props(dict(
				param_00='s | S | @ | option: x y', paramValInfo_00='just text')))
		imp.parseParams(log, 'ds', props(dict(
			param_00='s | S | @ | option: x y', paramValInfo_00='z: not there', paramInfo_04='orphan')))
		self.assertTrue(hdlr.has('WARNING', "names 'z'"))
		self.assertTrue(hdlr.has('WARNING', 'paramInfo/paramValInfo_04'))

	def test_param_sep(self):
		(log, hdlr) = newLog()
		(dHttp, dOpts, lDefs) = imp.parseParams(log, 'ds', props(dict(paramSep=',', param_00='a | A')))
		self.assertEqual(dHttp['flagSep'], ',')

class TestSplitExample(unittest.TestCase):

	def setUp(self):
		(log, hdlr) = newLog()
		(self.dHttp, dOpts, self.lDefs) = imp.parseParams(log, 'ds', props(g_dSurvey))
		self.sAll = g_dSurvey['exampleParams_01']

	def test_everything(self):
		(d, sLeft) = imp.splitExampleParams(self.lDefs, ' ', self.sAll)
		self.assertEqual(sLeft, '')
		P = 'options/props/'
		# lists come out in DSDF element order, whatever the example had
		self.assertEqual(d, {
			P+'res_cor':True, P+'bg_div':5, P+'lfdr':['Ex', 'Ew'], P+'mfr':['1', '2', 'Ex'],
			P+'nix':['bad_data', 'hf1pwr'], P+'dft':'fft512',
			P+'no_antlen':True,     # '-n antlen' is the longer match
			P+'fan':['090', '270']})

	def test_flag_given_twice(self):
		(d, sLeft) = imp.splitExampleParams(self.lDefs, ' ', '-n fake_data -n bad_data')
		self.assertEqual((d, sLeft), ({'options/props/nix':['bad_data', 'fake_data']}, ''))

	def test_leftover(self):
		(d, sLeft) = imp.splitExampleParams(self.lDefs, ' ', '-a -z 5')
		self.assertEqual(d, {'options/props/res_cor':True})
		self.assertEqual(sLeft, '-z 5')
		(d, sLeft) = imp.splitExampleParams(self.lDefs, ' ', '-lfdr ExEz')   # Ez is not an element
		self.assertEqual(sLeft, '-lfdr ExEz')
		(d, sLeft) = imp.splitExampleParams(self.lDefs, ' ', '-b five')
		self.assertEqual(sLeft, '-b five')

	def test_repeated_flag(self):
		# only a set: holds several values; anything else given twice would
		# lose the first, so the example is not taken
		(log, hdlr) = newLog()
		(dHttp, dOpts, lDefs) = imp.parseParams(log, 'ds', props(dict(
			param_00='notch | Free text | @', param_01='chan | Channel | -c @ | option: A B')))
		(d, sLeft) = imp.splitExampleParams(lDefs, ' ', '-c A -c B')
		self.assertEqual(sLeft, '-c B')
		(d, sLeft) = imp.splitExampleParams(lDefs, ' ', '2.4 4.8')
		self.assertEqual(sLeft, '4.8')

	def test_suffix(self):
		(log, hdlr) = newLog()
		(dHttp, dOpts, lDefs) = imp.parseParams(log, 'ds', props(dict(
			param_00='win | Window | --win=@s | range: 0.0 60.0',
			param_01='chan | Channels | (@) | set: + a b c',
			param_02='bw | Bandwidth | @Hz | option: 10 20',
			param_03='pair | Pair | --x @ --y',
			param_04='plain | No suffix | -p @')))
		dF = dHttp['flags']
		# the flag has the text on both sides, the list what goes between
		self.assertEqual(dF['win'], {'prefix':'--win=', 'suffix':'s', 'comment':'Window'})
		self.assertEqual(dF['chan'], {'prefix':'(', 'suffix':')', 'subSep':'+',
			'enum':['a', 'b', 'c'], 'comment':'Channels'})
		self.assertEqual(dF['bw'], {'prefix':'', 'suffix':'Hz', 'enum':['10', '20'], 'comment':'Bandwidth'})
		self.assertEqual(dF['pair']['suffix'], ' --y')
		self.assertNotIn('suffix', dF['plain'])

		# and an example's params come back apart at the same places
		P = 'options/props/'
		(d, sLeft) = imp.splitExampleParams(lDefs, ' ', '--win=2.5s (c+a) 20Hz --x 7 --y -p q')
		self.assertEqual((d, sLeft), ({P+'win':2.5, P+'chan':['a', 'c'], P+'bw':'20',
			P+'pair':'7', P+'plain':'q'}, ''))
		# the value has to be whole and the suffix has to be there
		self.assertEqual(imp.splitExampleParams(lDefs, ' ', '--win=2.5')[1], '--win=2.5')
		self.assertEqual(imp.splitExampleParams(lDefs, ' ', '(a+d)')[1], '(a+d)')
		self.assertEqual(imp.splitExampleParams(lDefs, ' ', '30Hz')[1], '30Hz')
		# a suffix letter inside the value is not the end of it
		(log, hdlr) = newLog()
		(dHttp, dOpts, lDefs) = imp.parseParams(log, 'ds', props(dict(
			param_00='name | Name | n=@s')))
		self.assertEqual(imp.splitExampleParams(lDefs, ' ', 'n=sensors'),
			({P+'name':'sensor'}, ''))

	def test_bare_words(self):
		(log, hdlr) = newLog()
		(dHttp, dOpts, lDefs) = imp.parseParams(log, 'ds', props(dict(
			param_00='type | Kind | @ | option: B BINT',
			param_01='notch | Free text | @',
			param_02='keep | Keep spikes | KEEP-SPIKES')))
		(d, sLeft) = imp.splitExampleParams(lDefs, ' ', 'KEEP-SPIKES BINT 2.4')
		# a listed word goes to its list, an unlisted one to the free text
		self.assertEqual(d, {'options/props/keep':True, 'options/props/type':'BINT',
		                     'options/props/notch':'2.4'})
		self.assertEqual(sLeft, '')

class TestBuildSource(unittest.TestCase):

	def build(self, d):
		(log, hdlr) = newLog()
		dSrc = imp.buildSource(log, 'Test/Ds', props(d), ['https://a.example/s?server=dataset&dataset=Test/Ds'])
		return (dSrc, hdlr)

	def test_survey_like(self):
		(dSrc, hdlr) = self.build(g_dSurvey)
		self.assertEqual(imp.checkSource(dSrc), [])
		self.assertEqual(dSrc['type'], 'HttpStreamSrc')
		self.assertEqual(dSrc['title'], 'Survey like test source')
		self.assertEqual(dSrc['contacts'], [
			{'type':'scientific', 'name':'S. One', 'email':'one@example.org'},
			{'type':'scientific', 'name':'S. Two'},
			{'type':'technical', 'name':'T. Tech', 'email':'tech@example.org'}])
		dP = dSrc['protocol']
		self.assertEqual(dP['authorization'], {'required':False})
		self.assertEqual(list(dP['httpParams']), ['start_time', 'end_time', 'resolution', 'ascii', 'params'])
		# the fixed das2 parameters say what a server does with them
		self.assertEqual(dP['httpParams']['end_time'], {'required':True, 'type':'isotime',
			'comment':"The exclusive upper bound required of the subset, may be larger at the server's option"})
		self.assertIn('coarsest time resolution', dP['httpParams']['resolution']['comment'])
		for sParam in ('start_time', 'end_time', 'resolution', 'ascii'):
			self.assertEqual(list(dP['httpParams'][sParam])[-1], 'comment')
		dI = dSrc['interface']
		self.assertEqual(list(dI), ['coords', 'data', 'formats', 'options', 'examples'])
		self.assertEqual(dI['coords']['time']['title'], 'Spacecraft Event Time')
		self.assertEqual(dI['coords']['time']['validRange'], ['1997-01-03T03:15', '2017-09-15T10:35'])
		self.assertEqual(dI['coords']['frequency']['validRange'], [1, 16e6])
		self.assertEqual(dI['data']['specdens']['props']['units'], {'value':'V**2 m**-2 Hz**-1'})
		self.assertEqual(list(dI['formats']), ['das2'])
		self.assertEqual(len(dI['examples']), 2)
		# 2000 points across one day
		self.assertEqual(dI['examples'][0]['settings']['coords/time/props/res'], 43.2)
		self.assertEqual(dI['examples'][1]['label'], 'Everything')

	def test_interval_qstream_realm(self):
		(dSrc, hdlr) = self.build(dict(
			description='Ephemeris', qstream='1', requiresInterval='1',
			securityRealm='Team', exampleRange_00='2020-01-01 to 2020-01-02',
			exampleInterval_00='60', usagePolicy='Ask First', usagePolicyUrl='https://x.example/p'))
		self.assertEqual(dSrc['protocol']['authorization'], {'required':True, 'realm':'Team'})
		self.assertIn('interval', dSrc['protocol']['httpParams'])
		self.assertEqual(dSrc['protocol']['httpParams']['interval']['comment'],
		                 'The time between model sample points')
		self.assertNotIn('resolution', dSrc['protocol']['httpParams'])
		self.assertEqual(list(dSrc['interface']['formats']), ['qstream'])
		self.assertEqual(dSrc['interface']['examples'][0]['settings']['coords/time/props/interval'], 60)
		self.assertEqual(dSrc['usage'], {'policy':'Ask First', 'url':'https://x.example/p'})
		self.assertNotIn('options', dSrc['interface'])

	def test_examples_dropped(self):
		(dSrc, hdlr) = self.build(dict(
			param_00='a | A', exampleRange_00='2020-01-01 2020-01-02',
			exampleRange_01='2020-01-01 to 2020-01-02', exampleParams_01='b'))
		self.assertNotIn('examples', dSrc['interface'])
		self.assertTrue(hdlr.has('WARNING', "not 'begin to end'"))
		self.assertTrue(hdlr.has('WARNING', 'matches no param'))
		self.assertTrue(hdlr.has('WARNING', 'no usable examples'))

	def test_bad_names(self):
		(log, hdlr) = newLog()
		with self.assertRaises(imp.DsdfError):
			imp.buildSource(log, 'd', props(dict(item_00='"phi | Angle')), ['u'])
		with self.assertRaises(imp.DsdfError):
			imp.buildSource(log, 'd', props(dict(coord_01='f | Freq | Hz', coordRange_01='lots')), ['u'])

class TestHashAndCheck(unittest.TestCase):

	def test_hash(self):
		d = props(g_dSurvey)
		s = imp.dsdfHash(d)
		self.assertRegex(s, r'^sha256:[0-9a-f]{16}$')
		# what an override does not depend on does not move the hash
		d2 = props(dict(g_dSurvey, techContact='New Person <n@example.org>',
		                description='Reworded', validRange='1997-01-01 to now',
		                cacheLevel_01='60 s | daily'))
		self.assertEqual(imp.dsdfHash(d2), s)
		# what it does depend on does
		for (k, v) in (('param_08', 'new | New switch'), ('paramValInfo_02', 'Ex: Other | Ew: Monopole'),
		               ('exampleRange_02', '2017-001 to 2017-002'), ('data_01', 'b | B | nT')):
			self.assertNotEqual(imp.dsdfHash(props(dict(g_dSurvey, **{k:v}))), s, k)
		# one value holding a newline is not two lines
		self.assertNotEqual(
			imp.dsdfHash({'paramInfo':{'00':'x\nparamInfo_01=y'}}),
			imp.dsdfHash({'paramInfo':{'00':'x', '01':'y'}}))

	def test_check(self):
		(log, hdlr) = newLog()
		dSrc = imp.buildSource(log, 'd', props(g_dSurvey), ['u'])
		self.assertEqual(imp.checkSource(dSrc), [])

		d = copy.deepcopy(dSrc)
		d['interface']['options']['props']['lfdr']['set']['flag'] = 'gone'
		self.assertIn("flag 'gone'", imp.checkSource(d)[0])

		d = copy.deepcopy(dSrc)
		d['interface']['options']['props']['lfdr']['set']['param'] = 'nope'
		self.assertIn('not a protocol parameter', imp.checkSource(d)[0])

		d = copy.deepcopy(dSrc)
		del d['protocol']['httpParams']['params']['flags']['lfdr']['subSep']
		self.assertIn('exactly one of subSep and repeat', imp.checkSource(d)[0])

		d = copy.deepcopy(dSrc)
		d['interface']['options']['props']['lfdr']['value'] = 'Ex'
		self.assertIn('a single value, it takes a list', imp.checkSource(d)[0])

		d = copy.deepcopy(dSrc)
		d['interface']['examples'][1]['settings']['options/props/lfdr'] = 'Ex'
		self.assertIn('takes a list', imp.checkSource(d)[0])

		d = copy.deepcopy(dSrc)
		d['interface']['examples'][0]['settings']['options/props/removed'] = True
		self.assertIn('not a settable property', imp.checkSource(d)[0])

		d = copy.deepcopy(dSrc)
		d['interface']['data']['bad-name'] = {'label':'x'}
		self.assertIn('not a legal name', imp.checkSource(d)[0])

		# a default or an example the property can't take
		d = copy.deepcopy(dSrc)
		d['interface']['examples'][1]['settings']['options/props/lfdr'] = ['Ex', 'Ez']
		self.assertIn("'Ez', which is not one of its choices", imp.checkSource(d)[0])
		d = copy.deepcopy(dSrc)
		d['interface']['examples'][1]['settings']['options/props/bg_div'] = 'five'
		self.assertIn('it is an integer', imp.checkSource(d)[0])
		d = copy.deepcopy(dSrc)
		d['interface']['options']['props']['lfdr']['multi'] = [2, 2]
		d['interface']['options']['props']['lfdr']['value'] = ['Ex']
		self.assertIn('1 items, it takes 2 to 2', imp.checkSource(d)[0])
		d = copy.deepcopy(dSrc)
		d['interface']['options']['props']['dft']['value'] = 'fft1024'
		self.assertIn('not one of its choices', imp.checkSource(d)[0])

		# each chosen item a switch of its own: nothing has to join
		d = copy.deepcopy(dSrc)
		d['protocol']['httpParams']['params']['flags'].update({'quiet':{'value':'-q'}, 'loud':{'value':'-v'}})
		d['interface']['options']['props']['verbosity'] = {'type':'enum', 'multi':True, 'value':[],
			'set':{'param':'params', 'enum':[{'value':'quiet', 'flag':'quiet'}, {'value':'loud', 'flag':'loud'}]}}
		self.assertEqual(imp.checkSource(d), [])
		del d['interface']['options']['props']['verbosity']['set']['enum'][1]['flag']
		self.assertIn('exactly one of subSep and repeat', imp.checkSource(d)[0])

		# whatever an override leaves behind is a finding, not a traceback
		for (sPath, val) in (('interface/data/specdens', 'text'), ('interface/formats', {}),
		                     ('interface/examples', ['text']), ('interface', [])):
			d = copy.deepcopy(dSrc)
			dAt = d
			for sTok in sPath.split('/')[:-1]: dAt = dAt[sTok]
			dAt[sPath.split('/')[-1]] = val
			self.assertEqual(len(imp.checkSource(d)), 1, sPath)

		# a switch on a joining flag has to name its element, and the
		# element has to be one the protocol lists
		d = copy.deepcopy(dSrc)
		d['interface']['options']['props']['lfdr_Ex'] = {'type':'boolean', 'value':False,
			'set':{'param':'params', 'flag':'lfdr', 'value':True, 'pval':'Ex'}}
		self.assertEqual(imp.checkSource(d), [])
		d['interface']['options']['props']['lfdr_Ex']['set']['pval'] = 'Ez'
		self.assertIn("sends 'Ez', which the protocol does not list", imp.checkSource(d)[0])
		del d['interface']['options']['props']['lfdr_Ex']['set']['pval']
		self.assertIn('needs a pval', imp.checkSource(d)[0])

	def test_check_proto_enum(self):
		"""Where the protocol lists its strings the interface sends no others"""
		(log, hdlr) = newLog()
		dSrc = imp.buildSource(log, 'd', props(dict(g_dSurvey,
			param_08='rate | Sample rate | @ | option: --10khz --80khz',
			param_09='frame | Output frame, default SYS3 | @ | option: IRC JSE')), ['u'])
		self.assertEqual(imp.checkSource(dSrc), [])
		dFlags = dSrc['protocol']['httpParams']['params']['flags']
		dOpts = dSrc['interface']['options']['props']

		# an item, by what it sends: its pval, else its value
		d = copy.deepcopy(dSrc)
		d['interface']['options']['props']['rate']['set']['enum'][1]['pval'] = '--90khz'
		self.assertIn("offers '80khz', which sends '--90khz'", imp.checkSource(d)[0])
		d = copy.deepcopy(dSrc)
		d['interface']['options']['props']['mfr']['set']['enum'].append({'value':'Bx'})
		self.assertIn("offers 'Bx', which sends 'Bx'", imp.checkSource(d)[0])
		d = copy.deepcopy(dSrc)
		d['protocol']['httpParams']['params']['flags']['dft']['enum'].remove('fft512')
		self.assertIn("offers 'fft512'", imp.checkSource(d)[0])

		# the protocol may list more than the interface shows
		d = copy.deepcopy(dSrc)
		del d['interface']['options']['props']['mfr']['set']['enum'][2]
		self.assertEqual(imp.checkSource(d), [])

		# the default the server gives for a request that says nothing has
		# no string to list
		d = copy.deepcopy(dSrc)
		dP = d['interface']['options']['props']['frame']
		dP['set']['enum'].insert(0, {'value':'SYS3'})
		self.assertIn("offers 'SYS3'", imp.checkSource(d)[0])
		dP['value'] = 'SYS3'
		self.assertEqual(imp.checkSource(d), [])
		# but not if it would have to be sent
		dP['set']['required'] = True
		self.assertIn("offers 'SYS3'", imp.checkSource(d)[0])
		d = copy.deepcopy(dSrc)
		dP = d['interface']['options']['props']['lfdr']
		dP['set']['enum'].insert(0, {'value':'Eu'})
		dP['value'] = ['Eu']
		self.assertIn("offers 'Eu'", imp.checkSource(d)[0])

		# typed values, in a default or an example, are held to a list too
		d = copy.deepcopy(dSrc)
		d['protocol']['httpParams']['params']['flags']['bg_div']['enum'] = ['5', '50']
		self.assertEqual(imp.checkSource(d), [])
		d['interface']['options']['props']['bg_div']['value'] = 7
		self.assertIn("has the value '7', which the protocol does not list", imp.checkSource(d)[0])
		del d['interface']['options']['props']['bg_div']['value']
		d['interface']['examples'][1]['settings']['options/props/bg_div'] = 6
		self.assertIn("example 1 gives options/props/bg_div '6'", imp.checkSource(d)[0])

		# a switch has its one value, a list goes with a prefix
		d = copy.deepcopy(dSrc)
		d['protocol']['httpParams']['params']['flags']['res_cor']['enum'] = ['-a']
		self.assertIn('has both value and enum', imp.checkSource(d)[0])

##############################################################################

class TestOverrideOps(unittest.TestCase):

	def doc(self):
		return {'a':{'x':1, 'y':2, 'z':3}, 'l':[10, 20, 30],
		        'interface':{'options':{'props':{'p1':{'t':'T1'}, 'p2':{'t':'T2'}}},
		                     'examples':[{'settings':{'options/props/p1':True, 'coords/time/props/min':'m'}}]}}

	def test_rfc_ops(self):
		d = self.doc()
		ovr.applyOps(d, [
			{'op':'add', 'path':'/a/w', 'value':0},
			{'op':'add', 'path':'/l/1', 'value':15},
			{'op':'add', 'path':'/l/-', 'value':40},
			{'op':'replace', 'path':'/a/y', 'value':'two'},
			{'op':'remove', 'path':'/a/z'},
			{'op':'copy', 'from':'/a/x', 'path':'/b/x2'},     # parent made on demand
			{'op':'test', 'path':'/l', 'value':[10, 15, 20, 30, 40]},
			{'op':'test', 'path':'/a/y', 'value':'two'},
		])
		self.assertEqual(list(d['a'].items()), [('x', 1), ('y', 'two'), ('w', 0)])
		self.assertEqual(d['b'], {'x2':1})

	def test_placement(self):
		d = self.doc()
		ovr.applyOps(d, [
			{'op':'add', 'path':'/a/first', 'value':0, 'before':'x'},
			{'op':'add', 'path':'/a/mid', 'value':0, 'after':'x'},
			{'op':'move', 'from':'/a/z', 'path':'/a/zed'},               # rename in place
			{'op':'move', 'from':'/a/y', 'path':'/a/y'},                 # onto itself, stays
			{'op':'add', 'path':'/a/x', 'value':'one'},                  # replace keeps place
		])
		self.assertEqual(list(d['a']), ['first', 'x', 'mid', 'y', 'zed'])
		self.assertEqual(d['a']['x'], 'one')
		ovr.applyOps(d, [{'op':'move', 'from':'/a/zed', 'path':'/a/zed2', 'before':'first'}])
		self.assertEqual(list(d['a'])[0], 'zed2')
		# onto itself with a placement is how a member is reordered
		ovr.applyOps(d, [{'op':'move', 'from':'/a/y', 'path':'/a/y', 'before':'zed2'}])
		self.assertEqual(list(d['a']), ['y', 'zed2', 'first', 'x', 'mid'])

	def test_wildcard_and_settings(self):
		d = self.doc()
		ovr.applyOps(d, [
			{'op':'move', 'from':'/interface/options/props/*', 'path':'/interface/data/*/props/enabled'},
			{'op':'move', 'from':'/interface/data/*/props/enabled/t', 'path':'/interface/data/*/title', 'before':'props'},
			{'op':'remove', 'path':'/interface/options'},
			{'op':'add', 'path':'/interface/data/*/props/enabled/type', 'value':'boolean'},
		])
		self.assertEqual(d['interface']['data'], {
			'p1':{'title':'T1', 'props':{'enabled':{'type':'boolean'}}},
			'p2':{'title':'T2', 'props':{'enabled':{'type':'boolean'}}}})
		# the example follows the property, in place
		self.assertEqual(list(d['interface']['examples'][0]['settings'].items()),
			[('data/p1/props/enabled', True), ('coords/time/props/min', 'm')])

	def test_failures(self):
		for dOp in (
			{'op':'test', 'path':'/a/x', 'value':2},
			{'op':'remove', 'path':'/a/nope'},
			{'op':'replace', 'path':'/a/nope', 'value':1},
			{'op':'move', 'from':'/a/nope', 'path':'/a/n2'},
			{'op':'move', 'from':'/a', 'path':'/a/x/in'},
			{'op':'add', 'path':'/l/9', 'value':1},
			{'op':'add', 'path':'/l/01', 'value':1},
			{'op':'add', 'path':'/a/x/deeper', 'value':1},
			{'op':'add', 'path':'/a/n', 'value':1, 'before':'nope'},
			{'op':'add', 'path':'a/n', 'value':1},
			{'op':'remove', 'path':'/empty/*'},
			{'op':'remove', 'path':'/l/*'},
			{'op':'copy', 'from':'/a/x', 'path':'/a/*'},
			{'op':'move', 'from':'/a/*/q/*', 'path':'/b/*'},
			{'op':'remove', 'path':''},
			{'op':'move', 'from':'/a/*', 'path':'/b/only'},       # all onto one target
			{'op':'copy', 'from':'/a/*', 'path':'/a/y'},
			{'op':'move', 'from':'/nope', 'path':'/nope'},        # onto itself, but not there
			{'op':'test', 'path':'/a/x', 'value':True},           # 1 is not true
			{'op':'test', 'path':'/l', 'value':[10, 20, 30.5]},
			{'op':'add', 'path':'/l/\u00b2', 'value':1},          # superscript two is no index
			{'op':'replace', 'path':'/interface/examples/0/settings/nope', 'value':[]},
		):
			d = self.doc()
			d['empty'] = {}
			with self.assertRaises(ovr.OverrideError, msg=str(dOp)): ovr.applyOps(d, [dOp])

	def test_wildcard_append(self):
		d = self.doc()
		ovr.applyOps(d, [{'op':'copy', 'from':'/a/*', 'path':'/l/-'}])
		self.assertEqual(d['l'], [10, 20, 30, 1, 2, 3])

	def test_json_equality(self):
		d = {'a':1, 'b':1.0, 'c':[True, {'x':None}], 'd':'1'}
		ovr.applyOps(d, [
			{'op':'test', 'path':'/a', 'value':1.0},              # numbers compare as numbers
			{'op':'test', 'path':'/c', 'value':[True, {'x':None}]},
		])
		for dOp in ({'op':'test', 'path':'/a', 'value':True},
		            {'op':'test', 'path':'/c', 'value':[1, {'x':None}]},
		            {'op':'test', 'path':'/d', 'value':1}):
			with self.assertRaises(ovr.OverrideError, msg=str(dOp)): ovr.applyOps(d, [dOp])

	def test_settings_follow(self):
		def doc():
			return {'interface':{
				'data':{'a':{'props':{'enabled':{}}}, 'b':{'props':{'enabled':{}}}},
				'options':{'props':{'p':{}, 'q':{}}},
				'examples':[{'settings':{'options/props/p':'MOVED', 'options/props/q':'GONE',
				                         'data/a/props/enabled':True}}]}}
		# onto an existing property: the moved one's setting is the one kept
		d = doc()
		ovr.applyOps(d, [{'op':'move', 'from':'/interface/options/props/p', 'path':'/interface/options/props/q'}])
		self.assertEqual(d['interface']['examples'][0]['settings'],
		                 {'options/props/q':'MOVED', 'data/a/props/enabled':True})
		# a whole group, and a swap through a spare name
		d = doc()
		ovr.applyOps(d, [
			{'op':'move', 'from':'/interface/data/a', 'path':'/interface/data/t'},
			{'op':'move', 'from':'/interface/data/b', 'path':'/interface/data/a'},
			{'op':'move', 'from':'/interface/data/t', 'path':'/interface/data/b'},
		])
		self.assertIn('data/b/props/enabled', d['interface']['examples'][0]['settings'])
		self.assertNotIn('data/a/props/enabled', d['interface']['examples'][0]['settings'])
		# a section
		d = doc()
		ovr.applyOps(d, [{'op':'move', 'from':'/interface/options/props', 'path':'/interface/data/x/props'}])
		self.assertEqual(list(d['interface']['examples'][0]['settings']),
		                 ['data/x/props/p', 'data/x/props/q', 'data/a/props/enabled'])
		# the key follows at the move, a later op's rewrite is not touched again
		d = doc()
		ovr.applyOps(d, [
			{'op':'move', 'from':'/interface/options/props/p', 'path':'/interface/options/props/r'},
			{'op':'replace', 'path':'/interface/examples/0/settings', 'value':{'options/props/p':'literal'}},
		])
		self.assertEqual(d['interface']['examples'][0]['settings'], {'options/props/p':'literal'})

	def test_error_names_the_op(self):
		with self.assertRaises(ovr.OverrideError) as cm:
			ovr.applyOps(self.doc(), [{'op':'test', 'path':'/a/x', 'value':1},
			                          {'op':'remove', 'path':'/a/nope'}])
		self.assertIn('op 1 (remove)', str(cm.exception))
		self.assertIn('/a/nope', str(cm.exception))

	def test_pointer_escapes(self):
		d = {'a/b':{'c~d':1}}
		ovr.applyOps(d, [{'op':'replace', 'path':'/a~1b/c~0d', 'value':2}])
		self.assertEqual(d, {'a/b':{'c~d':2}})

class TmpCase(unittest.TestCase):
	"""Tests that write files, in a scratch directory under $TMPDIR"""
	def setUp(self):
		self.sDir = tempfile.mkdtemp(prefix='test_import_')
	def tearDown(self):
		shutil.rmtree(self.sDir, ignore_errors=True)
	def write(self, sRel, sText):
		sPath = os.path.join(self.sDir, sRel)
		os.makedirs(os.path.dirname(sPath), exist_ok=True)
		with open(sPath, 'w', encoding='utf-8') as f: f.write(sText)
		return sPath
	def read(self, sRel):
		with open(os.path.join(self.sDir, sRel), encoding='utf-8') as f: return json.load(f)

class TestOverrideFile(TmpCase):

	def test_load(self):
		s = self.write('ok.json5', '''{
			// comments and trailing commas are fine
			"dataset": "A/B", "dsdf": "sha256:0000000000000000",
			"ops": [ {"op": "remove", "path": "/x"}, ],
		}''')
		d = ovr.loadOverride(s)
		self.assertEqual((d['dataset'], d['dsdf'], d['urlChange']),
		                 ('A/B', 'sha256:0000000000000000', None))

	def test_refused(self):
		for (i, s) in enumerate((
			'{"ops": []}',                                             # no ops
			'{"ops": [{"op": "delete", "path": "/x"}]}',               # not an op
			'{"ops": [{"op": "add", "path": "/x"}]}',                  # add without value
			'{"ops": [{"op": "move", "path": "/x"}]}',                 # move without from
			'{"ops": [{"op": "remove", "path": "/x", "value": 1}]}',   # stray member
			'{"ops": [{"op": "add", "path": "/x", "value": 1, "before": "a", "after": "b"}]}',
			'{"form": "multi", "ops": [{"op": "remove", "path": "/x"}]}',   # a member that is gone
			'{"why": "x", "ops": [{"op": "remove", "path": "/x"}]}',   # unknown member
			'{"ops": [{"op": "remove", "path": "/x"}], "ops": []}',    # duplicate key
			'{ops: [{"op": "remove", "path": "/x"}]}',                 # more JSON5 than we read
			'{"ops": [{"op": "add", "path": "/x", "value": 1, "before": ["a"]}]}',
			'{"ops": [{"op": "remove", "path": 7}]}',
			'{"dataset": 7, "ops": [{"op": "remove", "path": "/x"}]}',
			'[1]',
		)):
			with self.assertRaises(ovr.OverrideError, msg=s):
				ovr.loadOverride(self.write('bad%d.json5'%i, s))
		with self.assertRaises(ovr.OverrideError):
			ovr.loadOverride(os.path.join(self.sDir, 'missing.json5'))

##############################################################################
# End to end, with a pretend pair of servers

g_sA = 'https://a.example/das/server'
g_sB = 'https://b.example/das/server'

class FakeRequests(object):
	"""Stands in for the requests module.  dSrv is {server URL: {dataset:
	DSDF properties}}; lists and ids are made from it."""
	RequestException = Exception
	codes = types.SimpleNamespace(ok=200)

	def __init__(self, dSrv):
		self.dSrv = dSrv
		self.lAsked = []

	def get(self, sUrl, timeout=None):
		self.lAsked.append(sUrl)
		(sBase, sQuery) = sUrl.split('?', 1)
		dQ = dict(s.split('=', 1) for s in sQuery.split('&'))
		dSets = self.dSrv[sBase]
		if dQ['server'] == 'id': return types.SimpleNamespace(status_code=200, text='Test Server\n')
		if dQ['server'] == 'list':
			lDirs = sorted(set('/'.join(s.split('/')[:i]) + '/' for s in dSets for i in range(1, s.count('/') + 1)))
			lLines = ['%s|Directory %s'%(s, s) for s in lDirs]
			lLines += ['%s|%s'%(s, d.get('description', '')) for (s, d) in dSets.items()]
			return types.SimpleNamespace(status_code=200, text='\n'.join(sorted(lLines)) + '\n')
		if dQ['dataset'] not in dSets: return types.SimpleNamespace(status_code=404, text='')
		return types.SimpleNamespace(status_code=200, text=dsdf(**dSets[dQ['dataset']]))

g_dSimple = dict(description='Simple source', das2Stream='1', exampleRange_00='2020-01-01 to 2020-01-02')
g_dHsk = dict(description='Fields', qstream='1', exampleRange_00='2020-01-01 to 2020-01-02',
              exampleParams_00='12.0', param_01='p12v | +12V supply | 12.0', param_02='n5v | -5V supply | -5.00')

class TestRun(TmpCase):

	def run_import(self, dSrv, lArgs, sOut='out'):
		self.fake = FakeRequests(dSrv)
		imp.requests = self.fake
		(log, self.hdlr) = newLog()
		sSave = imp.setupLogger
		imp.setupLogger = lambda sLevel, sName: log
		try:
			return imp.main(['dsdf_cat_import'] + lArgs + [
				'https://cat.example/site/test.json', os.path.join(self.sDir, sOut)])
		finally:
			imp.setupLogger = sSave

	def test_tree_and_mirrors(self):
		dSrv = {
			g_sA: {'Mission/Inst/Survey':g_dSurvey, 'Mission/Inst/Simple':g_dSimple},
			g_sB: {'Mission/Inst/Survey':dict(g_dSurvey, description='Drifted'),
			       'Mission/Other':g_dSimple, 'Mission/em/Ground':g_dSimple,
			       'Mission/emfisis/Flight':g_dSimple, 'Mission/Test/Scratch':g_dSimple},
		}
		nRet = self.run_import(dSrv, ['-e', 'Mission/em', '-m', g_sB, g_sA, '/'])
		self.assertEqual(nRet, 0)

		dRoot = self.read('out/test.json')
		self.assertEqual((dRoot['type'], dRoot['title']), ('Catalog', 'Test Server'))
		self.assertEqual(dRoot['catalog']['mission']['urls'], ['https://cat.example/site/test/mission.json'])
		dM = self.read('out/test/mission.json')
		# em is excluded, emfisis is not; test directories are never written
		self.assertEqual(sorted(dM['catalog']), ['emfisis', 'inst', 'other'])

		dSet = self.read('out/test/mission/inst/survey.json')
		self.assertEqual(dSet['type'], 'SourceSet')
		self.assertEqual(dSet['catalog']['das2']['urls'],
		                 ['https://cat.example/site/test/mission/inst/survey/das2.json'])
		self.assertEqual(dSet['contacts'], [
			{'type':'scientific', 'name':'S. One', 'email':'one@example.org'},
			{'type':'scientific', 'name':'S. Two'}])
		dSrc = self.read('out/test/mission/inst/survey/das2.json')
		# first server's content, both servers as base URLs, in order
		self.assertEqual(dSrc['title'], 'Survey like test source')
		self.assertEqual(dSrc['protocol']['baseUrls'], [
			g_sA + '?server=dataset&dataset=Mission/Inst/Survey',
			g_sB + '?server=dataset&dataset=Mission/Inst/Survey'])
		self.assertTrue(self.hdlr.has('WARNING', 'differs from'))
		dOther = self.read('out/test/mission/other/das2.json')
		self.assertEqual(dOther['protocol']['baseUrls'], [g_sB + '?server=dataset&dataset=Mission/Other'])

		# a second run changes nothing and says so
		tStat = os.stat(os.path.join(self.sDir, 'out/test/mission/inst/survey/das2.json')).st_mtime_ns
		self.assertEqual(self.run_import(dSrv, ['-e', 'Mission/em', '-m', g_sB, g_sA, '/']), 0)
		self.assertEqual(tStat, os.stat(os.path.join(self.sDir, 'out/test/mission/inst/survey/das2.json')).st_mtime_ns)

	def test_no_op_and_subtree(self):
		dSrv = {g_sA: {'Mission/Inst/Survey':g_dSurvey, 'Mission/Inst/Simple':g_dSimple, 'Other/Thing':g_dSimple}}
		self.assertEqual(self.run_import(dSrv, ['-n', g_sA, '/']), 0)
		self.assertFalse(os.path.exists(os.path.join(self.sDir, 'out')))

		# OUT_DIR is where the SRV_PATH node goes, nothing above it is written
		self.assertEqual(self.run_import(dSrv, [g_sA, 'Mission/Inst'], 'sub'), 0)
		self.assertEqual(sorted(os.listdir(os.path.join(self.sDir, 'sub'))), ['inst', 'inst.json'])
		self.assertEqual(self.run_import(dSrv, [g_sA, 'Nope'], 'sub2'), 13)

	def test_bad_dsdf_is_skipped(self):
		dSrv = {g_sA: {'M/Good':g_dSimple, 'M/Bad':dict(g_dSimple, param_00='1bad | Illegal token')}}
		self.assertEqual(self.run_import(dSrv, [g_sA, '/']), 5)
		self.assertEqual(sorted(self.read('out/test/m.json')['catalog']), ['good'])
		self.assertTrue(self.hdlr.has('ERROR', 'M/Bad'))

	def test_broken_later_stays_listed(self):
		# A dataset that converted once and then breaks keeps its old node
		# and its place in the parent, the published catalog does not shrink
		dSrv = {g_sA: {'M/Good':g_dSimple, 'M/Flaky':dict(g_dSimple, description='Was fine')}}
		self.assertEqual(self.run_import(dSrv, [g_sA, '/']), 0)
		dSrv[g_sA]['M/Flaky'] = dict(g_dSimple, description='Now broken', param_00='1bad | Illegal token')
		self.assertEqual(self.run_import(dSrv, [g_sA, '/']), 5)
		dM = self.read('out/test/m.json')
		self.assertEqual(sorted(dM['catalog']), ['flaky', 'good'])
		self.assertEqual(dM['catalog']['flaky']['title'], 'Was fine')
		self.assertEqual(self.read('out/test/m/flaky/das2.json')['title'], 'Was fine')
		self.assertTrue(self.hdlr.has('WARNING', 'keeping the node already in'))

	def test_name_collisions(self):
		# one lower cased name space per directory, first come first kept,
		# and the loser is stopped before it can overwrite anything
		dSrv = {g_sA: {'M/Survey':dict(g_dSimple, description='First'),
		               'M/survey':dict(g_dSimple, description='Second'),
		               'M/Deep/Leaf':g_dSimple, 'M/deep':dict(g_dSimple, description='Dataset named as a dir')}}
		self.assertEqual(self.run_import(dSrv, [g_sA, '/']), 5)
		self.assertEqual(self.read('out/test/m/survey/das2.json')['title'], 'First')
		self.assertEqual(self.read('out/test/m/survey.json')['title'], 'First')
		self.assertEqual(self.read('out/test/m/deep.json')['type'], 'Catalog')
		self.assertTrue(os.path.isfile(os.path.join(self.sDir, 'out/test/m/deep/leaf/das2.json')))
		self.assertFalse(os.path.exists(os.path.join(self.sDir, 'out/test/m/deep/das2.json')))
		self.assertTrue(self.hdlr.has('ERROR', 'M/survey is not written'))
		self.assertTrue(self.hdlr.has('ERROR', 'M/deep is not written'))

	def test_exclusion_that_matches_nothing(self):
		dSrv = {g_sA: {'M/Good':g_dSimple}}
		self.assertEqual(self.run_import(dSrv, ['-e', 'm/good', g_sA, '/']), 0)
		self.assertTrue(self.hdlr.has('WARNING', "Exclusion 'm/good' matches nothing"))

	def override(self, sDs, sHash, sOps, sExtra=''):
		return self.write('ovr/%s.json5'%sDs, '''{
			// test override
			"dataset": "%s", "dsdf": %s, %s
			"ops": [%s]
		}'''%(sDs, json.dumps(sHash), sExtra, sOps))

	g_sHskOps = '''
		{"op": "move", "from": "/interface/options/props/*", "path": "/interface/data/*/props/enabled"},
		{"op": "move", "from": "/interface/data/*/props/enabled/title", "path": "/interface/data/*/title", "before": "props"},
		{"op": "remove", "path": "/interface/options"},
	'''

	def test_override_applies(self):
		dSrv = {g_sA: {'M/Hsk':g_dHsk, 'M/Simple':g_dSimple}}
		sHash = imp.dsdfHash(props(g_dHsk))
		self.override('M/Hsk', sHash, self.g_sHskOps)
		sOvr = os.path.join(self.sDir, 'ovr')
		self.assertEqual(self.run_import(dSrv, ['-o', sOvr, g_sA, '/']), 0)

		dSrc = self.read('out/test/m/hsk/das2.json')
		self.assertNotIn('options', dSrc['interface'])
		self.assertEqual(dSrc['interface']['data']['p12v'], {
			'title':'+12V supply',
			'props':{'enabled':{'label':'p12v', 'type':'boolean', 'value':False,
			                    'set':{'param':'params', 'flag':'p12v', 'value':True}}}})
		# the example followed the move, and the set summary has the variables
		self.assertEqual(dSrc['interface']['examples'][0]['settings']['data/p12v/props/enabled'], True)
		self.assertEqual(sorted(self.read('out/test/m/hsk.json')['data']), ['n5v', 'p12v'])
		self.assertTrue(self.hdlr.has('INFO', 'applied override'))

	def test_override_guards(self):
		dSrv = {g_sA: {'M/Hsk':g_dHsk}}
		sOvr = os.path.join(self.sDir, 'ovr')
		sHash = imp.dsdfHash(props(g_dHsk))
		sNode = os.path.join(self.sDir, 'out/test/m/hsk/das2.json')

		# stale: reviewed against another DSDF.  Not written, and the message
		# has the value to bless.
		self.override('M/Hsk', 'sha256:0000000000000000', self.g_sHskOps)
		self.assertEqual(self.run_import(dSrv, ['-o', sOvr, g_sA, '/']), 5)
		self.assertFalse(os.path.exists(sNode))
		self.assertTrue(self.hdlr.has('ERROR', sHash))

		# with a node from an earlier run on disk, a stale override leaves it
		# there and listed
		self.override('M/Hsk', sHash, self.g_sHskOps)
		self.assertEqual(self.run_import(dSrv, ['-o', sOvr, g_sA, '/']), 0)
		dSrv2 = {g_sA: {'M/Hsk':dict(g_dHsk, param_03='p5v | +5V supply | 5.0')}}
		self.assertEqual(self.run_import(dSrv2, ['-o', sOvr, g_sA, '/']), 5)
		self.assertEqual(sorted(self.read('out/test/m.json')['catalog']), ['hsk'])
		self.assertNotIn('p5v', self.read('out/test/m/hsk/das2.json')['interface']['data'])
		shutil.rmtree(os.path.join(self.sDir, 'out'))

		# no hash at all is stale too
		self.override('M/Hsk', None, self.g_sHskOps)
		self.assertEqual(self.run_import(dSrv, ['-o', sOvr, g_sA, '/']), 5)

		# an op that does not apply
		self.override('M/Hsk', sHash, '{"op": "remove", "path": "/interface/nope"}')
		self.assertEqual(self.run_import(dSrv, ['-o', sOvr, g_sA, '/']), 5)
		self.assertTrue(self.hdlr.has('ERROR', 'op 0 (remove)'))

		# an op that applies but leaves a broken node: the example still
		# names the option that was removed
		self.override('M/Hsk', sHash, '{"op": "remove", "path": "/interface/options/props/p12v"}')
		self.assertEqual(self.run_import(dSrv, ['-o', sOvr, g_sA, '/']), 5)
		self.assertTrue(self.hdlr.has('ERROR', 'not a settable property'))

		# filed where no dataset is, by name, by letter case or by extension:
		# a reviewed change that is not applied is an error, not a remark
		self.override('M/Hsk', sHash, self.g_sHskOps)
		for sWrong in ('M/Other.json5', 'M/hsk.json5', 'M/Hsk.json'):
			os.rename(os.path.join(sOvr, 'M/Hsk.json5'), os.path.join(sOvr, sWrong))
			self.assertEqual(self.run_import(dSrv, ['-o', sOvr, g_sA, '/']), 5, sWrong)
			self.assertTrue(self.hdlr.has('ERROR', 'was not used'), sWrong)
			os.rename(os.path.join(sOvr, sWrong), os.path.join(sOvr, 'M/Hsk.json5'))
		with open(os.path.join(sOvr, 'M/Hsk.json5')) as f: sText = f.read()
		self.write('ovr/M/Hsk.json5', sText.replace('"M/Hsk"', '"M/Else"'))
		self.assertEqual(self.run_import(dSrv, ['-o', sOvr, g_sA, '/']), 5)
		self.assertTrue(self.hdlr.has('ERROR', "says it is for dataset 'M/Else'"))

		self.assertEqual(self.run_import(dSrv, ['-o', os.path.join(self.sDir, 'nodir'), g_sA, '/']), 13)

	def test_list_run(self):
		dSrv = {g_sA: {'M/Survey':g_dSurvey}}
		self.assertEqual(self.run_import(dSrv, [g_sA, '/']), 0)
		dSrc = self.read('out/test/m/survey/das2.json')
		self.assertEqual(dSrc['interface']['options']['props']['nix']['multi'], True)
		self.assertEqual(dSrc['interface']['examples'][1]['settings']['options/props/mfr'], ['1', '2', 'Ex'])

##############################################################################

class TestRepoOverrides(unittest.TestCase):
	"""Every override file in the repository at least reads"""
	def test_they_load(self):
		sTop = os.path.join(g_sRepo, 'src', 'overrides')
		n = 0
		for (sDir, lDirs, lNames) in os.walk(sTop):
			for sName in lNames:
				if not sName.endswith('.json5'): continue
				sFile = os.path.join(sDir, sName)
				dOver = ovr.loadOverride(sFile)
				# filed where its dataset member says: <site>/<dataset>.json5
				sRel = os.path.relpath(sFile, sTop).replace(os.sep, '/')
				self.assertEqual(sRel.split('/', 1)[1], dOver['dataset'] + '.json5', sFile)
				self.assertRegex(dOver['dsdf'] or '', r'^sha256:[0-9a-f]{16}$', sFile)
				n += 1
		self.assertGreater(n, 0)

if __name__ == '__main__':
	unittest.main()
