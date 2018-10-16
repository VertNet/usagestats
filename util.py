# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

__author__ = '@jotegui'
__contributors__ = "Javier Otegui, John Wieczorek"
__copyright__ = "Copyright 2018 vertnet.org"
__version__ = "util.py 2018-10-15T23:19-03:00"

from datetime import datetime
import time
import json
import logging
import os
from urllib import urlencode
from google.appengine.api import urlfetch, memcache
from config import *

CDB_QUERY_TOO_LARGE_ERROR = 'Your query was not able to finish.' + \
    ' Either you have too many queries running or the one you are trying' + \
    ' to run is too expensive. Try again.'

class ApiQueryMaxRetriesExceededError(Exception):
    pass

def apikey(serv):
    """Return credentials file as a JSON object."""
    path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                        '{0}.key'.format(serv))
    key = open(path, "r").read().rstrip()
    return key

def add_time_limit(query, today=datetime.today(), lapse='month'):
    """Add time limit to Carto query.

Default behavior is to extract stats from just the last month.
"""
    if lapse == 'month':
        this_year = today.year
        this_month = today.month
        if this_month == 1:
            limit_year = this_year - 1
            limit_month = 12
        else:
            limit_year = this_year
            limit_month = this_month - 1
        limit_string = " and extract(year from created_at)=%s" % limit_year
        limit_string += " and extract(month from created_at)=%s" % limit_month
        query += limit_string

    return query

def api_query(api_url, params):
    """Launch query to an API.

Send the specified query and retrieve the specified field.
"""
    urlfetch.set_default_fetch_deadline(60)
    finished = False
    max_retries = 3
    retries = 0
    while not finished:
        retries += 1
        if retries >= max_retries:
            err_msg = "Query failed after maximum retries"
            logging.error(err_msg)
            raise ApiQueryMaxRetriesExceededError(err_msg)
        d = urlfetch.fetch(
            url=api_url,
            method=urlfetch.POST,
            payload=urlencode(params)
        ).content
        d = json.loads(d)
        if "error" in d.keys():
            logging.warning("Warning, something went wrong with the query.")
            logging.warning(d['error'])
            logging.warning("This is the call that caused it:")
            logging.warning(api_url)
            logging.warning(urlencode(params))
            logging.warning("Retrying in 3 seconds"
                            " attempt %d of %d" % (retries+1, max_retries))
            time.sleep(3)
        else:
            finished = True
            logging.info("Got response from %s" % api_url)
            return d

def carto_query(query):
    """Build parameters for launching a query to the Carto API."""
    params = {'q': query, 'api_key': apikey(serv="cdb")}
    d = api_query(api_url=CDB_URL, params=params)['rows']
    logging.info("Returned %d rows" % len(d))
    return d

def geonames_query(lat, lon):
    """Build parameters for launching a query to the GeoNames API."""
    error = False
    if lat == 0 and lon == 0:
        error = True
    if abs(lat) > 90 or abs(lon) > 180:
        error = True
    if error is True:
        d = "Unknown"
        return d

    k = "|".join([str(round(lat, 2)), str(round(lon, 2))])
    d = memcache.get(k)

    if d is not None:
        # logging.info("Retrieved country from memcache")
        return d
    else:
        params = {
            'formatted': 'true',
            'lat': lat,
            'lng': lon,
            'username': 'jotegui',
            'style': 'full'
        }
        try:
            d = api_query(api_url=GNM_URL, params=params)['countryName']
        except KeyError:
            d = "Unknown"
        memcache.add(k, d)
        return d

# GitHub params
ghb_headers = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "jotegui",
    "Authorization": "token {0}".format(apikey('ghb'))
}
ghb_org = 'VertNet'
ghb_rep = 'statReports'
tree_sha = '491528cecf9956e69e22d22d2349436142d2cbb6'

