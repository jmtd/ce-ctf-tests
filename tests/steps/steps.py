from behave import when, then, given
import subprocess
import time
import requests
import logging
import select
from time import sleep
from docker import Client
from container import Container

DOCKER_CLIENT = Client()

@when(u'container is ready')
def container_is_started(context):
    context.container = Container(context.image, save_output = False)
    context.container.start()
    

@then(u'check that page is served')
def handle_request(context):
    # set defaults
    port = 80
    wait = 30
    timeout = 0.5
    expected_status_code = 200
    path = '/'
    expected_phrase = None
    # adjust defaults from user table
    for row in context.table:
        if row['property'] == 'port':
            port = row['value']
        if row['property'] == 'expected_status_code':
            expected_status_code = int(row['value'])
        if row['property'] == 'wait':
            wait = int(row['value'])
        if row['property'] == 'timeout':
            timeout = row['value']
        if row['property'] == 'expected_phrase':
            expected_phrase = row['value']
        if row['property'] == 'path':
            path = row['value']
            
    logging.info("Checking if the container is returning status code %s on port %s" % (expected_status_code, port))
    
    start_time = time.time()

    ip = context.container.ip_address
    latest_status_code = 0
        
    while time.time() < start_time + wait:
        try:
            response = requests.get('http://%s:%s%s' % (ip, port, path), timeout = timeout, stream=False)
        except Exception as ex:
            # Logging as warning, bcause this does not neccessarily means
            # something bad. For example the server did not boot yet.
            logging.warn("Exception caught: %s" % repr(ex))
        else:
            latest_status_code = response.status_code
            logging.info("Response code from the container on port %s: %s (expected: %s)" % (port, latest_status_code, expected_status_code))
            if latest_status_code == expected_status_code:
                if not expected_phrase:
                    # The expected_phrase parameter was not set
                    return True

                if expected_phrase in response.text:
                    # The expected_phrase parameter was found in the body
                    logging.info("Document body contains the '%s' phrase!" % expected_phrase)
                    return True
                else:
                    # The phrase was not found in the response
                    raise Exception("Failure! Correct status code received but the document body does not contain the '%s' phrase!" % expected_phrase,
                        "Received body:\n%s" % response.text) # XXX: better diagnostics

        time.sleep(1)
    raise Exception("handle_request failed", expected_status_code) # XXX: better diagnostics         


@then(u'container log contains {message}')
def log_contains_msg(context, message):
    found = True
    found_messages = []
    start_time = time.time()

    # TODO: Add customization option for timeout
    while time.time() < start_time + 30:
        logs = context.container.get_output()
        if message in logs:
            logging.info("Message '%s' was found in the logs" % message)
            return
        # TODO: Add customization option for sleep time
        time.sleep(1)
    else:
        logging.error("Message '%s' was not found in the logs" % message)
    raise Exception("expect_message failed", message)

@then(u'run {cmd} in container and check its output for {output_phrase}')
@then(u'run {cmd} in container')
def run_command_expect_message(context, cmd, output_phrase):
    start_time = time.time()
    while time.time() < start_time + 80:
        output = context.container.execute(cmd=cmd)
        # in an ideal world we'd check the return code of the command, but
        # docker python client library doesn't provide us with that, so we
        # instead look for a predictable string in the output
        if output_phrase in output:
            return True
        time.sleep(1)
    raise Exception("run_command_expect_message didn't find message", output)


@then('{filename} should contain {phrase}')
def file_should_contain(context, filename, phrase):
     run_command_expect_message(context, 'cat %s' % filename, phrase)

@given(u'sti build {application}')
@given(u'sti build {application} from {path}')
def sti_build(context, application, path='.'):
    context.image = context.config.userdata.get('IMAGE', 'ctf')
    image_id = "integ-" + context.image
    command = "sti build --loglevel=5 --forcePull=false --contextDir=%s %s %s %s" % (path, application, context.image, image_id)
    logging.info("Executing new STI build...")
    if _execute(command):
        logging.info("STI build succeeded, image %s was built" % image_id)
    else:
        logging.error("STI build failed, check logs!")
    context.container = Container(image_id, save_output = False)
    context.container.start()


@given(u'container is started with env')
@when(u'container is started with env')
def start_container(context):
    env = {}
    for row in context.table:
        env[row['variable']] = row['value']
    context.container = Container(context.image, save_output = False)
    context.container.start(environment = env)

def _execute(command, **kwargs):
    """
    Helper method to execute a shell command and redirect the logs to logger
    with proper log level.
    """

    logging.debug("Executing '%s' command..." % command)

    try:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        
        levels = {
            process.stdout: logging.DEBUG,
            process.stderr: logging.ERROR
        }

        def read_output():
            ready = select.select([process.stdout, process.stderr], [], [], 1000)[0]
            read = False
            for output in ready:
                line = output.readline()[:-1]
                if line:
                    # fix it
                    logging.log(levels[output], line)
                    read = True
            return read

        while True:
            if not read_output():
                break

        process.wait()
    except subprocess.CalledProcessError as e:
        logging.error("Command '%s' failed, check logs" % command)
        return False

    return True
