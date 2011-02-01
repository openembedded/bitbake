import gtk

class ProgressBar(gtk.Dialog):
    def __init__(self, parent):

        gtk.Dialog.__init__(self)
        self.set_title("Parsing metadata, please wait...")
        self.set_default_size(500, 0)
        self.set_transient_for(parent)
        self.set_destroy_with_parent(True)
        self.progress = gtk.ProgressBar()
        self.vbox.pack_start(self.progress)
        self.show_all()

    def update(self, x, y):
        self.progress.set_fraction(float(x)/float(y))
        self.progress.set_text("%2d %%" % (x*100/y))

    def pulse(self):
        self.progress.set_text("Loading...")
        self.progress.pulse()
