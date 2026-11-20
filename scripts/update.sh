#!/bin/bash

cd /space/html/das2/catalog

catRootUrl=https://das2.org/catalog

export PYTHONPATH=/home/cwp/tmp/test/lib/python3.4:/home/cwp/tmp/test/lib/centos7/python3.4
makeRoot=/space/html/das2/catalog/das2_root_cat.py

importD22=/home/cwp/svn/das2/servers/devel/catalog/scripts/das2_cat_import

$makeRoot root  > index.json

$makeRoot das > das.json
$makeRoot spase > spase.json
$makeRoot cdaweb > cdaweb.json

mkdir das
cd das
$makeRoot das_site > site.json
$makeRoot das_test > test.json
mkdir site
mkdir test


cd site

exit 0

srv_url=https://voparis-maser-das.obspm.fr/das2/server
srv_path=/
root_uri=site:/voparis
root_url=https://das2.org/catalog/das/site/voparis.json
out_dir=$(pwd)
src_id_root=tag:obspm.fr,2018:das.

echo "$importD22 -i $src_id_root $srv_url $srv_path $root_uri $root_url $out_dir"
$importD22 -i $src_id_root $srv_url $srv_path $root_uri $root_url $out_dir


srv_url=https://planet.physics.uiowa.edu/das/das2Server
srv_path=/
root_uri=site:/uiowa
#root_url=https://das2.org/catalog/das/site/uiowa.json
root_url=https://das2.org/catalog/das/site/uiowa.json
out_dir=$(pwd)
src_id_root=tag:physics.uiowa.edu,2018:das.

ex1=/Juno/WAV/atlo
ex2=/Juno/WAV/em
ex3=/Juno/JED/devel

echo "$importD22 -i $src_id_root -e $ex1 -e $ex2 -e $ex3 $srv_url $srv_path $root_uri $root_url $out_dir"
$importD22 -i $src_id_root -e $ex1 -e $ex2 -e $ex3 $srv_url $srv_path $root_uri $root_url $out_dir
