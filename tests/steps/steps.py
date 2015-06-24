from behave import when, then, given
import subprocess
import time
import os
import requests
import logging
import select
import socket
import fcntl
from time import sleep
from docker import Client
from container import Container, ExecException

DOCKER_CLIENT = Client()
LOG_FORMAT='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(format=LOG_FORMAT)

@when(u'container is ready')
def container_is_started(context):
    context.container = Container(context.image, name=context.scenario.name)
    context.container.start()

@then(u'the image should contain label {label}')
@then(u'the image should contain label {label} {check} value {value}')
def label_exists(context, label, check="with", value=None):
    metadata = DOCKER_CLIENT.inspect_image(context.image)
    config = metadata['Config']

    try:
        labels = config['Labels']
    except KeyError:
        raise Exception("There are no labels in the %s image" % context.image)

    try:
        actual_value = labels[label]
    except KeyError:
        raise Exception("Label %s was not found in the %s image" % (label, context.image))

    if not value:
        return True

    if check == "with" and actual_value == value:
            return True
    elif check == "containing" and actual_value.find(value) >= 0:
            return True

    raise Exception("The %s label does not contain %s value, current value: %s" % (label, value, actual_value))

@then(u'check that page is not served')
def check_page_is_not_served(context):
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
    try:
        handle_request(context, port, wait, timeout, expected_status_code, path, expected_phrase)
    except:
        return True
    raise Exception("Page was served")


@then(u'check that page is served')
def check_page_is_served(context):
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
    handle_request(context, port, wait, timeout, expected_status_code, path, expected_phrase)

def handle_request(context, port, wait, timeout, expected_status_code, path, expected_phrase):
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

@then(u'container log should not contain {message}')
def log_not_contains_msg(context, message):
    try:
        log_contains_msg(context, message)
        raise Exception("log contains %s" % message)
    except:
        pass

@then(u'container log should contain {message}')
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

@then(u'run {cmd} in container and immediately check its output for {output_phrase}')
@then(u'run {cmd} in container and immediately check its output contains {output_phrase}')
def run_command_immediately_expect_message(context, cmd, output_phrase):
    output = context.container.execute(cmd=cmd)
    if not output_phrase in output:
        raise Exception("run_command_expect_message didn't find message", output)
    return True

@then(u'run {cmd} in container and immediately check its output does not contain {output_phrase}')
def run_command_immediately_unexpect_message(context, cmd, output_phrase):
    try:
        run_command_immediately_expect_message(context, cmd, output_phrase)
    except:
        return True
    raise Exception("commmand output contains prohibited text")

@then(u'run {cmd} in container and check its output does not contain {output_phrase}')
def run_command_unexpect_message(context, cmd, output_phrase):
    try:
        run_command_expect_message(context, cmd, output_phrase)
    except:
        return True
    raise Exception("commmand output contains prohibited text")

@then(u'run {cmd} in container and check its output for {output_phrase}')
@then(u'run {cmd} in container and check its output contains {output_phrase}')
@then(u'run {cmd} in container')
def run_command_expect_message(context, cmd, output_phrase):
    start_time = time.time()
    while time.time() < start_time + 80:
        last_output = None
        try:
            output = context.container.execute(cmd=cmd)
            if output_phrase in output:
                return True
        except ExecException as e:
            last_output = e.output
            time.sleep(1)
    raise Exception("run_command_expect_message didn't find message", last_output)


@then('file {filename} should contain {phrase}')
def file_should_contain(context, filename, phrase):
     run_command_expect_message(context, 'cat %s' % filename, phrase)

@given(u'sti build {application}')
@given(u'sti build {application} from {path}')
def sti_build(context, application, path='.'):
    context.image = context.config.userdata.get('IMAGE', 'ctf')
    image_id = "integ-" + context.image
    command = "sti build --loglevel=5 --force-pull=false --context-dir=%s %s %s %s" % (path, application, context.image, image_id)
    logging.info("Executing new STI build...")
    if _execute(command):
        logging.info("STI build succeeded, image %s was built" % image_id)
    else:
        logging.error("STI build failed, check logs!")
    context.container = Container(image_id, name=context.scenario.name)
    context.container.start()


@given(u'container is started with env')
@when(u'container is started with env')
def start_container(context):
    env = {}
    for row in context.table:
        env[row['variable']] = row['value']
    context.container = Container(context.image, name=context.scenario.name)
    context.container.start(environment = env)

@given(u'image is built')
def image(context):
    pass

@given(u'container is started as uid {uid}')
@when(u'container is started as uid {uid}')
def start_container(context, uid):
    if uid < 0:
        raise Exception("UID %d is negative" % uid)
    context.container = Container(context.image, save_output = False)
    context.container.start(user = uid)


@then(u'check that port {port} is open')
def check_port_open(context, port):
    start_time = time.time()

    ip = context.container.ip_address
    logging.info("connecting to %s port %s" % (ip, port))
    while time.time() < start_time + 30:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect((ip, int(port)))
            s.close()
            return True
        except Exception as ex:
            logging.debug("not connected yes %s" %ex)
        time.sleep(1)
    raise Exception("Port %s is not open" %port)

@then(u'file {file_name} should exist')
@then(u'file {file_name} should exist and be a {file_type}')
#TODO: @then(u'file {file_name} should exist and have {permission} permissions')
def check_file_exists(context, file_name, file_type = None):
    try:
        context.container.execute("test -e %s" % file_name)
    except ExecException:
        raise Exception("File %s does not exist" % file_name)

    if file_type:
        if file_type == "directory":
            try:
                context.container.execute("test -d %s" % file_name)
            except ExecException:
                raise Exception("File %s is not a directory" % file_name)
        elif file_type == "symlink":
            try:
                context.container.execute("test -L %s" % file_name)
            except ExecException:
                raise Exception("File %s is not a symlink" % file_name)

    return True

def _execute(command, log_output = True):
    """
    Helper method to execute a shell command and redirect the logs to logger
    with proper log level.
    """

    logging.debug("Executing '%s' command..." % command)

    try:
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


        levels = {
            proc.stdout: logging.DEBUG,
            proc.stderr: logging.ERROR
        }

        fcntl.fcntl(
            proc.stderr.fileno(),
            fcntl.F_SETFL,
            fcntl.fcntl(proc.stderr.fileno(), fcntl.F_GETFL) | os.O_NONBLOCK,
        )

        fcntl.fcntl(
            proc.stdout.fileno(),
            fcntl.F_SETFL,
            fcntl.fcntl(proc.stdout.fileno(), fcntl.F_GETFL) | os.O_NONBLOCK,
        )

        if log_output:
            while proc.poll() == None:
                readx = select.select([proc.stdout, proc.stderr], [], [])[0]
                for output in readx:
                    line = output.readline()[:-1]
                    logging.log(levels[output], line)

        retcode = proc.wait()

        if retcode is not 0:
            logging.error("Command '%s' returned code was %s, check logs" % (command, retcode))
            return False

    except subprocess.CalledProcessError as e:
        logging.error("Command '%s' failed, check logs" % command)
        return False

    return True
