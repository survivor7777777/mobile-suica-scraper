#!/bin/bash

export PYENV_ROOT="${HOME}/.pyenv"
if [ -d "${PYENV_ROOT}" ]; then
    export PATH=${PYENV_ROOT}/bin:$PATH
    eval "$(pyenv init -)"
fi

home_dir=`dirname $0`
param_file="model/parameters.json"

exec $home_dir/scrape-mysql.pl --model $param_file
