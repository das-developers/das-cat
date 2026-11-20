#!/bin/bash

srv_url=https://emfisis.physics.uiowa.edu/das/server
srv_path=/
root_uri=site:/uiowa
root_url=http://das2.org/catalog/das/site/uiowa.json
out_dir=./tmp

./scripts/das2_cat_import $srv_url $srv_path $root_uri $root_url $out_dir

