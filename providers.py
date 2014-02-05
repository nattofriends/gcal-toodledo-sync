"""Sync providers.
"""

import datetime
import json
import md5
import os
from calendar import timegm
from datetime import datetime
from time import time

import pytz
import requests
import wunderpy

import config
from util import log


class SyncBase(object):
    @classmethod
    def log(cls, msg):
        log("{}: {}".format(cls.__name__, msg))

    def sync(self, gcal_items):
        raise NotImplementedError


class ToodledoSync(SyncBase):
    API_ENDPOINT = "http://api.toodledo.com/2/"
    APPID = "WarosuGcalSync"

    def __init__ (self):
        self.api_token = config.toodledo['api_token']
        self.id = config.toodledo['id']
        self.password = config.toodledo['password']
        self.folder_id = config.toodledo['folder_id']

        self._get_credentials()

    def _call(self, resource, **params):
        return requests.get(ToodledoSync.API_ENDPOINT + resource, params=params).text

    def _get_credentials(self):
        try:
            last_modification = os.path.getmtime("cache");
        except:
            last_modification = 0;
        if (os.path.exists("cache") and time() - last_modification < 14400):
            self.log("Found cached token and key")
            with open("cache") as cache:
                self.session_token, self.key = cache.read().split(":")
        else:
            self.log("Getting new token and key")
            response = self._call("account/token.php",
                userid=self.id,
                appid=ToodledoSync.APPID,
                sig=md5.new(self.id + self.api_token).hexdigest()
            )
            response = json.loads(response)
            if not "token" in response:
                raise Exception("Invalid token, got response: " + str(response))
            self.session_token = response["token"]
            self.key = md5.new(md5.new(self.password).hexdigest() + self.api_token + self.session_token).hexdigest()
            with open("cache", 'w') as cache:
                cache.write("{}:{}".format(self.session_token, self.key))

    def sync(self, gcal_items):
        self.log("Starting sync")
        response = self._call("tasks/get.php",
            key=self.key,
            comp=-1,
            fields="duedate"
        )
        response = json.loads(response)[1:]
        td_items = {task["title"]: datetime.fromtimestamp(task["duedate"], pytz.utc) for task in response}
        self.log("{} items in list".format(len(td_items)))

        not_in_td = filter(lambda key: key not in td_items, gcal_items.keys())
        self.log("{} new items to add".format(len(not_in_td)))

        payload = [
            {
                "title": item,
                "duedate": timegm(gcal_items[item].timetuple()),
                "folder": self.folder_id
            }
            for item in not_in_td]

        if any(payload):
            map(lambda item: self.log("\tAdding '{}'".format(item["title"])), payload)
            payload = json.dumps(payload)
            response = self._call("tasks/add.php",
                key=self.key,
                tasks=payload
            )

            self.log("Synchronization complete.")
        else:
            self.log("Nothing synchronized.")


class WunderlistSync(SyncBase):
    def __init__(self):
        self.w = wunderpy.Wunderlist()
        self.w.login(config.wunderlist['username'], config.wunderlist['password'])
        self.w.update_lists()

    def sync(self, gcal_items):
        self.log("Starting sync")
        list_items = set(self.w.lists[config.wunderlist['list']]['tasks'].keys())
        self.log("{} items in list".format(len(list_items)))
        missing = set(gcal_items.keys()) - list_items
        self.log("{} items to add".format(len(missing)))

        if any(missing):
            for task in missing:
                local_time = gcal_items[task].astimezone(pytz.timezone(config.working_timezone))
                self.log("\t Adding '{}' ({})".format(task, local_time.isoformat()))
                self.w.add_task(task,
                    list=config.wunderlist['list'],
                    due_date=local_time.isoformat(),
                    starred=False
                )
            self.log("Synchronization complete.")
        else:
            self.log("Nothing synchronized.")
