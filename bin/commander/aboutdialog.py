#!/usr/bin/env python
# -*- coding: iso8859-15 -*-

from aboutdialogbase import *

class AboutDialog( AboutDialogBase ):
    pass


#------------------------------------------------------------------------#
# main
#------------------------------------------------------------------------#

import sys
from qt import *
app = QApplication( sys.argv )
mw = AboutDialog()
mw.exec_loop()

