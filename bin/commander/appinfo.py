import os
hostname = os.uname()[1]
hostos = os.uname()[2]
appname = "OpenEmbedded Commander"
appversion = "0.0.1"
appcaption = "%s V%s on %s (%s)" % ( appname, appversion, hostname, hostos )
imageDir = "%s/bin/commander/images/" % os.environ["OEDIR"]

