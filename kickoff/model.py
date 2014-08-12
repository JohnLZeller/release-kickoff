from datetime import datetime, timedelta

import pytz
import json

from sqlalchemy import func
from sqlalchemy.ext.hybrid import hybrid_property

from mozilla.release.info import getReleaseName

from kickoff import db


class Release(object):

    """A base class with all of the common columns for any release."""
    name = db.Column(db.String(100), primary_key=True)
    submitter = db.Column(db.String(250), nullable=False)
    _submittedAt = db.Column('submittedAt', db.DateTime(pytz.utc),
                             nullable=False, default=datetime.utcnow)
    version = db.Column(db.String(10), nullable=False)
    buildNumber = db.Column(db.Integer(), nullable=False)
    branch = db.Column(db.String(50), nullable=False)
    mozillaRevision = db.Column(db.String(100), nullable=False)
    l10nChangesets = db.Column(db.Text(), nullable=False)
    dashboardCheck = db.Column(db.Boolean(), nullable=False, default=False)
    ready = db.Column(db.Boolean(), nullable=False, default=False)
    complete = db.Column(db.Boolean(), nullable=False, default=False)
    status = db.Column(db.String(250), default="")
    mozillaRelbranch = db.Column(db.String(50), default=None, nullable=True)
    enUSPlatforms = db.Column(db.String(500), default=None, nullable=True)
    comment = db.Column(db.Text, default=None, nullable=True)

    # Dates are always returned in UTC time and ISO8601 format to make them
    # as transportable as possible.
    @hybrid_property
    def submittedAt(self):
        return pytz.utc.localize(self._submittedAt).isoformat()

    @submittedAt.setter
    def submittedAt(self, submittedAt):
        self._submittedAt = submittedAt

    def __init__(self, submitter, version, buildNumber, branch,
                 mozillaRevision, l10nChangesets, dashboardCheck,
                 mozillaRelbranch, enUSPlatforms=None, submittedAt=None,
                 comment=None):
        self.name = getReleaseName(self.product, version, buildNumber)
        self.submitter = submitter
        self.version = version.strip()
        self.buildNumber = buildNumber
        self.branch = branch.strip()
        self.mozillaRevision = mozillaRevision.strip()
        self.l10nChangesets = l10nChangesets
        self.dashboardCheck = dashboardCheck
        self.mozillaRelbranch = mozillaRelbranch
        self.enUSPlatforms = enUSPlatforms
        if submittedAt:
            self.submittedAt = submittedAt
        if comment:
            self.comment = comment

    def toDict(self):
        me = {'product': self.product}
        for c in self.__table__.columns:
            me[c.name] = getattr(self, c.name)
        me['submittedAt'] = me['submittedAt']
        return me

    @classmethod
    def createFromForm(cls, form):
        raise NotImplementedError

    def updateFromForm(self, form):
        self.version = form.version.data
        self.buildNumber = form.buildNumber.data
        self.branch = form.branch.data
        self.mozillaRevision = form.mozillaRevision.data
        self.l10nChangesets = form.l10nChangesets.data
        self.dashboardCheck = form.dashboardCheck.data
        self.mozillaRelbranch = form.mozillaRelbranch.data
        self.name = getReleaseName(self.product, self.version,
                                   self.buildNumber)
        self.comment = form.comment.data

    @classmethod
    def getRecent(cls, age=timedelta(weeks=7)):
        """Returns all releases of 'age' or newer."""
        since = datetime.now() - age
        return cls.query.filter(cls._submittedAt > since).all()

    @classmethod
    def getMaxBuildNumber(cls, version):
        """Returns the highest build number known for the version provided."""
        return cls.query \
            .with_entities(func.max(cls.buildNumber)) \
            .filter_by(version=version) \
            .one()[0]

    def __repr__(self):
        return '<Release %r>' % self.name


class FennecRelease(Release, db.Model):
    __tablename__ = 'fennec_release'
    product = 'fennec'

    @classmethod
    def createFromForm(cls, submitter, form):
        return cls(submitter, form.version.data,
                   form.buildNumber.data, form.branch.data,
                   form.mozillaRevision.data, form.l10nChangesets.data,
                   form.dashboardCheck.data, form.mozillaRelbranch.data,
                   form.comment.data)


