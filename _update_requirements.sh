#!/bin/bash
set -e
pip install --upgrade safety pip-tools
rm -f requirements.txt
pip-compile -r --output-file requirements.txt requirements.in 
safety check -r requirements.txt

pip install PdbBBEditSupport