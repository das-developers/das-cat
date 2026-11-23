#!/usr/bin/env bash

# Run this script from the root of the das-cat git project.  Validates the
# published schemas (build them with 'make schema') and then the root
# catalog nodes and the example nodes against them.  Each node is checked
# against the schema for its own type and version, see validate_tree.py.

if ! ls schema/*/v*.json > /dev/null 2>&1; then
	echo "No schema/<type>/v<version>.json files, run 'make schema' first"
	exit 7
fi

nFail=0

# The root nodes were stamped before their types had schemas (Catalog 0.3
# and 0.4), so -c: check them against the current schema of their type.
function validate {
	test/validate_tree.py -c "$@"

	if [ "$?" == "0" ] ; then
		echo "OK"
	else
		echo "Failed"
		nFail=$((nFail + 1))
	fi
}

if [ ! -d "venv" ]; then
	echo -n "Creating virtual environment... "
	python3 -m venv venv
	if [ "$?" == "0" ]; then
		echo "OK"
	else
		echo "Failed"
		exit 7
	fi

	source venv/bin/activate
	python3 -m pip install jsonschema check-jsonschema
	if [ "$?" != "0" ]; then
		echo "pip install failed"
		exit 7
	fi
else
	source venv/bin/activate
fi

echo "Validating schema files... "
check-jsonschema --check-metaschema schema/*/v*.json
if [ "$?" != "0" ]; then
	exit 7
fi

# cat/spase.json is left out.  SPASE records are another branch of the
# catalog with members of their own (type SpaseRecord, reference_urls)
# that the Catalog schema does not describe, and they are not part of
# what the das branch work covers.
echo "FedCat Root catalogs (not spase.json)... "
lRoots=""
for f in cat/*.json; do
	if [ "$f" == "cat/spase.json" ]; then
		echo "   skipping $f, SPASE nodes have no schema here"
	else
		lRoots="$lRoots $f"
	fi
done
validate $lRoots

# These carry current versions, no -c
echo "Example source nodes... "
test/validate_tree.py test/ex*.json
if [ "$?" == "0" ] ; then
	echo "OK"
else
	echo "Failed"
	nFail=$((nFail + 1))
fi

#echo "Checking das root catalogs... "
#validate cat/das/*.json

#echo "Checking das site root catalogs... "
#validate cat/das/site/*.json

#echo "Checking das test root catalogs... "
#validate cat/das/test/*.json

deactivate

if [ "$nFail" != "0" ]; then
	echo "$nFail validation group(s) failed"
	exit 7
fi

echo "All validation tests passed, but JHU-APL not checked"
exit 0
