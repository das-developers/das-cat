#!/usr/bin/env bash

# Run this script from the root of the das-cat git project.  Validates the
# generated schemas (build them with 'make schema') and then the root
# catalog nodes against them.  Usage: validate.sh [SCHEMA_DIR]

sSchema="${1:-schema/v0.7}"
if [ ! -f "$sSchema/catalog.json" ]; then
	echo "No $sSchema/catalog.json, run 'make schema' first"
	exit 7
fi

nFail=0

function validate {
	check-jsonschema --base-uri "file://$(pwd)/$sSchema/" \
		--schemafile "$(pwd)/$sSchema/catalog.json" "$@"

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
check-jsonschema --check-metaschema "$sSchema"/*.json
if [ "$?" != "0" ]; then
	exit 7
fi

echo "FedCat Root catalogs... "
validate cat/*.json

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
