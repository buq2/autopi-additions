import my_network
import pytest
import datetime
import numpy as np

use_real_time = True
fake_time = datetime.datetime.now()
def faked_current_time(usage_reason):
    global use_real_time
    global fake_time

    if use_real_time:
        return datetime.datetime.now()
    else:
        return fake_time


class FakedNet:
    def __init__(self):
        self.received = 0
        self.transmitted = 0

        self.total_received = 0
        self.total_transmitted = 0

        self.name = 'net'

    def progress_time(self, timedelta=datetime.timedelta(seconds=60*60)):
        global fake_time
        fake_time = fake_time + timedelta

    def get_fake_network_interface_state(self):
        out = {}
        out[self.name] = {my_network.RECEIVED: self.received,
                          my_network.TRANSMITTED: self.transmitted}

        return out

    def increase_net_usage(self):
        rec = np.random.randint(1, 10)
        trans = np.random.randint(1, 10)
        self.received += rec
        self.transmitted += trans

        self.total_received += rec
        self.total_transmitted += trans

    def reset(self):
        # Set non totals to smaller than previously
        self.received = np.min([np.random.randint(0, 10), self.received - 1])
        self.transmitted = np.min(
            [np.random.randint(0, 10), self.transmitted - 1])

        self.total_received += self.received
        self.total_transmitted += self.transmitted


@pytest.fixture
def net():
    my_network.MIN_DIFFERENCE_BETWEEN_TIMESERIES_POINTS = datetime.timedelta(
        seconds=0)
    my_network.get_current_time = faked_current_time
    my_network.clear()
    net = FakedNet()
    my_network.__get_network_interface_state = \
        lambda: net.get_fake_network_interface_state()

    return net


def check(net, state):
    assert state[net.name][my_network.RECEIVED] == net.total_received
    assert state[net.name][my_network.TRANSMITTED] == net.total_transmitted


def test_init(net):
    assert net.received == 0
    assert net.transmitted == 0


def test_without_reset(net):
    for i in range(5):
        state = my_network.get_network_usage()
        check(net, state)
        net.increase_net_usage()


def test_with_reset(net):
    for i in range(5):
        state = my_network.get_network_usage()
        check(net, state)
        net.increase_net_usage()
    state = my_network.get_network_usage()
    check(net, state)
    net.reset()
    state = my_network.get_network_usage()
    check(net, state)


def test_with_reset2(net):
    for i in range(5):
        state = my_network.get_network_usage()
        check(net, state)
        net.increase_net_usage()
    state = my_network.get_network_usage()
    check(net, state)
    net.reset()
    state = my_network.get_network_usage()
    check(net, state)
    for i in range(5):
        state = my_network.get_network_usage()
        check(net, state)
        net.increase_net_usage()


def test_with_reset3(net):
    for i in range(5):
        state = my_network.get_network_usage()
        check(net, state)
        net.increase_net_usage()
    state = my_network.get_network_usage()
    check(net, state)
    net.reset()
    state = my_network.get_network_usage()
    check(net, state)
    for i in range(5):
        state = my_network.get_network_usage()
        check(net, state)
        net.increase_net_usage()
    state = my_network.get_network_usage()
    check(net, state)
    net.reset()
    state = my_network.get_network_usage()
    check(net, state)
    for i in range(5):
        state = my_network.get_network_usage()
        check(net, state)
        net.increase_net_usage()

def test_removing_old_data(net):
    global use_real_time
    use_real_time = False
    for i in range(5):
        state = my_network.get_network_usage()
        check(net, state)
        net.increase_net_usage()
        net.progress_time()
    state = my_network.get_network_usage()
    check(net, state)
    net.progress_time(my_network.MAX_TIMESERIESPOINT_LIFE)
    state = my_network.get_network_usage()

    # Old data has been deleted
    assert state[net.name][my_network.RECEIVED] == 0
    assert state[net.name][my_network.TRANSMITTED] == 0

    use_real_time = True


if __name__ == '__main__':
    pytest.main()
