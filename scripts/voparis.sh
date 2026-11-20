#!/bin/bash

srv_url=http://voparis-maser-das.obspm.fr/das2/server
srv_path=/
root_uri=site:/voparis
root_url=http://das2.org/catalog/das/site/voparis.json
out_dir=/home/cwp/svn/das2/servers/devel/catalog/tmp
src_id_root=tag:obspm.fr,2018:das.

echo "./scripts/das2_cat_import -i $src_id_root $srv_url $srv_path $root_uri $root_url $out_dir"
./scripts/das2_cat_import -i $src_id_root $srv_url $srv_path $root_uri $root_url $out_dir

