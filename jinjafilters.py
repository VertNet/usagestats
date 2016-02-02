import os
import jinja2

__author__ = 'jotegui'


def query_countries_format(query_countries):

    return [["Country", "Events"]]+[[str(x.query_country), x.times] for x in query_countries if x.query_country != "Unknown"]


def query_dates_format(query_dates):

    return [["Date", "Events"]]+sorted([[x.query_date.day, x.times] for x in query_dates])


def query_terms_format(query_terms):

    return [["Terms", "Records retrieved"]]+[["%s (%d time/s)" % (str(x.query_terms), x.times), x.records] for x in query_terms]


def percentage_format(fl):

    return str(round(fl, 2))+"%"


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

JINJA_ENVIRONMENT.filters['querycountriesformat'] = query_countries_format
JINJA_ENVIRONMENT.filters['querydatesformat'] = query_dates_format
JINJA_ENVIRONMENT.filters['querytermsformat'] = query_terms_format
JINJA_ENVIRONMENT.filters['percentageformat'] = percentage_format