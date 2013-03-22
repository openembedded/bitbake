#
# BitBake Graphical GTK User Interface
#
# Copyright (C) 2011-2013   Intel Corporation
#
# Authored by Andrei Dinu <andrei.adrianx.dinu@intel.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import string
import gtk
import gobject
import os
import tempfile
import glib
from bb.ui.crumbs.hig.crumbsdialog import CrumbsDialog
from bb.ui.crumbs.hig.settingsuihelper import SettingsUIHelper
from bb.ui.crumbs.hig.crumbsmessagedialog import CrumbsMessageDialog
from bb.ui.crumbs.hig.layerselectiondialog import LayerSelectionDialog

"""
The following are convenience classes for implementing GNOME HIG compliant
BitBake GUI's
In summary: spacing = 12px, border-width = 6px
"""

class PropertyDialog(CrumbsDialog):
	
	def __init__(self, title, parent, information, flags, buttons=None):
		
		super(PropertyDialog, self).__init__(title, parent, flags, buttons)
                
                self.properties = information		

                if len(self.properties) == 10:
		        self.create_recipe_visual_elements()
                elif len(self.properties) == 4:
                        self.create_package_visual_elements()
                else:
                        self.create_information_visual_elements()


        def create_information_visual_elements(self):

                HOB_ICON_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ("icons/"))
                ICON_PACKAGES_DISPLAY_FILE    = os.path.join(HOB_ICON_BASE_DIR, ('info/info_display.png'))

                self.table = gtk.Table(1,1,False)
                self.table.set_row_spacings(0)
                self.table.set_col_spacings(0)

                self.image = gtk.Image()
                self.image.set_from_file(ICON_PACKAGES_DISPLAY_FILE)
                self.image.set_property("xalign",0)
                #self.vbox.add(self.image)

                image_info = self.properties.split("*")[0]
                info = self.properties.split("*")[1]
                
                vbox = gtk.VBox(True, spacing=30)        
                
                self.label_short = gtk.Label()
                self.label_short.set_line_wrap(False)
                self.label_short.set_markup(image_info)
                self.label_short.set_property("xalign", 0)

                self.info_label = gtk.Label()
                self.info_label.set_line_wrap(True)
                self.info_label.set_markup(info)
                self.info_label.set_property("yalign", 0.5)

                self.table.attach(self.image, 0,1,0,1, xoptions=gtk.FILL|gtk.EXPAND, yoptions=gtk.FILL,xpadding=5,ypadding=5)
                self.table.attach(self.label_short, 0,1,0,1, xoptions=gtk.FILL|gtk.EXPAND, yoptions=gtk.FILL,xpadding=40,ypadding=5)
                self.table.attach(self.info_label, 0,1,1,2, xoptions=gtk.FILL|gtk.EXPAND, yoptions=gtk.FILL,xpadding=40,ypadding=10)
        
                self.vbox.add(self.table)

                
        def create_package_visual_elements(self):

                name = self.properties['name']
                binb = self.properties['binb']
                size = self.properties['size']
                recipe = self.properties['recipe']

                #cleaning out the recipe variable
                recipe = recipe.split("+")[0]

                vbox = gtk.VBox(True,spacing = 0)

                ###################################### NAME ROW + COL #################################

                self.label_short = gtk.Label()
                self.label_short.set_size_request(300,-1)
                self.label_short.set_selectable(True)
                self.label_short.set_line_wrap(True)
                self.label_short.set_markup("<span weight=\"bold\">Name: </span>" + name)
                self.label_short.set_property("xalign", 0)
                                
                self.vbox.add(self.label_short)

                ###################################### SIZE ROW + COL ######################################

                self.label_short = gtk.Label()
                self.label_short.set_size_request(300,-1)
                self.label_short.set_selectable(True)
                self.label_short.set_line_wrap(True)
                self.label_short.set_markup("<span weight=\"bold\">Size: </span>" + size)
                self.label_short.set_property("xalign", 0)
                
                self.vbox.add(self.label_short)

                ##################################### RECIPE ROW + COL #########################################

                self.label_short = gtk.Label()
                self.label_short.set_size_request(300,-1)
                self.label_short.set_selectable(True)
                self.label_short.set_line_wrap(True)
                self.label_short.set_markup("<span weight=\"bold\">Recipe: </span>" + recipe)
                self.label_short.set_property("xalign", 0)

                self.vbox.add(self.label_short)

                ##################################### BINB ROW + COL #######################################
                
                if binb != '':
                        self.label_short = gtk.Label()
                        self.label_short.set_selectable(True)
                        self.label_short.set_line_wrap(True)
                        self.label_short.set_markup("<span weight=\"bold\">Brought in by: </span>")
                        self.label_short.set_property("xalign", 0)                

                        self.label_info = gtk.Label()
                        self.label_info.set_size_request(300,-1)
                        self.label_info.set_selectable(True)
                        self.label_info.set_line_wrap(True)
                        self.label_info.set_markup(binb)
                        self.label_info.set_property("xalign", 0)               
                                                        
                        self.vbox.add(self.label_short)
                        self.vbox.add(self.label_info)

                self.vbox.show_all()


	def create_recipe_visual_elements(self):

                summary = self.properties['summary']
		name = self.properties['name']
		version = self.properties['version']
		revision = self.properties['revision']
		binb = self.properties['binb']
		group = self.properties['group']
		license = self.properties['license']
		homepage = self.properties['homepage']
		bugtracker = self.properties['bugtracker']
		description = self.properties['description']
		
                #cleaning out the version variable and also the summary
                version = version.split(":")[1]
                if len(version) > 30:
                        version = version.split("+")[0]
                else:
                        version = version.split("-")[0]
                license = license.replace("&" , "and")
                if (homepage == ''):
                        homepage = 'unknown'
                if (bugtracker == ''):
                        bugtracker = 'unknown'
                summary = summary.split("+")[0]
                
                #calculating the rows needed for the table
                binb_items_count = len(binb.split(','))
                binb_items = binb.split(',')
                               		
		vbox = gtk.VBox(True,spacing = 0)
                
                ######################################## SUMMARY LABEL #########################################                	                
                
                if summary != '':                
                        self.label_short = gtk.Label()
                        self.label_short.set_size_request(300,-1)
                        self.label_short.set_selectable(True)                
                        self.label_short.set_line_wrap(True)
                        self.label_short.set_markup("<b>" + summary + "</b>")
                        self.label_short.set_property("xalign", 0)
                        
                        self.vbox.pack_start(self.label_short, expand=False, fill=False, padding=0)
                
                ########################################## NAME ROW + COL #######################################
                                
                self.label_short = gtk.Label()
                self.label_short.set_size_request(300,-1)
                self.label_short.set_selectable(True)
                self.label_short.set_line_wrap(True)
                self.label_short.set_markup("<span weight=\"bold\">Name: </span>" + name)
                self.label_short.set_property("xalign", 0)
                                
                self.vbox.add(self.label_short)

                ####################################### VERSION ROW + COL ####################################
                
                self.label_short = gtk.Label()
                self.label_short.set_size_request(300,-1)
                self.label_short.set_selectable(True)
                self.label_short.set_line_wrap(True)
                self.label_short.set_markup("<span weight=\"bold\">Version: </span>" + version)
                self.label_short.set_property("xalign", 0)
                
                self.vbox.add(self.label_short)

                ##################################### REVISION ROW + COL #####################################

                self.label_short = gtk.Label()
                self.label_short.set_size_request(300,-1)
                self.label_short.set_line_wrap(True)
                self.label_short.set_selectable(True)
                self.label_short.set_markup("<span weight=\"bold\">Revision: </span>" + revision)
                self.label_short.set_property("xalign", 0)                
                
                self.vbox.add(self.label_short)

                ################################## GROUP ROW + COL ############################################
               
                self.label_short = gtk.Label()
                self.label_short.set_size_request(300,-1)  
                self.label_short.set_selectable(True)              
                self.label_short.set_line_wrap(True)                                
                self.label_short.set_markup("<span weight=\"bold\">Group: </span>" + group)
                self.label_short.set_property("xalign", 0)
                                
                self.vbox.add(self.label_short)

                ################################# HOMEPAGE ROW + COL ############################################
                
                if homepage != 'unknown':
                        self.label_info = gtk.Label()
                        self.label_info.set_selectable(True)
                        self.label_info.set_line_wrap(True)
                        if len(homepage) > 35:
                                self.label_info.set_markup("<a href=\"" + homepage + "\">" + homepage[0:35] + "..." + "</a>")
                        else:
                                self.label_info.set_markup("<a href=\"" + homepage + "\">" + homepage[0:60] + "</a>")

                        self.label_info.set_property("xalign", 0)
                       
                        self.label_short = gtk.Label()
                        self.label_short.set_size_request(300,-1)   
                        self.label_short.set_selectable(True)                     
                        self.label_short.set_line_wrap(True)                        
                        self.label_short.set_markup("<b>Homepage: </b>")                      
                        self.label_short.set_property("xalign", 0)
                        
                        self.vbox.add(self.label_short)
                        self.vbox.add(self.label_info)
               
                ################################# BUGTRACKER ROW + COL ###########################################
                
                if bugtracker != 'unknown':
                        self.label_info = gtk.Label()
                        self.label_info.set_selectable(True)
                        self.label_info.set_line_wrap(True)
                        if len(bugtracker) > 35:
                                self.label_info.set_markup("<a href=\"" + bugtracker + "\">" + bugtracker[0:35] + "..." + "</a>")
                        else:
                                self.label_info.set_markup("<a href=\"" + bugtracker + "\">" + bugtracker[0:60] + "</a>")
                        self.label_info.set_property("xalign", 0)  

                        self.label_short = gtk.Label()
                        self.label_short.set_size_request(300,-1)    
                        self.label_short.set_selectable(True)                    
                        self.label_short.set_line_wrap(True)
                        self.label_short.set_markup("<b>Bugtracker: </b>")                   
                        self.label_short.set_property("xalign", 0)
                        
                        self.vbox.add(self.label_short)
                        self.vbox.add(self.label_info)

                ################################# LICENSE ROW + COL ############################################
                
                self.label_info = gtk.Label()
                self.label_info.set_size_request(300,-1)
                self.label_info.set_selectable(True)
                self.label_info.set_line_wrap(True)
                self.label_info.set_markup(license)
                self.label_info.set_property("xalign", 0)

                self.label_short = gtk.Label()
                self.label_short.set_selectable(True)                
                self.label_short.set_line_wrap(True)                
                self.label_short.set_markup("<span weight=\"bold\">License: </span>")
                self.label_short.set_property("xalign", 0)
                
                self.vbox.add(self.label_short)
                self.vbox.add(self.label_info)

                ################################### BINB ROW+COL #############################################
                
                if binb != '':
                        self.label_short = gtk.Label()
                        self.label_short.set_selectable(True)
                        self.label_short.set_line_wrap(True)
                        self.label_short.set_markup("<span weight=\"bold\">Brought in by: </span>")
                        self.label_short.set_property("xalign", 0)

                        self.label_info = gtk.Label()
                        self.label_info.set_size_request(300,-1)
                        self.label_info.set_selectable(True)
                        self.label_info.set_markup(binb)
                        self.label_info.set_property("xalign", 0)
                        self.label_info.set_line_wrap(True)
                        
                        self.vbox.add(self.label_short)
                        self.vbox.add(self.label_info)

                ################################ DESCRIPTION TAG ROW #################################################
                
                self.label_short = gtk.Label()
                self.label_short.set_line_wrap(True)
                self.label_short.set_markup("<span weight=\"bold\">Description </span>")
                self.label_short.set_property("xalign", 0)
                self.vbox.add(self.label_short)
                
                ################################ DESCRIPTION INFORMATION ROW ##########################################
                
                hbox = gtk.HBox(True,spacing = 0)

                self.label_short = gtk.Label()
                self.label_short.set_size_request(300,-1)
                self.label_short.set_selectable(True)                
                self.label_short.set_text(description)
                self.label_short.set_line_wrap(True)
                self.label_short.set_property("xalign", 0)
                self.vbox.add(self.label_short)

                self.vbox.show_all()
