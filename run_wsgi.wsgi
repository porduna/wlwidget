#!/usr/bin/env python

import os
import sys

class MyFile(file):
    def write(self, *args, **kwargs):
        out = file.write(self, *args, **kwargs)
        self.flush()
        return out

f = MyFile("/tmp/logs_wlwidget", 'w')
sys.stdout = sys.stderr = f

DIR = os.path.dirname(__file__)

os.environ['WLWIDGET_SETTINGS'] = os.path.join(DIR,'secret_credentials.py')

sys.path.insert(0, DIR)

from wlwidget import app as application
