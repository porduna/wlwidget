import sys
import os
import urllib2
import json

from flask import Flask, render_template, request
app = Flask(__name__)

if os.uname()[1] == 'plunder':
    print "Installing proxy handler...",
    import urllib2
    proxy = urllib2.ProxyHandler({'http': 'http://proxy-s-priv.deusto.es:3128/'})
    opener = urllib2.build_opener(proxy)     
    urllib2.install_opener(opener)
    print "done"


@app.route("/main/")
def main():
    st = request.args.get('st') or ''
    try:
        content = urllib2.urlopen("http://shindig.epfl.ch/rest/people/@me/@self?st=%s" % st).read()
        content = json.loads(content)
        name = (content['entry'].get('displayName') or 'anonymous')
        return render_template("contents.html", name = name)
    except Exception as e:
        return "Error: %s" % e

@app.route("/widget.xml")
def widget():
    return render_template('widget.xml')

@app.route('/')
def index():
    return render_template('index.html')

