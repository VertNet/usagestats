from google.appengine.ext import ndb
import webapp2

from models import Report

from util import *
from jinjafilters import *

__author__ = 'jotegui'


class DatasetViewer(webapp2.RequestHandler):
    def get(self, gbifdatasetid):

        dataset_key = ndb.Key("Dataset", gbifdatasetid)

        query = Report.query(Report.reported_resource == dataset_key)
        query = query.order(-Report.reported_period)
        report_keys = query.fetch(keys_only=True)

        period_list = [
            {
                "text": x.id().split("|")[0][:4]+"-"+x.id().split("|")[0][4:],
                "url": x.id().split("|")[0]
            } for x in report_keys]

        template = JINJA_ENVIRONMENT.get_template('dataset.html')
        self.response.write(template.render(
            dataset=dataset_key.get(),
            period_list=period_list,
            periods=len(period_list)
        ))
