#!/usr/bin/env python
# -*- coding: iso8859-15 -*-

from mainwindowbase import *

class MainWindow( MainWindowBase ):
    pass


#------------------------------------------------------------------------#
# main
#------------------------------------------------------------------------#

import sys
from qt import *
app = QApplication( sys.argv )
mw = MainWindow()
mw.show()
app.setMainWidget( mw )
app.exec_loop()

