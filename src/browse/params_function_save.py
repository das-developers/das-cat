g_dTypes = {'integer':'integer', 'real':'real number'}
def _inputFlagSet(sOpt, dInfo):
	"""All the crazy das 2.2 overloaded parameter strings can flow though
	this monstrosity of an input generator as well as the hapi data source
	toggles.

	Returns the name of a function to add to the list of functions called
	on form submit, or None if nothing is to be called.
	"""
	if 'FLAGS' not in dInfo:
		pout('<p><span class="error">FLAGS value missing from catalog item.'
		     '</span>  Contact the maintainer of this data source to fix '
			  'the issue</p>')
		return None

	if len(dInfo['FLAGS']) == 0:
		return None

	# Create the dummy check boxes that will not be sent to the server
	lFlagSetIds = []
	lFlagSetType = []
	for i in range(len(dInfo['FLAGS'])):
		dFlag = dInfo['FLAGS'][i]

		pout('<p class="download">')
		if 'VAL' in dFlag:
			pout('<input type="checkbox" id="q_%s_%02d" value="%s"> <b>%s</b>'%(
			  	sOpt, i, dFlag['VAL'], dFlag['VAL']))
			lFlagSetType.append("checkbox")
		elif 'VAL_TYPE' in dFlag:
			# This is an odd one, a value-type which we'll just treat as a string
			# other than the label hint
			if dFlag['VAL_TYPE'] in g_dTypes:
				sLbl = g_dTypes[dFlag['VAL_TYPE']]
			else:
				sLbl = dFlag['VAL_TYPE']
			pout('<p class="download">')
			pout('<label for="q_%s_%02d">%s</label>'%(sOpt, i, sLbl))
			pout('<input type="text" id="q_%s_%02d">'%(sOpt, i))
			lFlagSetType.append("text")
		else:
			pout('<p><span class="error">Either VAL or VAL_TYPE must be given for'
			     'flag number %d for option %s</span>  Contact the maintainer of '
				  'this data source to fix the issue</p>'%(i, sOpt))
			return None

		if 'description' in dFlag:
			pout(' - %s'%dFlag['description'])

		lFlagSetIds.append( "q_%s_%02d"%(sOpt, i) )
		pout('</p>')

	# Create the real field that will get the combinded values
	pout('<input type="hidden" name="%s" id="input_%s">'%(sOpt, sOpt))

	sFlagSep = ' '
	if 'FLAG_SEP' in dFlag: sFlagSep = dFlag['FLAG_SEP']

	# And the Javascript that will set the actual field
	sFlagCtrlIds = '["%s"]'%( '","'.join(lFlagSetIds))
	sFlagTypes   = '["%s"]'%( '","'.join(lFlagSetType))
	pout('''
<script>
var lFlagset_%s = %s;
var lFlagType_%s = %s;
var sFlagsetSep_%s = "%s";

function update_flagset_%s() {
	var lSelectedFlags = [];
	var i = 0;
	for(i = 0; i < lFlagset_%s.length; i++) {
		if(lFlagType_%s[i] == "checkbox"){
			// see if checkbox is checked for this flag
			if(document.getElementById(lFlagset_%s[i]).checked) {
				lSelectedFlags.push(document.getElementById(lFlagset_%s[i]).value);
			}
		}
		else{
			// see if text boxes are non-empty for this flag
			if(document.getElementById(lFlagset_%s[i]).value.length > 0){
				lSelectedFlags.push(document.getElementById(lFlagset_%s[i]).value);
			}
		}
	}
	// make a single string with all the flags
	var sVal = lSelectedFlags.join(sFlagsetSep_%s);

	// set the hidden field to have the combined value
	document.getElementById("input_%s").value = sVal;
}
</script>
	'''%(sOpt, sFlagCtrlIds, sOpt, sFlagTypes, sOpt, sFlagSep,
	     sOpt, sOpt, sOpt, sOpt, sOpt, sOpt, sOpt, sOpt, sOpt)
	)

	return "update_flagset_%s"%(sOpt)
