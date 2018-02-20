# mythadder
Script to support add/remove external drive with movies in MythTV video collection

Script automatically adds video files on removable media to the mythvideo database upon connect/mount
and remove them on disconnect.

Your distro should be set up to automount usb storage within 'mountWait' seconds after
connection into subdir=disk label within video SG directory. I.e. you have myth video SG 
in '/myth/video' dir and USB disk labelled 'USB-Movies1'. 
Your distro should mount USB disk into '/myth/video/USB-Movies1'.
Best way to achieve this will be use appropriate UDEV rule (see examplary rule in this repo)



