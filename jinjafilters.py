__author__ = 'jotegui'


def query_countries_format(query_countries):

    return [["Country", "Events"]]+[[str(x.query_country), x.times] for x in query_countries if x.query_country != "Unknown"]


def query_dates_format(query_dates):

    return [["Date", "Events"]]+sorted([[x.query_date.day, x.times] for x in query_dates])


def query_terms_format(query_terms):

    return [["Terms", "Records retrieved"]]+[["%s (%d time/s)" % (str(x.query_terms), x.times), x.records] for x in query_terms]


def percentage_format(fl):

    return str(round(fl, 2))+"%"
