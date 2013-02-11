import urllib2
import json

from flask import Flask, render_template, request
app = Flask(__name__)


@app.route("/main/")
def main():
    st = request.args.get('st') or ''
    try:
        content = urllib2.open("http://shindig.epfl.ch/rest/people/@me/@self?st=%s" % st).read()
        content = json.loads(content)
        return u'Hello, ' + (content['entry'].get('displayName') or 'null')
    except Exception as e:
        return "Error: %s" % e

@app.route("/widget.xml")
def widget():
    return render_template('widget.xml')

@app.route('/')
def index():
    return render_template('index.html')

