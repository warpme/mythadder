#!/usr/bin/python3

# mythadder - automatically add video files on removable media to the mythvideo database upon connect
# and remove them on disconnect.  
#
# Your distro should be set up to automount usb storage within 'mountWait' seconds after
# connection into subdir=<disk label> within video SG directory. I.e. you have myth video SG in '/myth/video' dir and USB
# disk labelled 'USB-Movies1' then your distro should mount USB disk into '/myth/video/USB-Movies1'.
#
# Probably best idea is to:
# 1.use udev rule to start mount script at usb add/remove
# 2.mount sript should mount usb drive at proper location and within <label> dir
# 3.call this script to make usb videos visible in mythtv
# Step3 can be by script like below called with parameter as kernel device representing usb drive (i.e. /dev/sde1)
#   export `blkid --output export $1`
#   export ACTION="add"
#   export MYTHCONFDIR="/home/mythtv/.mythtv"
#   /bin/su mythtv -p -c "/usr/bin/python3 /usr/local/bin/mythadder.py > /var/log/mythadder-add.log 2>&1"
#   /bin/su mythtv -c "/usr/bin/mythutil --clearcache"
#
# When usb is removed - You may call script with parameter as kernel device representing usb drive (i.e. /dev/sde1):
#   export `blkid --output export $1`
#   export ACTION="remove"
#   export MYTHCONFDIR="/home/mythtv/.mythtv"
#   /bin/su mythtv -p -c "/usr/bin/python3 /usr/local/bin/mythadder.py > /var/log/mythadder-remove.log 2>&1"
#   /bin/su mythtv -c "/usr/bin/mythutil --clearcache"
#
# If you want to automate all this - you can use i.e. my media-automout tool



#
# configuration section
#

# seconds to wait for mount after udev event
mountWait  = 5

# Don't change anything below this unless you are a real python programmer and I've done something really dumb.
# This is my python 'hello world', so be gentle.

version = "1.2.0"
MASCHEMA = "1030"

#
# code
#

import os
import sys
import subprocess
import struct
import re
import time
from MythTV import MythDB, MythLog, Video

def LOG(msg):
    logger = MythLog(module='mythadder.py')
    logger(MythLog.GENERAL, MythLog.INFO, msg)

