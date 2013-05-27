import os
import sys
import json
import time
import urllib2
import datetime
import threading
import traceback

from flask import Flask, render_template, request, url_for, redirect, abort

from wlwidget.weblabdeusto_client import WebLabDeustoClient
from wlwidget.weblabdeusto_data import ExperimentId, SessionId, Reservation

# These variables can be configured in the WLWIDGET_SETTINGS
#WEBLABDEUSTO_BASEURL = 'https://www.weblab.deusto.es/weblab/'
#WEBLABDEUSTO_LOGIN   = 'weblabfed'
#WEBLABDEUSTO_PASSWD  = 'password'

app = Flask(__name__)
app.config.from_object(__name__)
app.config.from_envvar('WLWIDGET_SETTINGS', silent=True)

if os.uname()[1] in ('plunder','scabb'): # Deusto servers
    print "Installing proxy handler...",
    import urllib2
    proxy = urllib2.ProxyHandler({'http': 'http://proxy-s-priv.deusto.es:3128/'})
    opener = urllib2.build_opener(proxy)     
    urllib2.install_opener(opener)
    print "done"

@app.route("/lab/<reservation_id>/")
def confirmed(reservation_id):
    task_data = TASK_MANAGER.get_task(reservation_id)
    status = task_data['status']
    base_url = status.url or app.config['WEBLABDEUSTO_BASEURL']
    print "status.url = %s; app config url = %s. Chosen: %s" % (status.url, app.config['WEBLABDEUSTO_BASEURL'], base_url)
    used_reservation_id = status.remote_reservation_id.id or reservation_id
    print "status.remote_reservation_id.id = %s; reservation_id = %s. Chosen: %s" % (status.remote_reservation_id.id, reservation_id, used_reservation_id)
    sys.stdout.flush()
    url = "%sclient/federated.html#reservation_id=%s" % (base_url, used_reservation_id)
    return render_template('confirmed.html', url = url, reservation_id = reservation_id)

@app.route("/status/<reservation_id>/")
def get_status(reservation_id):
    try:
        refresh = True
        try:
            task_data = TASK_MANAGER.get_task(reservation_id)
        except KeyError:
            return abort(404)
        
        status = task_data['status']

        refresh_time = 1

        if status is None:
            if task_data['finished']:
                return "ERROR: It was finished"
            waiting_message = "Starting reservation..."
            refresh_time = 0.5
        elif status.status == Reservation.WAITING:
            waiting_message = 'In queue; position %s' % status.position
        elif status.status == Reservation.WAITING_CONFIRMATION:
            waiting_message = 'Waiting confirmation from the lab'
            refresh_time = 0.5
        elif status.status == Reservation.WAITING_INSTANCES:
            waiting_message = 'Experiment broken. Waiting for admin to fix them. Position: %s' % status.position
            refresh_time = 10
        elif status.status == Reservation.CONFIRMED:
            return redirect(url_for('confirmed', reservation_id = reservation_id))
        else:
            # POST_RESERVATION IS REMOVED
            waiting_message = 'Unknown status. Contact admin'

        return render_template('get_status.html', waiting_message = waiting_message, refresh = refresh, refresh_time = refresh_time)
    except Exception as e:
        traceback.print_exc()
        return "Error: %s" % e

@app.route("/reserve/<laboratory_id>/")
def reserve(laboratory_id):
    if '@' not in laboratory_id:
        laboratory_id = urllib2.unquote(laboratory_id)
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

        # Many are not used (yet)

        client = WebLabDeustoClient(app.config['WEBLABDEUSTO_BASEURL'])
        session_id = client.login(app.config['WEBLABDEUSTO_LOGIN'], app.config['WEBLABDEUSTO_PASSWD'])

        consumer_data = {
            "user_agent"    : request.headers.get('User-Agent') or None,
            "referer"       : request.referrer,
            "from_ip"       : request.remote_addr,
            "external_user" : user_id,
            #     "priority"      : "...", # the lower, the better
            #     "time_allowed"  : 100,   # seconds
            #     "initialization_in_accounting" :  False,
        }
        consumer_data_str = json.dumps(consumer_data)
        reservation_status = client.reserve_experiment(session_id, ExperimentId.parse(laboratory_id), '{}', consumer_data_str)
        reservation_id = reservation_status.reservation_id.id
        TASK_MANAGER.add_task(client, reservation_id, session_id, name, consumer_data)
        return redirect(url_for('get_status', reservation_id = reservation_id))
    except Exception as e:
        traceback.print_exc()
        return "Error: %s" % e

@app.route("/widget.xml")
@app.route("/widget<id>.xml")
def widget(id = None):
    widget = request.args.get('widget') or 'camera'
    lab    = request.args.get('lab') or 'ud-logic@PIC experiments'
    return render_template('widget.xml', url = url_for('reserve', laboratory_id = lab, _external = True), widget = widget)


@app.route('/')
def index():
    return render_template('index.html')

LAST_ACTIVITY = "not set"

@app.route('/last-activity')
def last_activity():
    return LAST_ACTIVITY

