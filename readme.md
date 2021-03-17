![Build](https://github.com/buq2/autopi-additions/actions/workflows/main.yml/badge.svg)

# Usage

Copy content of `my_xxx.py`scripts to https://my.autopi.io/#/custom-code .

You can call the functions from the code using the AutoPi terminal (top right corner in web ui).
For example to get network statistics `my_network.get_network_usage`.

To automatically collect the stats, create a new job in https://my.autopi.io/#/jobs . Set the cron to run every Nth minute and set the function for example to `my_network.get_network_usage`. Returner should be set to `cloud`.

After these setups and waiting some data to be collected, you should be able to create a new widget in the AutoPi dashboard which uses `my_network.get_network_usage.wwan0.received`. Use `average` as the aggregation.

# Docker build / testing

```
docker build -t autopi_additions .
docker run --rm autopi_additions # runs pytest
```

# Wireguard

[I wrote a short description how to set up Wireguard VPN for AutoPi use.](readme_wireguard.md)