def prepTable(db):
    if db.settings.NULL['mythadder.DBSchemaVer'] is None:
        # create new table
        LOG("-->No REMOVABLEVIDEO table detected. Creating it...\n")
        c = db.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS `removablevideos` (
		partitionuuid varchar(100) NOT NULL,
		partitionlabel varchar(50) NOT NULL,
		fileinode int(11) NOT NULL,
		intid int(10) unsigned NOT NULL,
		title varchar(128) NOT NULL,
		subtitle text NOT NULL,
		tagline varchar(255) NULL,
		director varchar(128) NOT NULL,
		studio varchar(128) NOT NULL,
		plot text,
		rating varchar(128) NOT NULL,
		inetref varchar(255) NOT NULL,
		collectionref int(10) unsigned NOT NULL,
		homepage text,
		year int(10) unsigned NOT NULL,
		releasedate date,
		userrating float NOT NULL,
		length int(10) unsigned NOT NULL,
		playcount int(10) unsigned NOT NULL,
		season smallint(5) unsigned NOT NULL default '0',
		episode smallint(5) unsigned NOT NULL default '0',
		showlevel int(10) unsigned NOT NULL,
		filename text NOT NULL,
		hash varchar(128) NOT NULL,
		coverfile text NOT NULL,
		childid int(11) NOT NULL default '-1',
		browse tinyint(1) NOT NULL default '1',
		watched tinyint(1) NOT NULL default '0',
		processed tinyint(1) NOT NULL default '1',
		playcommand varchar(255) default NULL,
		category int(10) unsigned NOT NULL default '0',
		trailer text,
		host text NOT NULL,
		screenshot text,
		banner text,
		fanart text,
		insertdate timestamp NULL default CURRENT_TIMESTAMP,
		contenttype set('MOVIE','TELEVISION','ADULT','MUSICVIDEO','HOMEVIDEO') NOT NULL DEFAULT '',
                PRIMARY KEY  (`partitionuuid`,`fileinode`),
		KEY `director` (`director`),
		KEY `title` (`title`),
		KEY `partitionuuid` (`partitionuuid`)
            ) ENGINE=MyISAM DEFAULT CHARSET=utf8;""")
        c.close()
        db.settings.NULL['mythadder.DBSchemaVer'] = MASCHEMA

    elif db.settings.NULL['mythadder.DBSchemaVer'] == MASCHEMA:
        LOG("-->REMOVABLEVIDEO table schema " + db.settings.NULL['mythadder.DBSchemaVer'] + " is valid\n")
    else:
        LOG("-->Wrong or undefined REMOVABLEVIDEO table schema. Exiting...\n")
        sys.exit(1)


def hashFile(filename):
    try:
        longlongformat = 'q'  # long long
        bytesize = struct.calcsize(longlongformat)
        f = open(filename, "rb")
        filesize = os.path.getsize(filename)
        hash = filesize
        if filesize < 65536 * 2:    # Video file is too small
               return u''
        for x in range(int(65536/bytesize)):
                buffer = f.read(bytesize)
                (l_value,)= struct.unpack(longlongformat, buffer)
                hash += l_value
                hash = hash & 0xFFFFFFFFFFFFFFFF #to remain as 64bit number
        f.seek(max(0,filesize-65536),0)
        for x in range(int(65536/bytesize)):
                buffer = f.read(bytesize)
                (l_value,)= struct.unpack(longlongformat, buffer)
                hash += l_value
                hash = hash & 0xFFFFFFFFFFFFFFFF
        f.close()
        returnedhash =  "%016x" % hash
        return returnedhash

    except(IOError):    # Accessing to this video file caused and error
        return u''

inodes = []

device = os.environ.get('DEVNAME',False)
action = os.environ.get('ACTION',False)
uuid   = os.environ.get('UUID',False)
label  = os.environ.get('LABEL',False)

if device:
    LOG("mythadder.py v%s by Wagnerrp, Piotr Oniszczuk\n\n -Device      : %s\n -Action      : %s\n -DeviceLabel : %s\n -DeviceUUID  : %s\n" % (version, device, action, label, uuid))

    #
    # the drive is connected
    #
    if action == 'add':
        # connect to db
        try:
            LOG("-->Connecting to MythTV DB\n")
            db = MythDB()
            prepTable(db)
        except (Exception) as e:
            LOG(e.args[0])
            LOG("-->Connectinon to MythTV DB failed!\n")
            sys.exit(1)

        cursor = db.cursor()

        regex = re.compile(device)
        time.sleep(mountWait) # wait a few seconds until the drive is mounted
        mount_output = subprocess.getoutput('mount -v')
        for line in mount_output.split('\n'):
            if regex.match(line):
                mount_point = line.split(' type ')[0].split(' on ')[1]
                LOG("Disk mounted at " + mount_point)

        cursor.execute("""SELECT extension FROM videotypes WHERE f_ignore=0""")
        extensions = list(zip(*cursor.fetchall()))[0]

        cursor.execute("""SELECT dirname FROM storagegroup  WHERE groupname='Videos'""")
        row = list(zip(*cursor.fetchall()))[0]

        videoSGpath = str(row[0])

        for directory in os.walk(mount_point):
            for file in directory[2]:
                if file.rsplit('.',1)[1] in extensions:
                    thisFile = directory[0] + '/' + file
                    thisHash = hashFile(thisFile)
                    thisTitle = os.path.splitext(file)[0]
                    thisInode = str(os.stat(thisFile).st_ino)
                    thisMythSGPath = re.sub(videoSGpath,'',thisFile)
                    thisHost = subprocess.check_output(['hostname'])
                    thisHost = thisHost.rstrip()

                    inodes.append(thisInode)

                    # insert each file that matches our extensions or update if it's already in the table
                    sql = """
                        INSERT INTO
                                removablevideos
			SET partitionuuid = %s
				,partitionlabel = %s
				,fileinode = %s
				,intid = 0
				,title = %s
				,subtitle = ''
				,studio = ''
				,director = ''
				,rating = ''
				,homepage = ''
				,inetref = ''
				,collectionref = '0'
				,playcount = '0'
				,year = 0
				,releasedate = '1900-01-01'
				,userrating = 0.0
				,length = 0
				,showlevel = 1
				,filename = %s
				,hash = %s
				,coverfile = ''
				,host = %s
			ON DUPLICATE KEY UPDATE
				partitionlabel = %s
				,filename = %s;"""
                    try:
                        LOG("Inserting into REMOVABLEVIDEOS table record with:\n -Disk UUID   : " + uuid +'\n -Disk Label  : '+label+'\n -File Inode  : '+thisInode+'\n -Movie Title : '+thisTitle+'\n -File Path   : '+thisFile+'\n -File(in SG) : '+thisMythSGPath+'\n -VideoSG path: '+videoSGpath+'\n -File Hash   : '+thisHash+'\n')
                        cursor.execute(sql, (uuid, label,  thisInode,  thisTitle,  thisMythSGPath,  thisHash,  thisHost,  label,  thisMythSGPath))
                    except (Exception) as e:
                        LOG(e.args[0])

        inodeList = ','.join(inodes)

        # delete any rows for files that were deleted from the disk
        # there seems to be a bug in the mysql package that fails to handle the 
        # tuples for this query because of the inode list so we're letting python do the substitution here
        sql = """
            DELETE FROM
                removablevideos
            WHERE
                partitionuuid = '%s' AND
                fileinode NOT IN (%s) ;""" % (uuid,  inodeList)

        try:
            LOG("-->Removing from REMOVABLEVIDEOS all records for files deleted on " + label + " disk\n")
            cursor.execute(sql)
        except (MySQLdb.Error) as e:
            LOG(e.args[0])

        # insert anything from our table that already has an id from mythtv
        sql = """
            INSERT INTO videometadata (
		intid
		,title
		,subtitle
		,tagline
		,director
		,studio
		,plot
		,rating
		,inetref
		,collectionref
		,homepage
		,year
		,releasedate
		,userrating
		,length
		,playcount
		,season
		,episode
		,showlevel
		,filename
		,hash
		,coverfile
		,childid
		,browse
		,watched
		,processed
		,playcommand
		,category
		,trailer
		,host
		,screenshot
		,banner
		,fanart
		,insertdate
		,contenttype)
            SELECT
		intid
		,title
		,subtitle
		,tagline
		,director
		,studio
		,plot
		,rating
		,inetref
		,collectionref
		,homepage
		,year
		,releasedate
		,userrating
		,length
		,playcount
		,season
		,episode
		,showlevel
		,filename
		,hash
		,coverfile
		,childid
		,browse
		,watched
		,processed
		,playcommand
		,category
		,trailer
		,host
		,screenshot
		,banner
		,fanart
		,insertdate
		,contenttype
            FROM
                removablevideos
            WHERE
                partitionuuid = %s AND
                intid != 0 ;"""
        try:
            LOG("-->Insert all records from REMOVABLEVIDEO table into VIDEOMETADATA table\n")
            cursor.execute(sql, [uuid])
        except (Exception) as e:
            LOG(e.args[0])

        # get all our rows that have never been in mythtv before so we can insert them one at a time and capture the resulting mythtv id
        sql = """
            SELECT
		title
		,subtitle
		,tagline
		,director
		,studio
		,plot
		,rating
		,inetref
		,collectionref
		,homepage
		,year
		,releasedate
		,userrating
		,length
		,playcount
		,season
		,episode
		,showlevel
		,filename
		,hash
		,coverfile
		,childid
		,browse
		,watched
		,processed
		,playcommand
		,category
		,trailer
		,host
		,screenshot
		,banner
		,fanart
		,insertdate
		,contenttype
		,fileinode
            FROM
                removablevideos 
            WHERE
                partitionuuid = %s AND
                intid = 0 ;"""

        try:
            LOG("-->Getting all movie records from REMOVABLEVIDEO table not yet seen by myth\n")
            cursor.execute(sql,  [uuid])
            data = cursor.fetchall()
        except (Exception) as e:
            LOG(e.args[0])

        # insert one row from new videos and capture the id it gets assigned
        sql = """
            INSERT INTO videometadata (
		title
		,subtitle
		,tagline
		,director
		,studio
		,plot
		,rating
		,inetref
		,collectionref
		,homepage
		,year
		,releasedate
		,userrating
		,length
		,playcount
		,season
		,episode
		,showlevel
		,filename
		,hash
		,coverfile
		,childid
		,browse
		,watched
		,processed
		,playcommand
		,category
		,trailer
		,host
		,screenshot
		,banner
		,fanart
		,insertdate
		,contenttype)
		VALUES ( %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);

            SELECT LAST_INSERT_ID() AS intid;""" 
        for row in data:
            try:
                LOG('-->Adding movie '+ row[0]+' into VIDEOMETADATA table\n')
                cursor.execute(sql, [row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10], row[11], row[12], row[13], row[14], row[15], row[16], row[17], row[18], row[19], row[20], row[21], row[22], row[23], row[24], row[25], row[26], row[27], row[28], row[29], row[30], row[31], row[32], row[33]])
            except (Exception) as e:
                LOG(e.args[0])

            cursor.nextset()
            intid = cursor.fetchone()[0]

            # update our table with the intid from mythtv so we can remove the rows when the drive is disconnected
            sql2 = """
                UPDATE removablevideos
                SET intid = %s
                WHERE partitionuuid = %s AND fileinode = %s
            """
            try:
                LOG("Updating intid=" + str(intid) + " for this movie\n")
                cursor.execute(sql2, [intid,  uuid, row[34]])
            except (Exception) as e:
                LOG(e.args[0])

        LOG("-->All done with success!\n Exiting ...\n")

    #
    # the drive is being removed.
    #
    if action == 'remove':
        # connect to db
        try:
            LOG("-->Connecting to MythTV DB\n")
            db = MythDB()
            prepTable(db)
        except (Exception) as e:
            LOG(e.args[0])

        cursor = db.cursor()

        # update everything in our table to catch metadata changes done inside mythtv
        sql = """
            UPDATE
                removablevideos rv,  videometadata vm
            SET
		rv.title = vm.title
		,rv.subtitle = vm.subtitle
		,rv.tagline = vm.tagline
		,rv.director = vm.director
		,rv.studio = vm.studio
		,rv.plot = vm.plot
		,rv.rating = vm.rating
		,rv.inetref = vm.inetref
		,rv.collectionref = vm.collectionref
		,rv.homepage = vm.homepage
		,rv.year = vm.year
		,rv.releasedate = vm.releasedate
		,rv.userrating = vm.userrating
		,rv.length = vm.length
		,rv.playcount = vm.playcount
		,rv.season = vm.season
		,rv.episode = vm.episode
		,rv.showlevel = vm.showlevel
		,rv.filename = vm.filename
		,rv.hash = vm.hash
		,rv.coverfile = vm.coverfile
		,rv.childid = vm.childid
		,rv.browse = vm.browse
		,rv.watched = vm.watched
		,rv.processed = vm.processed
		,rv.playcommand = vm.playcommand
		,rv.category = vm.category
		,rv.trailer = vm.trailer
		,rv.host = vm.host
		,rv.screenshot = vm.screenshot
		,rv.banner = vm.banner
		,rv.fanart = vm.fanart
		,rv.insertdate = vm.insertdate
		,rv.contenttype = vm.contenttype
            WHERE
                rv.intid = vm.intid AND
                rv.partitionlabel = %s;"""
        try:
            LOG("-->Updating all metadata fields from VIDEOMETADATA in REMOVABLEVIDEO table\n")
            cursor.execute(sql, [label])
        except (Exception) as e:
            LOG(e.args[0])

        # and finally delete all the rows in mythtv that match rows in our table for the drive being removed
        sql = """
            DELETE
                vm
            FROM
                videometadata vm, removablevideos rv
            WHERE
                rv.intid = vm.intid AND
                rv.partitionlabel = %s;"""
        try:
            LOG("-->Remove all relevant movie records from VIDEOMETADAT table\n")
            cursor.execute(sql, [label])
        except (MySQLdb.Error) as e:
            LOG(e.args[0])

        LOG("-->All done with success!\n Exiting ...\n")
