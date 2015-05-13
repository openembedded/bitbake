from __future__ import print_function
import sys

import httplib2
import time

import config
import urllist

# TODO: spawn server here
BASEURL="http://localhost:8000/"

#def print_browserlog(url):
#    driver = webdriver.Firefox()
#    driver.get(url)
#    body = driver.find_element_by_tag_name("body")
#    body.send_keys(Keys.CONTROL + 't')
#    for i in driver.get_log('browser'):
#        print(i)
#    driver.close()


# TODO: turn to a test
def validate_html(url):
    h = httplib2.Http(".cache")
    # TODO: the w3c-validator must be a configurable setting
    urlrequest = "http://icarus.local/w3c-validator/check?doctype=HTML5&uri="+url
    try:
        resp, content = h.request(urlrequest, "HEAD")
        if resp['x-w3c-validator-status'] == "Abort":
            config.logger.error("FAILed call %s" % url)
        else:
            config.logger.error("url %s is %s\terrors %s warnings %s (check at %s)" % (url, resp['x-w3c-validator-status'], resp['x-w3c-validator-errors'], resp['x-w3c-validator-warnings'], urlrequest))
    except Exception as e:
        config.logger.warn("Failed validation call: %s" % e.__str__())

    print("done %s" % url)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        validate_html(sys.argv[1])
    else:
        for url in urllist.URLS:
            validate_html(BASEURL+url)