# Structure of download files
fieldList_160 = [
    "datasource_and_rights",
    "type",
    "modified",
    "language",
    "rights",
    "rightsholder",
    "accessrights",
    "bibliographiccitation",
    "references",
    "institutionid",
    "collectionid",
    "datasetid",
    "institutioncode",
    "collectioncode",
    "datasetname",
    "ownerinstitutioncode",
    "basisofrecord",
    "informationwithheld",
    "datageneralizations",
    "dynamicproperties",
    "occurrenceid",
    "catalognumber",
    "occurrenceremarks",
    "recordnumber",
    "recordedby",
    "individualid",
    "individualcount",
    "sex",
    "lifestage",
    "reproductivecondition",
    "behavior",
    "establishmentmeans",
    "occurrencestatus",
    "preparations",
    "disposition",
    "othercatalognumbers",
    "previousidentifications",
    "associatedmedia",
    "associatedreferences",
    "associatedoccurrences",
    "associatedsequences",
    "associatedtaxa",
    "eventid",
    "samplingprotocol",
    "samplingeffort",
    "eventdate",
    "eventtime",
    "startdayofyear",
    "enddayofyear",
    "year",
    "month",
    "day",
    "verbatimeventdate",
    "habitat",
    "fieldnumber",
    "fieldnotes",
    "eventremarks",
    "locationid",
    "highergeographyid",
    "highergeography",
    "continent",
    "waterbody",
    "islandgroup",
    "island",
    "country",
    "countrycode",
    "stateprovince",
    "county",
    "municipality",
    "locality",
    "verbatimlocality",
    "verbatimelevation",
    "minimumelevationinmeters",
    "maximumelevationinmeters",
    "verbatimdepth",
    "minimumdepthinmeters",
    "maximumdepthinmeters",
    "minimumdistanceabovesurfaceinmeters",
    "maximumdistanceabovesurfaceinmeters",
    "locationaccordingto",
    "locationremarks",
    "verbatimcoordinates",
    "verbatimlatitude",
    "verbatimlongitude",
    "verbatimcoordinatesystem",
    "verbatimsrs",
    "decimallatitude",
    "decimallongitude",
    "geodeticdatum",
    "coordinateuncertaintyinmeters",
    "coordinateprecision",
    "pointradiusspatialfit",
    "footprintwkt",
    "footprintsrs",
    "footprintspatialfit",
    "georeferencedby",
    "georeferenceddate",
    "georeferenceprotocol",
    "georeferencesources",
    "georeferenceverificationstatus",
    "georeferenceremarks",
    "geologicalcontextid",
    "earliesteonorlowesteonothem",
    "latesteonorhighesteonothem",
    "earliesteraorlowesterathem",
    "latesteraorhighesterathem",
    "earliestperiodorlowestsystem",
    "latestperiodorhighestsystem",
    "earliestepochorlowestseries",
    "latestepochorhighestseries",
    "earliestageorloweststage",
    "latestageorhigheststage",
    "lowestbiostratigraphiczone",
    "highestbiostratigraphiczone",
    "lithostratigraphicterms",
    "group",
    "formation",
    "member",
    "bed",
    "identificationid",
    "identifiedby",
    "dateidentified",
    "identificationreferences",
    "identificationverificationstatus",
    "identificationremarks",
    "identificationqualifier",
    "typestatus",
    "taxonid",
    "scientificnameid",
    "acceptednameusageid",
    "parentnameusageid",
    "originalnameusageid",
    "nameaccordingtoid",
    "namepublishedinid",
    "taxonconceptid",
    "scientificname",
    "acceptednameusage",
    "parentnameusage",
    "originalnameusage",
    "nameaccordingto",
    "namepublishedin",
    "namepublishedinyear",
    "higherclassification",
    "kingdom",
    "phylum",
    "class",
    "order",
    "family",
    "genus",
    "subgenus",
    "specificepithet",
    "infraspecificepithet",
    "taxonrank",
    "verbatimtaxonrank",
    "scientificnameauthorship",
    "vernacularname",
    "nomenclaturalcode",
    "taxonomicstatus",
    "nomenclaturalstatus",
    "taxonremarks"
]

