import logging
import pytz
import json

from flask import request, jsonify, render_template, Response, redirect, make_response, abort
from flask.views import MethodView

from kickoff import db
from kickoff.log import cef_event, CEF_WARN, CEF_INFO, CEF_ALERT
from kickoff.model import ReleaseEvents, getEvents, getStatus
from kickoff.views.forms import ReleasesForm, ReleaseAPIForm, getReleaseForm

log = logging.getLogger(__name__)


def sortedEvents():
    def cmpEvents(x, y):
        return cmp(y.sent, x.sent)
    return sorted(getEvents(), cmp=cmpEvents)


class StatusAPI(MethodView):

    def get(self, releaseName):
        events = {'release': releaseName, 'events': [], 'status': {}}
        rows = ReleaseEvents.query.filter_by(name=releaseName)
        for row in rows:
            events['events'].append(row.toDict())
        events['status'] = getStatus(releaseName)
        return jsonify(events)

    def post(self, releaseName):
        # TODO: Look for and handle expected variables that have value as None
        releaseEventsUpdate = {}
        for field, value in request.form.items():
            releaseEventsUpdate[field] = value
        releaseEventsUpdate['name'] = releaseName
        releaseEventsUpdate.pop('csrf_token')

        # Create a ReleaseEvent object from the request data
        try:
            releaseEventsUpdate = ReleaseEvents.createFromRequest(
                releaseEventsUpdate)
        except Exception as e:
            log.error('User Input Failed - {} - ({}, {})'.format(e,
                      releaseEventsUpdate['name'],
                      releaseEventsUpdate['event_name']))
            cef_event('User Input Failed', CEF_ALERT)
            return Response(status=400, response=e)

        # Validate the POST data
        # TODO: Validate may not be necessary
        validity = True
        if not validity:
            cef_event('User Input Failed', CEF_INFO)
            return Response(status=400, response="Error in data")

        # Check if this ReleaseEvent already exists in the ReleaseEvents table
        if db.session.query(ReleaseEvents).\
                      filter(ReleaseEvents.name==releaseEventsUpdate.name,
                             ReleaseEvents.event_name==releaseEventsUpdate.event_name).first():
            msg = 'ReleaseEvents ({}, {}) already exists'.\
                   format(releaseEventsUpdate.name, releaseEventsUpdate.event_name)
            log.error('{}'.format(msg))
            cef_event('User Input Failed', CEF_INFO,
                      ReleaseName=releaseEventsUpdate.name)
            return Response(status=400, response=msg)

        # Add a new ReleaseEvents row to the ReleaseEvents table with new data
        db.session.add(releaseEventsUpdate)
        db.session.commit()
        log.debug('({}, {}) - added to the ReleaseEvents table in the database'.
                  format(releaseEventsUpdate.name, releaseEventsUpdate.event_name))

        return Response(status=200)