class DesktopRelease(Release):
    partials = db.Column(db.String(100))
    promptWaitTime = db.Column(db.Integer(), nullable=True)

    def __init__(self, partials, promptWaitTime, *args, **kwargs):
        self.partials = partials
        self.promptWaitTime = promptWaitTime
        Release.__init__(self, *args, **kwargs)

    def updateFromForm(self, form):
        Release.updateFromForm(self, form)
        self.partials = form.partials.data
        self.promptWaitTime = form.promptWaitTime.data


class FirefoxRelease(DesktopRelease, db.Model):
    __tablename__ = 'firefox_release'
    product = 'firefox'

    @classmethod
    def createFromForm(cls, submitter, form):
        return cls(form.partials.data, form.promptWaitTime.data, submitter,
                   form.version.data, form.buildNumber.data, form.branch.data,
                   form.mozillaRevision.data, form.l10nChangesets.data,
                   form.dashboardCheck.data, form.mozillaRelbranch.data,
                   form.comment.data)


class ThunderbirdRelease(DesktopRelease, db.Model):
    __tablename__ = 'thunderbird_release'
    product = 'thunderbird'
    commRevision = db.Column(db.String(100))
    commRelbranch = db.Column(db.String(50))

    def __init__(self, commRevision, commRelbranch, *args, **kwargs):
        self.commRevision = commRevision
        self.commRelbranch = commRelbranch
        DesktopRelease.__init__(self, *args, **kwargs)

    @classmethod
    def createFromForm(cls, submitter, form):
        return cls(form.commRevision.data, form.commRelbranch.data,
                   form.partials.data, form.promptWaitTime.data, submitter,
                   form.version.data, form.buildNumber.data, form.branch.data,
                   form.mozillaRevision.data, form.l10nChangesets.data,
                   form.dashboardCheck.data, form.mozillaRelbranch.data,
                   form.comment.data)

    def updateFromForm(self, form):
        DesktopRelease.updateFromForm(self, form)
        self.commRevision = form.commRevision.data
        self.commRelbranch = form.commRelbranch.data


def getReleaseTable(release):
    """Helper method to figure out what type of release a request is for.
       Because the API methods are not specific to the type of release, we
       need this to make sure we operate on the correct table."""
    release = release.lower()
    if release.startswith('fennec'):
        return FennecRelease
    elif release.startswith('firefox'):
        return FirefoxRelease
    elif release.startswith('thunderbird'):
        return ThunderbirdRelease
    else:
        raise ValueError("Can't find release table for release %s" % release)


def getReleases(ready=None, complete=None):
    filters = {}
    if ready is not None:
        filters['ready'] = ready
    if complete is not None:
        filters['complete'] = complete
    releases = []
    for table in (FennecRelease, FirefoxRelease, ThunderbirdRelease):
        if filters:
            for r in table.query.filter_by(**filters):
                releases.append(r)
        else:
            for r in table.query.all():
                releases.append(r)
    return releases


