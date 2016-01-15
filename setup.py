import base64
from datetime import datetime
import json
import logging
# import os
# from urllib import urlencode

from models import *
from util import *

from google.appengine.api import urlfetch, taskqueue
# from google.appengine.api import modules
from google.appengine.ext import ndb
from models import Report

import jinja2
import webapp2

__author__ = 'jotegui'


# GitHub-specific params
ghb_url = 'https://api.github.com'
ghb_headers = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "jotegui",
    "Authorization": "token {0}".format(apikey('ghb'))
}
ghb_org = 'jotegui'
ghb_rep = 'statReports'
tree_sha = '491528cecf9956e69e22d22d2349436142d2cbb6'


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class ReportsSetupHandler(webapp2.RequestHandler):
    def get(self):
        urlfetch.set_default_fetch_deadline(60)

        resp = urlfetch.fetch(
            url='/'.join([ghb_url, "repos", ghb_org, ghb_rep, "git", "trees", tree_sha]),
            headers=ghb_headers,
            method=urlfetch.GET
        )

        reports = json.loads(resp.content)['tree']
        self.response.headers['content-type'] = "application/json"
        self.response.write(json.dumps(reports[0]))


