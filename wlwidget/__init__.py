import sys
import os
import urllib2
import json

from flask import Flask, render_template, request, url_for
app = Flask(__name__)

if os.uname()[1] in ('plunder','scabb'): # Deusto servers
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
        space_owner_str = urllib2.urlopen("http://shindig.epfl.ch/rest/people/@owner/@self?st=%s" % st).read()
        owner_data = json.loads(space_owner_str)

        owner_name = owner_data['entry']['displayName']
        owner_id   = owner_data['entry']['id']

        current_user_str  = urllib2.urlopen("http://shindig.epfl.ch/rest/people/@me/@self?st=%s" % st).read()
        current_user_data = json.loads(current_user_str)
        
        name    = current_user_data['entry'].get('displayName') or 'anonymous'
        user_id = current_user_data['entry'].get('id') or 'no-id'

        return render_template("contents.html", name = name, id = user_id, owner = owner)
    except Exception as e:
        return "Error: %s" % e

@app.route("/widget.xml")
@app.route("/widget<id>.xml")
def widget(id):
    return render_template('widget.xml', url = url_for('main', _external=True))

@app.route('/')
def index():
    return render_template('index.html')

