from time import asctime

def log(msg):
    print "{}  {}".format(asctime(), msg)
