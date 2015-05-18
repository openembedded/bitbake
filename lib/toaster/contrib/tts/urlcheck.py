from __future__ import print_function
import sys

import httplib2
import time

import config
import urllist


# TODO: turn to a test
def validate_html5(url):
    h = httplib2.Http(".cache")
    status = "Failed"
    errors = -1
    warnings = -1

    # TODO: the w3c-validator must be a configurable setting
    urlrequest = config.W3C_VALIDATOR+url
    try:
        resp, content = h.request(urlrequest, "HEAD")
        if resp['x-w3c-validator-status'] != "Abort":
            status = resp['x-w3c-validator-status']
            errors = int(resp['x-w3c-validator-errors'])
            warnings = int(resp['x-w3c-validator-warnings'])
    except Exception as e:
        config.logger.warn("Failed validation call: %s" % e.__str__())
    return (status, errors, warnings)

if __name__ == "__main__":
    print("Testing %s with %s" % (config.TOASTER_BASEURL, config.W3C_VALIDATOR))

    def print_validation(url):
        status, errors, warnings = validate_html5(url)
        config.logger.error("url %s is %s\terrors %s warnings %s (check at %s)" % (url, status, errors, warnings, config.W3C_VALIDATOR+url))

    if len(sys.argv) > 1:
        print_validation(sys.argv[1])
    else:
        for url in urllist.URLS:
            print_validation(config.TOASTER_BASEURL+url)
