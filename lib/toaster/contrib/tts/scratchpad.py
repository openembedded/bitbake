import config

# Code testing section
def _code_test():
    def callback_writeeventlog(opt, opt_str, value, parser):
        if len(parser.rargs) < 1 or parser.rargs[0].startswith("-"):
            value = ""
        else:
            value = parser.rargs[0]
            del parser.rargs[0]

        setattr(parser.values, opt.dest, value)

    parser = optparse.OptionParser()
    parser.add_option("-w", "--write-log", help = "Writes the event log of the build to a bitbake event json file.",
                       action = "callback", callback=callback_writeeventlog, dest = "writeeventlog")

    options, targets = parser.parse_args(sys.argv)

    print (options, targets)
