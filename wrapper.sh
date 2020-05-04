#!/bin/bash

# setup pyenv
if ! which pyenv > /dev/null 2>&1 && [ -d $HOME/.pyenv ]; then
    export PATH=$HOME/.pyenv/shims:$PATH
    eval "$(pyenv init -)"
    eval "$(pyenv virtualenv-init -)"
    export PIP_CONFIG_FILE=$HOME/.pyenv/pip.conf
fi

# setup plenv
if which plenv > /dev/null 2>&1; then
    eval "$(plenv init -)"
fi

pwd=`dirname $0`
exec $pwd/scrape.pl "$@"