def serialize_experiment_use(experiment_use, name, consumer_data):

    display_name = name
    user_id      = consumer_data['external_user']
    origin       = consumer_data['from_ip']
    user_agent   = consumer_data['user_agent']
    referer      = consumer_data['referer']
    # TODO
    locale       = "to be set"


    activity_stream = {}
    ##########################
    # 
    #        General
    #   
    # TODO: UTC to ...
    activity_stream['published']      = datetime.datetime.fromtimestamp(experiment_use.start_date).strftime("%Y-%m-%d %H:%M:%S.%sZ")
    activity_stream['finished']       = datetime.datetime.fromtimestamp(experiment_use.end_date).strftime("%Y-%m-%d %H:%M:%S.%sZ")
    activity_stream['reservation-id'] = experiment_use.reservation_id
    activity_stream['verb']           = 'post'

    activity_stream['target'] = {
        'objectType' : 'remote-lab',
        'id'         : experiment_use.experiment_id.to_weblab_str(),
        'rig'        : experiment_use.coord_address.address,
    }

    activity_stream['actor'] = {
        'objectType'       : 'person',
        'displayName'      : display_name,
        'id'               : user_id,
        'origin'           : origin,
        'federated-server' : None,
        'federated-user'   : None,
        'mobile'           : False,
        'facebook'         : False,
        'user-agent'       : user_agent,
        'language'         : locale,
        'referer'          : referer,
    }

    attachments = []
    for pos, command in enumerate(experiment_use.commands):
        attachments.append({
            'published'  : datetime.datetime.fromtimestamp(command.timestamp_before).strftime("%Y-%m-%d %H:%M:%S.%sZ"),
            'finished'   : datetime.datetime.fromtimestamp(command.timestamp_after).strftime("%Y-%m-%d %H:%M:%S.%sZ"),
            'objectType' : 'command',
            'id'         : '%s::%s' % (experiment_use.experiment_use_id, pos),
            'request'    : command.command.commandstring,
            'response'   : command.response.commandstring,
        })

    activity_stream['object'] = {
        'objectType'  : "reservation",
        'id'          : experiment_use.experiment_use_id,
        'attachments' : attachments,
    }

    return json.dumps(activity_stream, indent = True)

def process_experiment_use(experiment_use, name, consumer_data):
    activity_stream = serialize_experiment_use(experiment_use, name, consumer_data)
    global LAST_ACTIVITY
    LAST_ACTIVITY = activity_stream


class TaskManager(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.setName("wlwidget-TaskManager")
        self.lock = threading.Lock()
        self.reservations = {}

    def add_task(self, client, reservation_id, session_id, name, consumer_data):
        with self.lock:
            self.reservations[reservation_id] = dict( client=client, session_id = session_id, status = None, last_poll = time.time(), finished = False, name = name, consumer_data = consumer_data )

    def get_task(self, reservation_id):
        with self.lock:
            return self.reservations[reservation_id].copy()

    def run(self):
        while True:
            try:
                reservations = []
                with self.lock:
                    for reservation_id in self.reservations:
                        reservation_data = self.reservations[reservation_id]
                        TIME_BETWEEN_POLLS = 2 # seconds
                        if time.time() - reservation_data['last_poll'] > TIME_BETWEEN_POLLS:
                            reservations.append((reservation_id, reservation_data))

                reservations_to_remove = []

                for reservation_id, reservation_data in reservations:
                    client        = reservation_data['client']
                    session_id    = reservation_data['session_id']
                    name          = reservation_data['name']
                    consumer_data = reservation_data['consumer_data']
                    try:
                        print "Retrieving reservation...", reservation_id
                        sys.stdout.flush()
                        reservation_status = client.get_reservation_status(SessionId(reservation_id))
                        print "Done:", reservation_status
                        sys.stdout.flush()
                    except Exception as e:
                        traceback.print_exc()
                        reservations_to_remove.append(reservation_id)
                        continue
                    else:
                        reservation_data['status'] = reservation_status
                        if reservation_status.status == 'Reservation::post_reservation':
                            try:
                                experiment_use = client.get_experiment_use_by_id(session_id, SessionId(reservation_id))
                                if experiment_use.is_alive():
                                    pass
                                elif experiment_use.is_cancelled() or experiment_use.is_forbidden():

                                    reservations_to_remove.append(reservation_id)
                                elif experiment_use.is_finished():
                                    reservations_to_remove.append(reservation_id)
                                    try:
                                        process_experiment_use(experiment_use.experiment_use, name, consumer_data)
                                    except:
                                        traceback.print_exc()
                                        print "Error processing experiment use"

                                else:
                                    print "Error: didn't know how to process", experiment_use
                            except:
                                print "Error retrieving experiment use"
                                traceback.print_exc()

                with self.lock:
                    for reservation_id in reservations_to_remove:
                        self.reservations.pop(reservation_id)
            except:
                traceback.print_exc()
            time.sleep(0.2)

TASK_MANAGER = TaskManager()
TASK_MANAGER.start()

