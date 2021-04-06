#!/bin/python3
import pickle
import datetime
import bisect
import functools
import logging
import copy
import os

DB_FILENAME_DEV = 'network_stats.slv'
DB_FILENAME = '/home/pi/' + DB_FILENAME_DEV
RECEIVED = 'received'
TRANSMITTED = 'transmitted'
TIMESERIES_NAME = 'timeseries'
MAX_TIMESERIESPOINT_LIFE = datetime.timedelta(days=2)
MAX_NUMBER_OF_TIMESERIES_POINTS = 60*24*3
MIN_DIFFERENCE_BETWEEN_TIMESERIES_POINTS = datetime.timedelta(seconds=50)
FORCE_MONOTONIC_TIMESERIES = True

log = logging.getLogger(__name__)

# Helper function to ease testing
def get_current_time(usage_reason):
    return datetime.datetime.now()

def __get_network_interface_state():
    out = {}
    for line in open('/proc/net/dev', 'r'):
        try:
            interface, rest = line.split(':')
            interface = interface.strip()
            data = rest.split()
            if len(data) >= 16:
                out[interface] = {RECEIVED: int(
                    data[0]), TRANSMITTED: int(data[8])}
        except BaseException:
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
        self.__data = data
        self.__monotonic_fix = None

    def ensure_monotonicness(self, prev):
        # Make sure that the data is monotonically increasing

        prev_data = prev.get_data(with_monotonic_fix=False)
        data = self.get_data(with_monotonic_fix=False)
        for key, val in data.items():
            if key in prev_data:
                prev_val = prev_data[key]
                if prev_val > val:
                    # Data would not monotonic, try to fix
                    # This works if modem was reset and all values were zeroed
                    self.__fix_monotonic(prev)
                    return

        # This point is still monotonic, we can use previous monotonicness data
        self.__set_monotonic(prev)

    def __fix_monotonic(self, other):
        self.__monotonic_fix = other.get_data(with_monotonic_fix=True)

    def __set_monotonic(self, other):
        self.__monotonic_fix = other.__monotonic_fix

    def get_data(self, with_monotonic_fix=True):
        out = copy.copy(self.__data)

        if not with_monotonic_fix or self.__monotonic_fix is None:
            return out

        if isinstance(out, dict):
            for key, val in out.items():
                out[key] += self.__monotonic_fix.get(key, 0)
        else:
            out += self.__monotonic_fix

        return out

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
            time = get_current_time('add')

        if len(self) > 0 and time - \
                self.get_latest().datetime < \
                MIN_DIFFERENCE_BETWEEN_TIMESERIES_POINTS:
            log.info('Previous timepoint too close, ignoring new point')
            return

        ts_point = TimeseriesPoint(time, point)

        if FORCE_MONOTONIC_TIMESERIES:
            self.__check_monotonicness(ts_point)

        self.__data.append(ts_point)

    def __check_monotonicness(self, point):
        # Check for monotonicness
        # This is needed as autopi modem resets transferred bytes each
        # time autopi sleeps so if we see that previous values are
        # lower than current ones, we need to fix them

        if len(self) == 0:
            # No data, can not yet fix issues (/there is no issues)
            return

        prev = self.get_latest()
        point.ensure_monotonicness(prev)

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
            return self.__data[-1], len(self.__data) - 1
        before = self.__data[idx - 1]
        after = self.__data[idx]
        if after.datetime - time < time - before.datetime:
            return after, idx
        else:
            return before, idx - 1

    def prune(self):
        limit_datetime = get_current_time('prune') - MAX_TIMESERIESPOINT_LIFE
        (point, idx) = self.__get_closest_to_time(limit_datetime)
        if point.datetime < limit_datetime:
            del self.__data[:idx + 1]
        else:
            del self.__data[:idx]

        # Delete old ones if too many points
        if len(self.__data) > MAX_NUMBER_OF_TIMESERIES_POINTS:
            print('Too many timeseries points, deleting oldest ones')
            del self.__data[-MAX_NUMBER_OF_TIMESERIES_POINTS:]

    def __str__(self):
        return 'len: {}'.format(len(self.__data))

    def __len__(self):
        return len(self.__data)

    def sort(self):
        if len(self) > 0:
            self.__data.sort(key=lambda x: x.datetime)
        self.__sorted = True


def __calculate_network_stats(ts, delta, weighted=False):
    out = {}
    latest = ts.get_latest()
    prev = ts.get_closest_to_time(latest.datetime - delta)
    real_delta = latest.datetime - prev.datetime

    data_latest = latest.get_data()
    data_prev = prev.get_data()

    # If requested interval was 1day, but for what ever reason we have only
    # 12 hours of data, to get average consuptions with current rate,
    # we should multiply the consumption in 12 hours by 2.
    if weighted and real_delta.total_seconds() != 0:
        multiplier = delta.total_seconds() / real_delta.total_seconds()
    else:
        # Probably in a test which data is created almost instantly
        multiplier = 1

    for key, val_latest in data_latest.items():
        if key not in data_prev:
            continue
        out[key] = (val_latest - data_prev[key]) * multiplier
    return out


def __process_data(
    network_timeseries,
    interface=None,
    delta=datetime.timedelta(
        days=1)):
    out = {}

    if interface is not None:
        out[interface] = __calculate_network_stats(
            network_timeseries[interface], delta)
    else:
        for interface, ts in network_timeseries.items():
            out[interface] = __calculate_network_stats(ts, delta)

    return out


def __update_network_timeseries(timeseries):
    state = __get_network_interface_state()
    for key, val in state.items():
        if key not in timeseries:
            ts = Timeseries()
            timeseries[key] = ts
        else:
            ts = timeseries[key]
        ts.add(val)

    for key, ts in timeseries.items():
        ts.prune()

        # Remove timeseries which have no data
        if len(ts) == 0:
            del timeseries[key]

def get_db():
    db = {}

    try:
        if os.path.exists(DB_FILENAME):
            with open(DB_FILENAME,'rb') as f:
                db = pickle.load(f)
        elif os.path.exists(DB_FILENAME_DEV):
            with open(DB_FILENAME_DEV,'rb') as f:
                db = pickle.load(f)
    except:
        print('Failed to load db, starting new')

    return db

def write_db(db):
    fname = None
    if os.path.exists(DB_FILENAME):
        fname = DB_FILENAME
    elif os.path.exists(DB_FILENAME_DEV):
        fname = DB_FILENAME_DEV

    if fname is not None:
        with open(fname, 'wb') as f:
            pickle.dump(db, f)
    else:
        try:
            with open(DB_FILENAME, 'wb') as f:
                pickle.dump(db, f)
        except:
            with open(DB_FILENAME_DEV, 'wb') as f:
                pickle.dump(db, f)


def clear():
    """
    Clear database of network usage
    """

    db = get_db()
    db.clear()
    write_db(db)


def get_network_usage():
    """
    Return network statistics for last 24h
    Output format
    {<interface_name>:{'received':bytes, 'transmitted':bytes}}
    """
    # Get history
    db = get_db()

    if TIMESERIES_NAME in db:
        timeseries = db[TIMESERIES_NAME]
    else:
        log.info('Initializing timeseries')
        timeseries = {}

    __update_network_timeseries(timeseries)

    # Write back to storage
    db[TIMESERIES_NAME] = timeseries
    write_db(db)

    return __process_data(timeseries)


def help():
    """
    Shows this help information.
    """

    return __salt__["sys.doc"]("my_network")  # noqa: F821


if __name__ == '__main__':
    print(get_network_usage())
