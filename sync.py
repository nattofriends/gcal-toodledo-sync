#!/usr/bin/env python
from datetime import datetime, date, time, timedelta

from icalendar import Calendar
import pytz
import requests

import config
from providers import ToodledoSync, WunderlistSync
from util import log

SYNC_PROVIDERS = [ToodledoSync, WunderlistSync]

log("shinku: starting")

calText = requests.get(config.calendar['source']).text
cal = Calendar.from_ical(calText)
items = {}
for component in cal.walk("VEVENT"):
    now = datetime.now(tz=pytz.utc)
    until = now + timedelta(config.lookahead)

    dt = component.decoded("dtstart")

    # As it so turns out, datetime is a subclass of date, meaning our time for
    # events had always been off because the time info had been blown away
    # every single time. Go figure.
    if type(dt) is date:
        dt = datetime.combine(dt, time(tzinfo=pytz.utc))

    if (now < dt < until):
        items[unicode(component.decoded("summary"), encoding='utf-8')] = dt

log("Google Calendar: {} items in next {} days".format(len(items), config.lookahead))

for provider in SYNC_PROVIDERS:
    syncer = provider()
    syncer.sync(items)
