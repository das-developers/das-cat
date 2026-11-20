#!/bin/bash
export PYTHONPATH=/opt/project/voyager/lib/python3.4:/opt/project/voyager/lib/centos7/python3.4

srv_url=http://planet.physics.uiowa.edu/das/das2Server
srv_path=/
root_uri=site:/uiowa
root_url=http://das2.org/catalog/das/site/uiowa.json
#root_url=http://das2.org/cat_test/das/site/uiowa.json
out_dir=./tmp
src_id_root=tag:physics.uiowa.edu,2018:das.

ex1=/Juno/WAV/atlo
ex2=/Juno/WAV/em
ex3=/Juno/JED/devel

echo "./scripts/das2_cat_import -i $src_id_root -e $ex1 -e $ex2 -e $ex3 $srv_url $srv_path $root_uri $root_url $out_dir"
./scripts/das2_cat_import -i $src_id_root -e $ex1 -e $ex2 -e $ex3 $srv_url $srv_path $root_uri $root_url $out_dir

