# jingle-dmx

All sorts of lightning-producing fun

## Setup

on a fresh raspberry one needs to set the permissions for udmx device so that we can send signals through it

that's done by copying `98-udmx.rules` to `/etc/udev/rules.d/98-udmx.rules` and reloading udev rules / replugging udmx cable

```sh
cp 98-udmx.rules /etc/udev/rules.d/98-udmx.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```
