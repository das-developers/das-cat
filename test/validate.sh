#!/usr/bin/env bash

# Run this script from the root of the das-cat git project

function validate {
	check-jsonschema -v --base-uri $(pwd)/schema/ --schemafile $(pwd)/schema/catalog.json5 "$@"

	if [ "$?" != "0" ] ; then
		echo "OK"
	else
		echo "Failed"
		exit "$?"
	fi
}

if [ ! -d "test_venv" ]; then
	echo -n "Creating virtual environment... "
	python3 -m venv test_venv
	if [ "$?" == "0" ]; then 
		echo "OK"
	else
		echo "Failed"
		exit 7
	fi

	source test_venv/bin/activate
	python3 -m pip install jsonschema check-jsonschema json5	
else
	source test_venv/bin/activate
fi

echo "Validating schema files... "
check-jsonschema -v  --check-metaschema schema/*.json5
if [ "$?" != "0" ]; then
	exit 7
fi

echo -n "FedCat Root catalogs... "
validate cat/*.json

#echo -n "Checking das root catalogs... "
#validate cat/das/*.json

#$echo -n "Checking das site root catalogs... "
#validate cat/das/site/*.json

#echo -n "Checking das test root catalogs... "
#validate cat/das/test/*.json

echo "All validation tests passed, but JHU-APL not checked"

deactivate

exit 0


