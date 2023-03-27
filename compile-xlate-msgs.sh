#!/bin/bash

set -e
set -u

base_dir=$( dirname "$0" )
cd "${base_dir}" ||exit 99

locale_dir="locale"
locale_domain="postfix_logsums"
# pot_file="${locale_dir}/${locale_domain}.pot"
# po_with="99"
# my_address="${DEBEMAIL:-frank@brehm-online.com}"

pybabel compile --domain "${locale_domain}" \
    --directory "${locale_dir}" \
    --statistics
