I needed VPN tunneling between my server (Ubuntu), AutoPi and laptop (Windows). I decided to use 4323 as UDP port for Wireguard.

# Server setup:

Server is running Ubuntu 18.04

## Check ip forwarding

Make sure that `sysctl net.ipv4.ip_forward` returns `net.ipv4.ip_forward = 1`. If not, add following to `/etc/sysctl.conf`:

```
net.ipv4.ip_forward = 1
```

and run `sudo sysctl -p /etc/sysctl.conf`.


## Install wireguard:

```
sudo apt update && sudo apt install -y wireguard wireguard-tools
```


## Create keys

```
(umask 0077; wg genkey | tee peer_A.key | wg pubkey > peer_A.pub) && echo 'Private:' && cat peer_A.key && echo 'Public:' && cat peer_A.pub
```


## Wireguard conf and setting up as a service

Create /etc/wireguard/wg0.conf
``` 
[Interface]
PrivateKey = <server_private_key:
Address = 10.0.0.1/24
ListenPort = 4323

[Peer]
PublicKey = <autopi_public_key>
AllowedIPs = 10.0.0.2/32

[Peer]
PublicKey = <laptop_public_key>
AllowedIPs = 10.0.0.3/32
```

Start wireguard at boot, and immediately:
```
systemctl enable wg-quick@wg0.service
systemctl start wg-quick@wg0.service
```

## Firewall

Wireguard UDP traffic needs port 4323 to be allowed through the server firewall. I use `ufw` as firewall interface so had to only do:
```
ufw allow 4323
```


# Autopi setup:

GEN3 AutoPi is running kernel:
```
uname -a
# Linux autopi-7a8b384f0f90 4.19.66-v7+ #1253 SMP Thu Aug 15 11:49:46 BST 2019 armv7l GNU/Linux
```

Followed instructions from: https://www.sigmdel.ca/michel/ha/wireguard/wireguard_02_en.html
```
echo "deb http://archive.raspbian.org/raspbian testing main" | sudo tee --append /etc/apt/sources.list.d/testing.list  
printf 'Package: *\nPin: release a=testing\nPin-Priority: 50\n' | sudo tee --append /etc/apt/preferences.d/limit-testing  
sudo apt update
sudo apt install wireguard -y
```

I lost connection to AutoPi during the installation and had to restart  the AutoPi by unplugging it. Probably unrelated to the installation.

## Keys

Generate same way as for the server

## Wireguard conf and setting up as a service

```
[Interface]
PrivateKey = <autopi_private_key>
Address = 10.0.0.2/32

[Peer]
PublicKey = <server_public_key>
AllowedIPs = 10.0.0.0/24
Endpoint = <server ip or fqdn>:4323
PersistentKeepalive = 60
```

Start wireguard at boot, and immediately:
```
systemctl enable wg-quick@wg0.service
systemctl start wg-quick@wg0.service
```

## Firewall

In https://my.autopi.io/#/advanced-settings added iptables rule:
```
-I INPUT 1 -i wg0 -j ACCEPT
```
this allows all traffic through the VPN tunnel.


# Laptop

Used Windows client for Wireguard and following conf:
```
[Interface]
PrivateKey = <laptopt_private_key>
Address = 10.0.0.3/32

[Peer]
PublicKey = <server_public_key>
AllowedIPs = 10.0.0.0/24
Endpoint = <server ip or fqdn>:4323
PersistentKeepalive = 60
```

# End

Now ssh/https/etc works from any of the machines, to any other machine.
