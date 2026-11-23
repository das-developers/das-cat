#!/usr/bin/env bash

# Build the U. Iowa site catalog (site:/uiowa) from the das2 servers.
#
#   uiowa.sh OUT_DIR [importer options...]
#
# OUT_DIR gets uiowa.json and the uiowa/ tree below it.  Nothing is
# written anywhere else, so build into a scratch directory, check the
# result (see src/curation/checks.md) and copy it into place afterwards.
# Whatever is in the published catalog directory is live at once.
# Clients need das2C 3.0.6 or later to read these nodes.
#
# jupiter is the first choice for the datasets it has (Earth, Galileo,
# Juno); planet has everything and is the mirror for those.  The order
# here is the order of each source's base URLs, which is the order
# clients fail over in.
#
# Left out:
#   Juno/WAV/em                  ground test model, not flight data
#   Juno/JAD/ElectronPitchAngle  listed by the servers but not installed
#
# Extra options go to the importer, for example:
#   -n        report what would change, write nothing
#
# This replaces uiowa_gurnett.sh and the uiowa part of update.sh, which
# use the command line of the 0.6 importer.

if [ -z "$1" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
	sed -n '3,26p' "$0" | sed 's/^# \{0,1\}//'
	exit 3
fi

sOut=$1; shift
sHere=$(cd "$(dirname "$0")" && pwd)

exec "$sHere/dsdf_cat_import" \
	-e Juno/WAV/em \
	-e Juno/JAD/ElectronPitchAngle \
	-o "$sHere/../overrides/uiowa" \
	-m https://planet.physics.uiowa.edu/das/das2Server \
	"$@" \
	https://jupiter.physics.uiowa.edu/das/server \
	/ \
	https://das2.org/catalog/das/site/uiowa.json \
	"$sOut"
