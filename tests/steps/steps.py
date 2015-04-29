from behave import when, then, given
import subprocess
import time
import requests
from time import sleep
from docker import Client

d = Client()
#from common_steps import common_docker_steps, common_connection_steps


@when(u'Container is started')
def container_is_started(context):
    context.job = context.run('docker run -d --cidfile %s %s' % (context.cid_file, context.image))
    print("job: %s" % context.job)
    context.cid = context.open_file(context.cid_file).read().strip()
    print ("cid: %s " % context.cid)


@then(u'Check that page is served on port "{port}"')
def handle_request(context, port):
    # HACK - just set params
    expected_status_code=403
    expected_phrase="This page is used to test the proper operation of the Apache HTTP server after it has been installed."
    wait = 20
    timeout = 0.5
    path = '/'
    # test
    start_time = time.time()
    print ("docker inspect --format='{{.NetworkSettings.IPAddress}}' %s" % context.cid)

    ip =  d.inspect_container(container=context.cid)['NetworkSettings']['IPAddress']
    print("ip: '%s'" % ip )
    while time.time() < start_time + wait:
        try:
            response = requests.get('http://%s:%s%s' % (ip, port, path), timeout = timeout, stream=False)
        except Exception as ex:
            # Logging as warning, bcause this does not neccessarily means
            # something bad. For example the server did not boot yet.
            print("Exception caught: %s" % repr(ex))
        else:
            latest_status_code = response.status_code
            print("Response code from the container on port %s: %s (expected: %s)" % (port, latest_status_code, expected_status_code))
            if latest_status_code == expected_status_code:
                if not expected_phrase:
                    # The expected_phrase parameter was not set
                    return True

                if expected_phrase in response.text:
                    # The expected_phrase parameter was found in the body
                    print("Document body contains the '%s' phrase!" % expected_phrase)
                    return True
                else:
                    # The phrase was not found in the response
                    raise Exception("Failure! Correct status code received but the document body does not contain the '%s' phrase!" % expected_phrase,
                        "Received body:\n%s" % response.text) # XXX: better diagnostics

        time.sleep(1)
    raise Exception("handle_request failed", expected_status_code)


