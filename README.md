# mythadder

mythadder - automatically add video files on removable media to the mythvideo database upon connect
and remove them on disconnect...

Your distro should be set up to automount usb storage within 'mountWait' seconds after
connection into subdir=<disk label> within video SG directory. I.e. you have myth video SG in '/myth/video' dir and USB
disk labelled 'USB-Movies1' then your distro should mount USB disk into '/myth/video/USB-Movies1'.

Probably best idea is to:
1.use udev rule to start mount script at usb add/remove
2.mount sript should mount usb drive at proper location and within <label> dir
3.call this script to make usb videos visible in mythtv
Step3 can be by script like below called with parameter as kernel device representing usb drive (i.e. /dev/sde1)
  export `blkid --output export $1`
  export ACTION="add"
  export MYTHCONFDIR="/home/mythtv/.mythtv"
  /bin/su mythtv -p -c "/usr/bin/python3 /usr/local/bin/mythadder.py > /var/log/mythadder-add.log 2>&1"
  /bin/su mythtv -c "/usr/bin/mythutil --clearcache"

When usb is removed - You may call script with parameter as kernel device representing usb drive (i.e. /dev/sde1):
  export `blkid --output export $1`
  export ACTION="remove"
  export MYTHCONFDIR="/home/mythtv/.mythtv"
  /bin/su mythtv -p -c "/usr/bin/python3 /usr/local/bin/mythadder.py > /var/log/mythadder-remove.log 2>&1"
  /bin/su mythtv -c "/usr/bin/mythutil --clearcache"

If you want to automate all this - you can use i.e. my media-automout tool

