#!/usr/lib/ckan/default/bin paster

from paste.script.serve import ServeCommand

ServeCommand("serve").run(["/etc/ckan/default/development.ini"])