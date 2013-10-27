#!/opt/local/bin/python
import os, re, md5, urllib, urllib2, json
import time as time_module
import calendar as calendar_module
from datetime import datetime, date, time, timedelta
from icalendar import Calendar, UTC
import tzinfo_examples as tzinfo

from config import calSource, toodledoApiToken, toodledoId, toodledoFolderId, toodledoPass

# Google Calendar - Toodledo Sync 2.0
# Uses icalendar module, Toodledo API 2.0

# Configuration

lookahead        = 14
operationalTZ    = tzinfo.USTimeZone(-8, "Pacific",  "PST", "PDT")



class ToodledoSync:
    API_ENDPOINT = "http://api.toodledo.com/2/"
    APPID = "WarosuGcalSync"

    def __init__(self, _toodledo_api_token, _toodledo_id, _toodledo_pass, _toodledo_folder_id):
        self.api_token = _toodledo_api_token;
        self.id = _toodledo_id;
        self.password = _toodledo_pass;
        self.folderId = _toodledo_folder_id;
        
    def apply(self, supplementary_url, **params):
        return urllib2.urlopen(ToodledoSync.API_ENDPOINT + supplementary_url + "?" + urllib.urlencode(params)).read()
        
    def getTokenAndKey(self):
        try:
            lastModification = os.path.getmtime("cache");
        except:
            lastModification = 0;
        if (os.path.exists("cache") and time_module.time() - lastModification < 14400):
            ghettoLog("Found cached token and key")
            with open("cache") as cache:
                self.session_token, self.key = cache.read().split(":")
        else:
            ghettoLog("Getting new token and key")
            response = self.apply("account/token.php", 
                userid = self.id,
                appid = ToodledoSync.APPID,
                sig = md5.new(self.id + self.api_token).hexdigest())
            response = json.loads(response)
            if not "token" in response:
                raise Exception("Invalid token, got response: " + str(response))
            self.session_token = response["token"]
            self.key = md5.new(md5.new(self.password).hexdigest() + self.api_token + self.session_token).hexdigest()
            with open("cache", 'w') as cache:
                cache.write("{}:{}".format(self.session_token, self.key))
    
    def sync(self, gcalItems):
        ghettoLog("Starting sync")
        response = self.apply("tasks/get.php", 
            key = self.key, 
            comp = -1,
            fields = "duedate")
        response = json.loads(response)[1:]
        tdItems = {task["title"]: datetime.fromtimestamp(task["duedate"], UTC) for task in response}
        ghettoLog("Toodledo: {} items in list".format(len(tdItems)))
        
        notInToodledo = filter(lambda key: key not in tdItems, gcalItems.keys())
        ghettoLog("{} new items to add".format(len(notInToodledo)))
        
        payload = [
            {"title": item, 
             "duedate": calendar_module.timegm(gcalItems[item].timetuple()),
             "folder": self.folderId
            }
            for item in notInToodledo]
        if len(payload) > 0:
            map(lambda item: ghettoLog("\tAdding '{}'".format(item["title"])), payload)
            payload = json.dumps(payload)
            response = self.apply("tasks/add.php",
                key = self.key,
                tasks = payload);
            ghettoLog("Synchronization complete.")
        else:
            ghettoLog("Nothing synchronized.")


def ghettoLog(msg):
    print "{}  {}".format(time_module.asctime(), msg)

ghettoLog("Starting Google Calendar - Toodledo sync")

calText = urllib2.urlopen(calSource).read()
cal = Calendar.from_string(calText)
items = {}
for component in cal.walk("VEVENT"):
    now = datetime.now(tz = UTC)
    nextWeek = now + timedelta(lookahead)
    dt = component.decoded("dtstart")
    if isinstance(dt, datetime):
        dt = dt.replace(tzinfo = tzinfo.UTC())
    elif isinstance(dt, date):
        dt = datetime.combine(dt, time(tzinfo = tzinfo.UTC()))
    dt = dt.astimezone(operationalTZ)
    if (now < dt < nextWeek):
        items[component.decoded("summary")] = dt
ghettoLog("Google Calendar: {} items in next {} days".format(len(items), lookahead))

toodle = ToodledoSync(toodledoApiToken, toodledoId, toodledoPass, toodledoFolderId);
toodle.getTokenAndKey();
toodle.sync(items);