fieldList_176 = [
    "modified",
    "license",
    "rightsholder",
    "accessrights",
    "bibliographiccitation",
    "references",
    "institutionid",
    "collectionid",
    "datasetid",
    "institutioncode",
    "collectioncode",
    "datasetname",
    "ownerinstitutioncode",
    "basisofrecord",
    "informationwithheld",
    "datageneralizations",
    "dynamicproperties",
    "occurrenceid",
    "catalognumber",
    "recordnumber",
    "recordedby",
    "individualcount",
    "organismquantity",
    "organismquantitytype",
    "sex",
    "lifestage",
    "reproductivecondition",
    "behavior",
    "establishmentmeans",
    "occurrencestatus",
    "preparations",
    "disposition",
    "associatedmedia",
    "associatedreferences",
    "associatedsequences",
    "associatedtaxa",
    "othercatalognumbers",
    "occurrenceremarks",
    "organismid",
    "organismname",
    "organismscope",
    "associatedoccurrences",
    "associatedorganisms",
    "previousidentifications",
    "organismremarks",
    "materialsampleid",
    "eventid",
    "parenteventid",
    "fieldnumber",
    "eventdate",
    "eventtime",
    "startdayofyear",
    "enddayofyear",
    "year",
    "month",
    "day",
    "verbatimeventdate",
    "habitat",
    "samplingprotocol",
    "samplesizevalue",
    "samplesizeunit",
    "samplingeffort",
    "fieldnotes",
    "eventremarks",
    "locationid",
    "highergeographyid",
    "highergeography",
    "continent",
    "waterbody",
    "islandgroup",
    "island",
    "country",
    "countrycode",
    "stateprovince",
    "county",
    "municipality",
    "locality",
    "verbatimlocality",
    "minimumelevationinmeters",
    "maximumelevationinmeters",
    "verbatimelevation",
    "minimumdepthinmeters",
    "maximumdepthinmeters",
    "verbatimdepth",
    "minimumdistanceabovesurfaceinmeters",
    "maximumdistanceabovesurfaceinmeters",
    "locationaccordingto",
    "locationremarks",
    "decimallatitude",
    "decimallongitude",
    "geodeticdatum",
    "coordinateuncertaintyinmeters",
    "coordinateprecision",
    "pointradiusspatialfit",
    "verbatimcoordinates",
    "verbatimlatitude",
    "verbatimlongitude",
    "verbatimcoordinatesystem",
    "verbatimsrs",
    "footprintwkt",
    "footprintsrs",
    "footprintspatialfit",
    "georeferencedby",
    "georeferenceddate",
    "georeferenceprotocol",
    "georeferencesources",
    "georeferenceverificationstatus",
    "georeferenceremarks",
    "geologicalcontextid",
    "earliesteonorlowesteonothem",
    "latesteonorhighesteonothem",
    "earliesteraorlowesterathem",
    "latesteraorhighesterathem",
    "earliestperiodorlowestsystem",
    "latestperiodorhighestsystem",
    "earliestepochorlowestseries",
    "latestepochorhighestseries",
    "earliestageorloweststage",
    "latestageorhigheststage",
    "lowestbiostratigraphiczone",
    "highestbiostratigraphiczone",
    "lithostratigraphicterms",
    "group",
    "formation",
    "member",
    "bed",
    "identificationid",
    "identificationqualifier",
    "typestatus",
    "identifiedby",
    "dateidentified",
    "identificationreferences",
    "identificationverificationstatus",
    "identificationremarks",
    "taxonid",
    "scientificnameid",
    "acceptednameusageid",
    "parentnameusageid",
    "originalnameusageid",
    "nameaccordingtoid",
    "namepublishedinid",
    "taxonconceptid",
    "scientificname",
    "acceptednameusage",
    "parentnameusage",
    "originalnameusage",
    "nameaccordingto",
    "namepublishedin",
    "namepublishedinyear",
    "higherclassification",
    "kingdom",
    "phylum",
    "class",
    "order",
    "family",
    "genus",
    "subgenus",
    "specificepithet",
    "infraspecificepithet",
    "taxonrank",
    "verbatimtaxonrank",
    "scientificnameauthorship",
    "vernacularname",
    "nomenclaturalcode",
    "taxonomicstatus",
    "nomenclaturalstatus",
    "taxonremarks",
    "dataset_url",
    "gbifdatasetid",
    "gbifpublisherid",
    "dataset_contact_email",
    "dataset_contact",
    "migrator_version",
    "dataset_pubdate",
    "lastindexed",
    "iptlicense"
]
