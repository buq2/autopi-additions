#/bin/python3
import shelve
import datetime
import bisect
import functools
import logging
from collections import defaultdict

DB_FILENAME='/home/pi/network_stats.slv'
RECEIVED='received'
TRANSMITTED='transmitted'
TIMESERIES_NAME='timeseries'
MAX_TIMESERIESPOINT_LIFE = datetime.timedelta(days=2)
MIN_DIFFERENCE_BETWEEN_TIMESERIES_POINTS = datetime.timedelta(seconds=50)

log = logging.getLogger(__name__)

def __get_network_interface_state():
    out = {}
    for line in open('/proc/net/dev', 'r'):
        try:
            interface, rest = line.split(':')
            interface = interface.strip()
            data = rest.split()
            if len(data) >= 16:
                out[interface] = {RECEIVED:int(data[0]), TRANSMITTED:int(data[8])}
        except:
            # Ignore header and incorrectly formatted data
            pass

    return out

@functools.total_ordering
class TimeseriesPoint:
    @staticmethod
    def invalid():
        return TimeseriesPoint(None, None)

    def __init__(self, datetime, data):
        self.datetime = datetime
        self.data = data
    
    def __lt__(self, other):
        if isinstance(other, TimeseriesPoint):
            return self.datetime < other.datetime
        elif isinstance(other, datetime.datetime):
            return self.datetime < other


class Timeseries:
    def __init__(self):
        self.__data = []
        self.__sorted = False

    def add(self, point, time=None):
        if time is None:
            time = datetime.datetime.now()

        if len(self) > 0 and time - self.get_latest().datetime < MIN_DIFFERENCE_BETWEEN_TIMESERIES_POINTS:
            log.info('Previous timepoint too close, ignoring new point')
            return

        if len(self.__data) == 0 or self.__data[-1] < time:
            self.__sorted = True
        else:
            self.__sorted = False
        self.__data.append(TimeseriesPoint(time, point))

    def get_latest(self):
        if not self.__sorted:
            self.sort()

        if len(self) == 0:
            return TimeseriesPoint.invalid()

        return self.__data[-1]

    def get_closest_to_time(self, time):
        return self.__get_closest_to_time(time)[0]

    def __get_closest_to_time(self, time):
        if not self.__sorted:
            self.sort()
        if len(self.__data) == 0:
            return None, None

        idx = bisect.bisect_left(self.__data, time)
        if idx == 0:
            return self.__data[idx], 0
        elif idx == len(self.__data):
            return self.__data[-1], len(self.__data)-1
        before = self.__data[idx-1]
        after = self.__data[idx]
        if after.datetime - time < time - before.datetime:
            return after, idx
        else:
            return before, idx-1

    def prune(self):
        limit_datetime = datetime.datetime.now() - MAX_TIMESERIESPOINT_LIFE
        (point, idx) = self.__get_closest_to_time(limit_datetime)
        if point.datetime < limit_datetime:
            del self.__data[:idx+1]
        else:
            del self.__data[:idx]

    def __str__(self):
        return 'len: {}'.format(len(self.__data))

    def __len__(self):
        return len(self.__data)

    def sort(self):
        self.__data.sort(key = lambda x : x[0])
        self.__sorted = True

def __calculate_network_stats(ts, delta):
    out = {}
    latest = ts.get_latest()
    prev = ts.get_closest_to_time(latest.datetime - delta)
    real_delta = latest.datetime - prev.datetime

    data_latest = latest.data
    data_prev = prev.data
    for key, val_latest in data_latest.items():
        if key not in data_prev:
            continue
        out[key] = val_latest - data_prev[key]
    return out

def __process_data(network_timeseries, interface = None, delta = datetime.timedelta(days=1)):
    out = {}
    
    if interface is not None:
        out[interface] = __calculate_network_stats(network_timeseries[interface], delta)
    else:
        for interface, ts in network_timeseries.items():
            out[interface] = __calculate_network_stats(ts, delta)
            
    return out

def __update_network_timeseries(timeseries):
    state = __get_network_interface_state()
    for key,val in state.items():
        if key not in timeseries:
            ts = Timeseries()
            timeseries[key] = ts
        else:
            ts = timeseries[key]
        ts.add(val)

    for key,ts in timeseries.items():
        ts.prune()

        # Remove timeseries which have no data
        if len(ts) == 0:
            del timeseries[key]

def get_network_usage():
    """
    Return network statistics for last 24h
    Output format
    {<interface_name>:{'received':bytes, 'transmitted':bytes}}
    """
    # Get history
    db = shelve.open(DB_FILENAME)

    if TIMESERIES_NAME in db:
        timeseries = db[TIMESERIES_NAME]
    else:
        log.info('Initializing timeseries')
        timeseries = {}

    __update_network_timeseries(timeseries)

    # Write back to storage
    db[TIMESERIES_NAME] = timeseries

    return __process_data(timeseries)


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"]("my_network")

if __name__ == '__main__':
    get_network_usage()