class ReleaseEvents(db.Model):

    """A base class to store release events primarily from buildbot."""
    __tablename__ = 'release_events'
    name = db.Column(db.String(100), nullable=False, primary_key=True)
    sent = db.Column(db.DateTime(pytz.utc), nullable=False)
    event_name = db.Column(db.String(150), nullable=False, primary_key=True)
    platform = db.Column(db.String(500), nullable=True)
    results = db.Column(db.Integer(), nullable=False)
    chunkNum = db.Column(db.Integer(), default=0, nullable=False)
    chunkTotal = db.Column(db.Integer(), default=0, nullable=False)
    group = db.Column(db.String(100), default=None, nullable=True)

    def __init__(self, name, sent, event_name, platform, results, chunkNum=0,
                 chunkTotal=0, group=None):
        self.name = name
        self.sent = sent
        self.event_name = event_name
        self.platform = platform
        self.results = results
        self.chunkNum = chunkNum
        self.chunkTotal = chunkTotal
        self.group = group

    def toDict(self):
        me = {}
        for c in self.__table__.columns:
            me[c.name] = str(getattr(self, c.name))
        return me

    @classmethod
    def createFromRequest(cls, form):
        #TODO: This is a really hacky way to remove the possible timezone from the end of
        #      the form['sent'] string. Ideally, we would convert the timezone to datetime
        #      also, but datetime.strftime will not parse timezone offsets. Temporary
        #      solution it to just cut it off and remove it completely
        if '+' in form['sent'][-6:] or '-' in form['sent'][-6:]:
            form['sent'] = datetime.strptime(form['sent'][:-6], "%Y-%m-%dT%H:%M:%S")
        else:
            form['sent'] = datetime.strptime(form['sent'], "%Y-%m-%dT%H:%M:%S")
        return cls(form.get('name'), form.get('sent'), form.get('event_name'),
                   form.get('platform'), form.get('results'), form.get('chunkNum'),
                   form.get('chunkTotal'), form.get('group'))

    def __repr__(self):
        return '<ReleaseEvents %r>' % self.name


    def getEvents(group=None):
        filters = {}
        if group is not None:
            filters['group'] = group
        if filters:
            return ReleaseEvents.query.filter_by(**filters)
        else:
            return ReleaseEvents.query.all()


    def getStatus(name):
        if not ReleaseEvents.query.filter_by(name=name).first():
            return None
        status = {'tag': tagStatus, 'build': buildStatus, 'repack': repackStatus,
                  'update': updateStatus, 'releasetest': releasetestStatus,
                  'readyforrelease': readyForReleaseStatus, 'postrelease': postreleaseStatus}
        for step in status:
            status[step] = status[step](name)
        status['name'] = name
        return status


    def tagStatus(name):
        if ReleaseEvents.query.filter_by(name=name, group='tag').count() > 0:
            return {'progress': 0.00}
        return {'progress': 1.00}


    def buildStatus(name):
        build_events = ReleaseEvents.query.filter_by(name=name, group='build')

        builds = {'platforms': {}, 'progress': 0.00}
        for platform in getEnUSPlatforms(name):
            builds['platforms'][platform] = 0.00

        for build in build_events:
            builds['platforms'][build.platform] = 1.00
            builds['progress'] += (1.00/len(builds['platforms']))

        return builds


    def repackStatus(name):
        repack_events = ReleaseEvents.query.filter_by(name=name, group='repack')

        repacks = {'platforms': {}, 'progress': 0.00}
        for platform in getEnUSPlatforms(name):
            repacks['platforms'][platform] = 0.00

        for repack in repack_events:
            if 'complete' not in repack.event_name:
                repacks['platforms'][repack.platform]['progress'] += (1.00/repack.chunkTotal)
            else:
                # TODO: Make sure thaty we catch scenario where not all chunks, but have repack_complete
                repacks[repack.platform]['progress'] = 1.00

        # TODO: Assumes platforms have varying chunkTotal
        repacks['progress'] = (sum(repacks['platforms'].values()) / len(repacks['platforms']))

        # TODO: Ensure that progress is rounded

        return repacks


    def updateStatus(name):
        if ReleaseEvents.query.filter_by(name=name, group='update').count() > 0:
            return {'progress': 0.00}
        return {'progress': 1.00}


    def releasetestStatus(name):
        if ReleaseEvents.query.filter_by(name=name, group='releasetest').count() > 0:
            return {'progress': 0.00}
        return {'progress': 1.00}


    def readyForReleaseStatus(name):
        update_verify_events = ReleaseEvents.query.filter_by(name=name, group='update_verify')
        release_events = ReleaseEvents.query.filter_by(name=name, group='release')

        update_verifys = {}
        for platform in getEnUSPlatforms(name):
            update_verifys[platform] = 0.00

        for update_verify in update_verify_events:
            if 'complete' not in update_verify.event_name:
                update_verifys[update_verify.platform]['progress'] += (1.00/update_verify.chunkTotal)
            else:
                # TODO: Make sure that we catch scenario where not all chunks, but have update_verify_complete
                update_verifys[update_verify.platform]['progress'] = 1.00
        data = {'platforms': update_verifys, 'progress': 0.00}

        # TODO: Assumes platforms have varying chunkTotal
        data['progress'] = (sum(data['platforms'].values()) / len(data['platforms']))

        # TODO: Ensure that progress is rounded

        if release_events.first():
            data['progress'] = 1.00

        return data


    def postreleaseStatus(name):
        if ReleaseEvents.query.filter_by(name=name, event_name.like('%postrelease%')).count() > 0:
            return {'progress': 1.00}
        return {'progress': 0.00}


    def getEnUSPlatforms(name):
        releaseTable = getReleaseTable(name.split('-')[0].title())
        release = releaseTable.query.filter_by(name=name).first()
        return json.loads(release.enUSPlatforms)
