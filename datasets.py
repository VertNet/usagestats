from google.appengine.ext import ndb
from google.appengine.api import urlfetch

import json
from urllib import urlencode
import webapp2

from util import *
from models import Dataset

__author__ = 'jotegui'


class DatasetsSetupHandler(webapp2.RequestHandler):
    """Populates the datastore with Dataset objects."""
    def get(self):
        urlfetch.set_default_fetch_deadline(60)
        self.response.headers['Content-Type'] = 'application/json'

        q = "select gbifdatasetid, icode, orgname, github_orgname, " \
            "source_url, github_reponame, url, gbifpublisherid " \
            "from resource_staging " \
            "where ipt=true and networks like '%VertNet%'"
        params = {
            "q": q,
            "api_key": apikey('cdb')
        }
        payload = urlencode(params)

        resp = urlfetch.fetch(
            url=cdb_url,
            payload=payload,
            method=urlfetch.POST
        )
        resources = json.loads(resp.content)['rows']

        ds = []
        for resource in resources:

            ds.append(Dataset(id=resource['gbifdatasetid'], **resource))

        keys = ndb.put_multi(ds)

        result = {
            "datasets processed": len(keys),
        }
        self.response.write(json.dumps(result))
