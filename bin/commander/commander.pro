
QMAKE_UIC 	= pyuic
QMAKE_MOC 	= echo
QMAKE_EXT_CPP 	= .cpp
QMAKE_EXT_H 	= .py
FORMS	= mainwindowbase.ui \
	aboutdialogbase.ui
TEMPLATE	=app
CONFIG	+= qt warn_on release
