"""
The MIT License (MIT)

Copyright (c) 2015 Red Hat

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.mgb
"""
from __future__ import print_function
import logging
from docker import Client
import os
import re
d = Client()

class ExecException(Exception):
    def __init__(self, message, output=None):
        super(ExecException, self).__init__(message)
        self.output = output

class Container(object):
    """
    Object representing a docker test container, it is used in tests
    """

    def __init__(self, image_id, name=None, remove_image = False, output_dir = "target", save_output=True, **kwargs):
        self.image_id = image_id
        self.container = None
        self.name = name
        self.ip_address = None
        self.output_dir = output_dir
        self.save_output = save_output
        self.remove_image = remove_image
        self.kwargs = kwargs
        self.logging = logging.getLogger("dock.middleware.container")
        self.running = False

    def __enter__(self):
        self.start(**self.kwargs)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        if self.remove_image:
            self.remove_image()

    def start(self, **kwargs):
        """ Starts a detached container for selected image """
        if self.running:
            self.logging.debug("Container is running")
            return
        self.logging.debug("Creating container from image '%s'..." % self.image_id)
        self.container = d.create_container(image=self.image_id, detach=True, **kwargs)
        self.logging.debug("Starting container '%s'..." % self.container.get('Id'))
        d.start(container=self.container)
        self.running = True
        self.ip_address =  d.inspect_container(container=self.container.get('Id'))['NetworkSettings']['IPAddress']

    def stop(self):
        """
        Stops (and removes) selected container.
        Additionally saves the STDOUT output to a `container_output` file for later investigation.
        """
        if self.running and self.save_output:
            if not self.name:
                self.name = self.container.get('Id')
            filename = "".join([c for c in self.name if re.match(r'\w', c)])
            out_path = self.output_dir + "/output-" + filename + ".txt"
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
            with open(out_path, 'w') as f:
                print(d.attach(container=self.container.get('Id'), stream=False, logs=True), file=f)
            f.closed
        if self.container:
            self.logging.debug("Removing container '%s'" % self.container['Id'])
            d.kill(container=self.container)
            self.running = False
            d.remove_container(self.container)

    def execute(self, cmd):
        """ executes cmd in container and return its output """
        inst = d.exec_create(container=self.container, cmd=cmd)

        output = d.exec_start(inst)
        retcode = d.exec_inspect(inst)['ExitCode']

        if retcode is not 0:
            raise ExecException("Command %s failed to execute, return code: %s" % (cmd, retcode), output)

    def get_output(self, history = True):
        return d.attach(container = self.container, stream = False, logs=history)

    def remove_image(self, force = False):
        self.logging.info("Removing image %s" % self.image_id)
        d.remove_image(image = self.image_id, force= force)


 
