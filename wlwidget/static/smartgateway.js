function trace(msg) {
    if (console && console.log) 
        console.log(msg);
}

function SmartGateway(container, url) {

    var me = this;
    this._identifier = Math.random();
    this._container = container;

    this._imMaster = false;

    this._LOADING_TIME     = 400; // ms
    this._inLoadingPeriod  = true;
    this._imMasterTemporal = false; // During the loading period, see if I'm gonna be one
    this._forceNotMaster   = false; // If after the loading time, somebody comes back, define "no, you're not the master"

    this._loadCallback = null;

    this._init = function() {
        gadgets.openapp.publish({
            event: "select",
            type: "json",
            message: {
                'wlwidget-msg' : 'wlwidget::master-solver',
                'wlwidget-id'     : me._identifier, 
            }
        });

        trace("Submitted " + me._identifier + "; now configuring timer: " + new Date().getTime());
        setTimeout(function(){ me._onLoadingTimeElapsed(); }, me._LOADING_TIME);
        gadgets.openapp.connect(me._onEvent);
    }

    this._setUpMaster = function() {
        me._imMaster = true;
        var token = shindig.auth.getSecurityToken();
        var srcString = url + '?st=' + token;
        me._container.innerHTML = '<iframe id="weblabIFrame" onload="gadgets.window.adjustHeight();" frameborder="0" width="100%" height="100%" src="'+srcString+'"></iframe>';
    }

    this._setUpSlave = function(){
        me._container.innerHTML = "Waiting for the master widget...";
    }

    this._onEvent = function(envelope, message) {
        // Solving who is the master: there are two periods: the first one, short (LOADING_TIME), on which all the widgets send a message.
        // The last message received by everybody will be the master. So everybody will think that they're the master until they receive
        // a message defining that they're not. If in LOADING_TIME no more systems define that they're the master, they everyone know that
        // they're the master. If later somebody comes in and says "hey, I'm the master", they will receive a message defining "no, you're 
        // not".
        if (message["wlwidget-msg"] == 'wlwidget::master-solver') {
            if (me._inLoadingPeriod) {
                trace("Still loading: I'm " + me._identifier + "; got: " + message['wlwidget-id']);
                
                if( me._forceNotMaster )
                    return true;

                if (message['wlwidget-id'] == me._identifier) {
                    me._imMasterTemporal = true;
                } else {
                    me._imMasterTemporal = false;
                }
            } else {
                trace("Not loading anymore: force not master");

                gadgets.openapp.publish({
                    event: "select",
                    type: "json",
                    message: {
                        'wlwidget-msg' : 'wlwidget::not-master',
                        'wlwidget-id'     : me._identifier, 
                    }
                });
            }
        } else if (message["wlwidget-msg"] == 'wlwidget::not-master') {
            trace("Got a force not master");
            me._forceNotMaster = true;
            me._onLoadingTimeElapsed();
        } else if (message["wlwidget-msg"] == 'wlwidget::activate') {
            if (!me._imMaster ) {
                if ( me._loadCallback != null )
                    me._loadCallback(message['wlwidget-reservation-id']);
                else
                    alert("No callback defined!");
            }
        }
        return true;
    }

    this._onLoadingTimeElapsed = function() {
        if ( !me._inLoadingPeriod )
            return;

        me._inLoadingPeriod = false;
        trace("Loading time elapsed: " + new Date().getTime() + "; force not master: " + me._forceNotMaster + "; imMasterTemporal: " + me._imMasterTemporal);

        if (me._forceNotMaster) {
            me._setUpSlave();
        } else {
            if(me._imMasterTemporal) {
                me._setUpMaster();
            } else {
                me._setUpSlave();
            }
        }
    }

    // Whenever the widget (being a master or a slave) gets a reservation
    // finished, this method is called.
    this.registerOnLoad = function(onLoadCallback) {
        this._loadCallback = onLoadCallback;
    };

    this._init();
}