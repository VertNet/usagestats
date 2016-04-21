import json

from google.appengine.ext import ndb
from google.appengine.api import urlfetch
import webapp2

from models import Dataset

from util import cartodb_query

__author__ = 'jotegui'


class DatasetsSetup(webapp2.RequestHandler):
    """Populates the datastore with Dataset objects."""
    def post(self):
        urlfetch.set_default_fetch_deadline(60)
        self.response.headers['Content-Type'] = 'application/json'

        q = "select gbifdatasetid, icode, orgname, github_orgname, " \
            "source_url, github_reponame, url, gbifpublisherid " \
            "from resource_staging " \
            "where ipt=true and networks like '%VertNet%'"
        resources = cartodb_query(q)

        ds = []
        for resource in resources:
            ds.append(Dataset(id=resource['gbifdatasetid'], **resource))

        keys = ndb.put_multi(ds)

        result = {
            "datasets processed": len(keys),
        }

        self.response.write(json.dumps(result))
        return
