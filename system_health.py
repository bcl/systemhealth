#!/usr/bin/python

# ------------------------------------------------------------------------
# Linux System Health Monitoring v1.1
# by Brian C. Lane
# Copyright 2005-2009 by Brian C. Lane
# All Rights Reserved
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA
#
# ------------------------------------------------------------------------
# 07/02/2009   Adding support for output of nut (Network UPS Tools) upsc
#              status command.
#
# 01/20/2008   Added --new which checks for new processes and prompts
#              to add them to the current configuration.
#
# 01/12/2008   Changed comment strings to align better with newer rrdtool
#              fonts. Added try/except on external config options since
#              older versions will not have that.
#
# 09/02/2006   Changed ctime() call to ctime().replace(":","\\:") to 
#              escape the : character for the COMMENT sections.
#
# 06/10/2006   Adding external call feature. This will allow it to call
# bcl          an external program which returns a single numeric ASCII
#              value for inclusion into a rrdtool graph. The external
#              program can be added with the --add command which will
#              then prompt the user for appropriate parameters.
#
# 02/12/2005   Changed version to 0.6 without the useless trailing .0
# bcl
#
# 02/05/2005   Changed it so that --graph and --log can be done at the 
# bcl          same time. Simplified the crontab entry.
#
# 02/01/2005   Nope, the problem is with /proc/meminfo in the 2.6.10
# bcl          kernel. They added a new field - CommitLimit - in the
#              middle of the output.
#              read_meminfo now needs to get alot more complicated. 
#              Instead of just dumping each value into the RRD it needs to
#              parse the field name and put it into the right place in 
#              the RRD, and skip CommitLimit if >2.4 and < 2.6.10
#              Stuff the data from /proc/meminfo into a hash, then walk a
#              list of the fields for the meminfo.rrd and if it isn't in
#              the hash set it to a 'U'.
#
# 01/15/2005   New kernel release broke kernel_rev, fixed it by added a
# bcl          test for version so it should always get the right place.
#
# 08/28/2004   Added more overview pages and links to them from the index.
# bcl
#
# 08/08/2004   This is going to be version 0.5.0 and it WILL go out today.
# bcl
#
# 08/07/2004   Initial release today. Cleaning up some last bits of cruft.
# bcl          Need to add a --check option to generate missing rrd and
#              html files after a manual edit (ie. adding processes)
#
# 08/04/2004   Really finishing up :) Creating graphs and webpages to 
# bcl          display the graphs.
#
# 08/03/2004   Finishing up this project.
# bcl          Adding graphing. Most of the graphing is working.
#
# 08/02/2004   Adding creation of rrd files. Problems running os.spawnv
# bcl          but os.popen works fine.
#
# 08/01/2004   Adding process list checking
# bcl          I'm going to change to using ConfigParser to make it easier
#              to setup, and I am going to add a '--setup' mode that
#              scans the system and asks questions and creates the config
#              file interactivly.
#              Chart generation and initial rrd creation will also be in
#              the same program, keeping everything in one place.
#
# 07/31/2004   Rewriting my old System Health perl scripts in python
# bcl          Network interface logging is working
#              loadavg, meminfo and uptime are all working on 2.4
#              need to test meminfo on 2.6 kernel
#
# ------------------------------------------------------------------------
import sys, os, string, re, traceback, ConfigParser, pickle
from time import *
from getopt import *


# Diagnostic, ask user for this later
upsc_host = "cyberpower@localhost"

release_version = "v1.1"

# turn on a bunch of debugging prints
debug = 0

# getopt command line arguments
command = {
          }

# Where to get the configuration from
config_file = os.getenv("HOME") + os.sep + ".syshealthrc"

# Possible paths for system executables (used in setup)
df_paths      = ["/bin/df"]
ps_paths      = ["/bin/ps"]
rrdtool_paths = ["/usr/bin/rrdtool","/usr/local/bin/rrdtool","/usr/local/rrdtool/bin/rrdtool"]
upsc_paths    = ["/bin/upsc"]

# Start with empty paths to the binaries
df_path      = ""
ps_path      = ""
rrdtool_path = ""
upsc_path    = ""

# .png image size (should be in the config file)
width  = 400
height = 100

# Time graphs to generate (shortest first)
rrd_time = [ "-3hours", "-32hours", "-8days", "-5weeks", "-13months" ]


# meminfo fields (as of kernel 2.6.10)
meminfo_fields = [
                    "MemTotal",
                    "MemFree",
                    "Buffers",
                    "Cached",
                    "SwapCached",
                    "Active",
                    "Inactive",
                    "HighTotal",
                    "HighFree",
                    "LowTotal",
                    "LowFree",
                    "SwapTotal",
                    "SwapFree",
                    "Dirty",
                    "Writeback",
                    "Mapped",
                    "Slab",
                    "CommitLimit",
                    "Committed_AS",
                    "PageTables",
                    "VmallocTotal",
                    "VmallocUsed",
                    "VmallocChunk",
                    "HugePages_Total",
                    "HugePages_Free",
                    "Hugepagesize"
                 ]

upsc_fields = [
		("battery.charge","bat_charge"),
		("battery.charge.low","bat_charge_low"),
		("battery.charge.warning","bat_warning"),
		("battery.runtime","bat_runtime"),
		("battery.runtime.low","bat_runtime_low"),
		("battery.voltage","bat_voltage"),
		("battery.voltage.nominal","bat_volts_nominal"),
		("input.transfer.high","input_high"),
		("input.transfer.low","input_low"),
		("input.voltage","input_voltage"),
		("input.voltage.nominal","input_volts_nominal"),
		("output.voltage","output_voltage"),
		("ups.delay.shutdown","shutdown_delay"),
		("ups.load","ups_load"),
		]

upsc_graph = [
        "bat_charge",
        "bat_runtime",
        "bat_voltage",
        "input_voltage",
        "output_voltage",
        "ups_load",
        ]


# ------------------------------------------------------------------------
# System Health Monitor usage
# ------------------------------------------------------------------------
def usage():
    print "System Health Monitor %s" % (release_version)
    print "by Brian C. Lane <bcl@brianlane.com>"
    print "Copyright 2005-2008 by Brian C. Lane"
    print "All Rights Reserved"
    print "Released under GPL v2.0"
    print "See LICENSE and README for details\n\n"
    print "  --setup    Interactive setup of paths, interfaces and processes to be"
    print "             monitored. NOTE that all previous settings in "
    print "             %s are erased." % (config_file)
    print "  --log      Scan system and log current stats to rrd databases"
    print "  --graph    Graph the information in the rrd databases"
    print "  --html     Regenerate the HTML pages (use after manual editing of "
    print "             the %s config file)" % (config_file)
    print "  --check    Check for new additions to the %s " % (config_file)
    print "             config file and create the missing rrd files"
    print "  --add      Add an external program. It should return a single"
    print "             ASCII number (integer or float)"
    print "  --new      Check for new processes and prompt to add missing ones."


# ------------------------------------------------------------------------
# Simple debugging output to stderr
# Prepend it with the function and line number
# ------------------------------------------------------------------------
def debug_print( text ):
    """
    Print debugging information to STDERR, including function namw and
    line number along with a message
    """
    module, line, function, info = traceback.extract_stack()[-2]
    sys.stderr.write( "%s (%s) : %s\n" % (function, line, text) )



def create_loadavg( rrd_file ):
    """
    Create the initial loadavg RRD file
    """
    
    if os.path.isfile( rrd_file ):
        print "%s exists, skipping creation" % (rrd_file)
    else:
        rrd_cmd = ( rrdtool_path, "create", rrd_file, 
                    "DS:load_1:GAUGE:600:U:U",
                    "DS:load_5:GAUGE:600:U:U",
                    "DS:load_15:GAUGE:600:U:U",
                    "DS:running:GAUGE:600:U:U",
                    "DS:total:GAUGE:600:U:U",
                    "RRA:AVERAGE:0.5:1:676",
                    "RRA:AVERAGE:0.5:6:672",
                    "RRA:AVERAGE:0.5:24:720",
                    "RRA:AVERAGE:0.5:288:730",
                    "RRA:MAX:0.5:1:676",
                    "RRA:MAX:0.5:6:672",
                    "RRA:MAX:0.5:24:720",
                    "RRA:MAX:0.5:288:797",
                  )

        if debug>0: 
            debug_print(rrd_cmd)
            
        rrd_string = ""
        for i in rrd_cmd:
            rrd_string = rrd_string + i + " "
        
        output = os.popen( rrd_string ).readlines()

def create_meminfo( rrd_file ):
    """
    Create the initial meminfo RRD file
    """
    if os.path.isfile( rrd_file ):
        print "%s exists, skipping creation" % (rrd_file)
    else:
        rrd_cmd = ( rrdtool_path,  "create", rrd_file,
                    "DS:MemTotal:GAUGE:600:U:U",
                    "DS:MemFree:GAUGE:600:U:U",
                    "DS:Buffers:GAUGE:600:U:U",
                    "DS:Cached:GAUGE:600:U:U",
                    "DS:SwapCached:GAUGE:600:U:U",
                    "DS:Active:GAUGE:600:U:U",
                    "DS:Inactive:GAUGE:600:U:U",
                    "DS:HighTotal:GAUGE:600:U:U",
                    "DS:HighFree:GAUGE:600:U:U",
                    "DS:LowTotal:GAUGE:600:U:U",
                    "DS:LowFree:GAUGE:600:U:U",
                    "DS:SwapTotal:GAUGE:600:U:U",
                    "DS:SwapFree:GAUGE:600:U:U",
                    "DS:Dirty:GAUGE:600:U:U",
                    "DS:Writeback:GAUGE:600:U:U",
                    "DS:Mapped:GAUGE:600:U:U",
                    "DS:Slab:GAUGE:600:U:U",
                    "DS:CommitLimit:GAUGE:600:U:U",
                    "DS:Committed_AS:GAUGE:600:U:U",
                    "DS:PageTables:GAUGE:600:U:U",
                    "DS:VmallocTotal:GAUGE:600:U:U",
                    "DS:VmallocUsed:GAUGE:600:U:U",
                    "DS:VmallocChunk:GAUGE:600:U:U",
                    "DS:HugePages_Total:GAUGE:600:U:U",
                    "DS:HugePages_Free:GAUGE:600:U:U",
                    "DS:Hugepagesize:GAUGE:600:U:U",
                    "RRA:AVERAGE:0.5:1:676",
                    "RRA:AVERAGE:0.5:6:672",
                    "RRA:AVERAGE:0.5:24:720",
                    "RRA:AVERAGE:0.5:288:730",
                    "RRA:MAX:0.5:1:676",
                    "RRA:MAX:0.5:6:672",
                    "RRA:MAX:0.5:24:720",
                    "RRA:MAX:0.5:288:797",
                  )

        if debug>0: 
            debug_print(rrd_cmd)
            
        rrd_string = ""
        for i in rrd_cmd:
            rrd_string = rrd_string + i + " "
        
        output = os.popen( rrd_string ).readlines()
    

def create_uptime( rrd_file ):
    """
    Create the initial uptime RRD file
    """
    if os.path.isfile( rrd_file ):
        print "%s exists, skipping creation" % (rrd_file)
    else:
        rrd_cmd = ( rrdtool_path,  "create", rrd_file,
                    "DS:uptime:GAUGE:600:U:U",
                    "DS:idletime:GAUGE:600:U:U",
                    "RRA:AVERAGE:0.5:1:676",
                    "RRA:AVERAGE:0.5:6:672",
                    "RRA:AVERAGE:0.5:24:720",
                    "RRA:AVERAGE:0.5:288:730",
                    "RRA:MAX:0.5:1:676",
                    "RRA:MAX:0.5:6:672",
                    "RRA:MAX:0.5:24:720",
                    "RRA:MAX:0.5:288:797",
                  )

        if debug>0: 
            debug_print(rrd_cmd)
            
        rrd_string = ""
        for i in rrd_cmd:
            rrd_string = rrd_string + i + " "
        
        output = os.popen( rrd_string ).readlines()


def create_interface( rrd_file ):
    """
    Create a network interface RRD file
    """
    if os.path.isfile( rrd_file ):
        print "%s exists, skipping creation" % (rrd_file)
    else:
        rrd_cmd = ( rrdtool_path,  "create", rrd_file,
                    "DS:rx_bytes:COUNTER:600:U:U",
                    "DS:rx_packets:COUNTER:600:U:U",
                    "DS:rx_errs:COUNTER:600:U:U",
                    "DS:rx_drop:COUNTER:600:U:U",
                    "DS:rx_fifo:COUNTER:600:U:U",
                    "DS:rx_frame:COUNTER:600:U:U",
                    "DS:rx_compressed:COUNTER:600:U:U",
                    "DS:rx_multicast:COUNTER:600:U:U",
                    "DS:tx_bytes:COUNTER:600:U:U",
                    "DS:tx_packets:COUNTER:600:U:U",
                    "DS:tx_errs:COUNTER:600:U:U",
                    "DS:tx_drop:COUNTER:600:U:U",
                    "DS:tx_fifo:COUNTER:600:U:U",
                    "DS:tx_colls:COUNTER:600:U:U",
                    "DS:tx_carrier:COUNTER:600:U:U",
                    "DS:tx_compressed:COUNTER:600:U:U",
                    "RRA:AVERAGE:0.5:1:676",
                    "RRA:AVERAGE:0.5:6:672",
                    "RRA:AVERAGE:0.5:24:720",
                    "RRA:AVERAGE:0.5:288:730",
                    "RRA:MAX:0.5:1:676",
                    "RRA:MAX:0.5:6:672",
                    "RRA:MAX:0.5:24:720",
                    "RRA:MAX:0.5:288:797",
                  )

        if debug>0: 
            debug_print(rrd_cmd)
            
        rrd_string = ""
        for i in rrd_cmd:
            rrd_string = rrd_string + i + " "
        
        output = os.popen( rrd_string ).readlines()

    
def create_drive_space( rrd_file ):
    """
    Create a drive space RRD file
    """
    if os.path.isfile( rrd_file ):
        print "%s exists, skipping creation" % (rrd_file)
    else:
        rrd_cmd = ( rrdtool_path,  "create", rrd_file,
                    "DS:Total:GAUGE:600:U:U",
                    "DS:Used:GAUGE:600:U:U",
                    "DS:Available:GAUGE:600:U:U",
                    "RRA:AVERAGE:0.5:1:676",
                    "RRA:AVERAGE:0.5:6:672",
                    "RRA:AVERAGE:0.5:24:720",
                    "RRA:AVERAGE:0.5:288:730",
                    "RRA:MAX:0.5:1:676",
                    "RRA:MAX:0.5:6:672",
                    "RRA:MAX:0.5:24:720",
                    "RRA:MAX:0.5:288:797",
                  )

        if debug>0: 
            debug_print(rrd_cmd)
            
        rrd_string = ""
        for i in rrd_cmd:
            rrd_string = rrd_string + i + " "
        
        output = os.popen( rrd_string ).readlines()

    
    
def create_drive_inodes( rrd_file ):
    """
    Create a drive inodes RRD file
    """
    if os.path.isfile( rrd_file ):
        print "%s exists, skipping creation" % (rrd_file)
    else:
        rrd_cmd = ( rrdtool_path,  "create", rrd_file,
                    "DS:Inodes:GAUGE:600:U:U",
                    "DS:IUsed:GAUGE:600:U:U",
                    "DS:IFree:GAUGE:600:U:U",
                    "RRA:AVERAGE:0.5:1:676",
                    "RRA:AVERAGE:0.5:6:672",
                    "RRA:AVERAGE:0.5:24:720",
                    "RRA:AVERAGE:0.5:288:730",
                    "RRA:MAX:0.5:1:676",
                    "RRA:MAX:0.5:6:672",
                    "RRA:MAX:0.5:24:720",
                    "RRA:MAX:0.5:288:797",
                  )

        if debug>0: 
            debug_print(rrd_cmd)
            
        rrd_string = ""
        for i in rrd_cmd:
            rrd_string = rrd_string + i + " "
        
        output = os.popen( rrd_string ).readlines()

    
    
def create_process( rrd_file ):
    """
    Create a process RRD file
    """
    if os.path.isfile( rrd_file ):
        print "%s exists, skipping creation" % (rrd_file)
    else:
        rrd_cmd = ( rrdtool_path,  "create", rrd_file,
                    "DS:running:GAUGE:600:U:U",
                    "RRA:AVERAGE:0.5:1:676",
                    "RRA:AVERAGE:0.5:6:672",
                    "RRA:AVERAGE:0.5:24:720",
                    "RRA:AVERAGE:0.5:288:730",
                    "RRA:MAX:0.5:1:676",
                    "RRA:MAX:0.5:6:672",
                    "RRA:MAX:0.5:24:720",
                    "RRA:MAX:0.5:288:797",
                  )

        if debug>0: 
            debug_print(rrd_cmd)
            
        rrd_string = ""
        for i in rrd_cmd:
            rrd_string = rrd_string + i + " "
        
        output = os.popen( rrd_string ).readlines()


def create_gauge( rrd_file ):
    """
    Create a a simple gauge RRD file
    """
    if os.path.isfile( rrd_file ):
        print "%s exists, skipping creation" % (rrd_file)
    else:
        rrd_cmd = ( rrdtool_path,  "create", rrd_file,
                    "DS:value:GAUGE:600:U:U",
                    "RRA:AVERAGE:0.5:1:676",
                    "RRA:AVERAGE:0.5:6:672",
                    "RRA:AVERAGE:0.5:24:720",
                    "RRA:AVERAGE:0.5:288:730",
                    "RRA:MAX:0.5:1:676",
                    "RRA:MAX:0.5:6:672",
                    "RRA:MAX:0.5:24:720",
                    "RRA:MAX:0.5:288:797",
                  )

        if debug>0: 
            debug_print(rrd_cmd)
            
        rrd_string = ""
        for i in rrd_cmd:
            rrd_string = rrd_string + i + " "
        
        output = os.popen( rrd_string ).readlines()


def create_counter( rrd_file ):
    """
    Create a a simple counter RRD file
    """
    if os.path.isfile( rrd_file ):
        print "%s exists, skipping creation" % (rrd_file)
    else:
        rrd_cmd = ( rrdtool_path,  "create", rrd_file,
                    "DS:value:COUNTER:600:U:U",
                    "RRA:AVERAGE:0.5:1:676",
                    "RRA:AVERAGE:0.5:6:672",
                    "RRA:AVERAGE:0.5:24:720",
                    "RRA:AVERAGE:0.5:288:730",
                    "RRA:MAX:0.5:1:676",
                    "RRA:MAX:0.5:6:672",
                    "RRA:MAX:0.5:24:720",
                    "RRA:MAX:0.5:288:797",
                  )

        if debug>0: 
            debug_print(rrd_cmd)
            
        rrd_string = ""
        for i in rrd_cmd:
            rrd_string = rrd_string + i + " "
        
        output = os.popen( rrd_string ).readlines()


def create_upsc( rrd_file ):
    """
    Create the initial upsc RRD file
    """
    if os.path.isfile( rrd_file ):
        print "%s exists, skipping creation" % (rrd_file)
        return
    rrd_cmd = [ rrdtool_path,  "create", rrd_file, ]

    for k in upsc_fields:
        rrd_cmd.append("DS:%s:GAUGE:600:U:U" % (k[1]))

        rrd_cmd += ["RRA:AVERAGE:0.5:1:676",
                    "RRA:AVERAGE:0.5:6:672",
                    "RRA:AVERAGE:0.5:24:720",
                    "RRA:AVERAGE:0.5:288:730",
                    "RRA:MAX:0.5:1:676",
                    "RRA:MAX:0.5:6:672",
                    "RRA:MAX:0.5:24:720",
                    "RRA:MAX:0.5:288:797",
                  ] 

        if debug>0: 
            debug_print(rrd_cmd)
            
        rrd_string = ""
        for i in rrd_cmd:
            rrd_string = rrd_string + i + " "
        
        output = os.popen( rrd_string ).readlines()


def ask_number( prompt, default ):
    """
    Prompt the user to enter a number. If enter it hit the default is
    returned. Entry is checked for conversion to an integer
    """
    done = 0
    while not done:
        tmp_num = raw_input( prompt % (default) )
        if tmp_num != '':
            try:
                new_num = int(tmp_num)
            except:
                print "Please enter a number"
            else:
                done = 1            
        else:
            new_num = default
            done = 1
            
    return new_num


def ask_path( prompt, default, perm=0700 ):
    """
    Prompt user for a path, create it if it doesn't exist and they agree
    set permissions to 0700 by default
    """
    new_path = default
    while not os.path.isdir(new_path):
        tmp_path = raw_input( prompt % (new_path) )
        if tmp_path != '':
            new_path = tmp_path
        if not os.path.isdir(new_path):
            yn = raw_input( "%s does not exist, create it now? (y/N) : " % (new_path) ).lower()
            if yn == 'y':
                try:
                    os.mkdir( new_path, perm )
                except:
                    print "Cannot create %s. Check permissions" % (new_path)
    
    return new_path
    
  

def setup_monitor():
    """
    Interactive setup for the System Health Monitor
    Scans for network interfaces and running processes
    Prompts for paths and checks to make sure they are writeable
    """
    global rrdtool_path
    global ps_path
    global df_path
    global upsc_path
    global width
    global height
    
    
    try:
        cf = open( config_file, "w" )
    except:
        print "Opening %s for writing failed. " % (config_file)
        sys.exit(-1)
        
    config.add_section("paths")

    # Find rrdtool
    for path in rrdtool_paths:
        if os.path.isfile(path):
            break
    else:
        # Prompt the user for the location
        while not os.path.isfile(path):
             path = raw_input("Enter location of rrdtool : ")

    config.set("paths","rrdtool",path)
    rrdtool_path = path
    
    # Find df
    for path in df_paths:
        if os.path.isfile(path):
            break
    else:
        # Prompt the user for the location
        while not os.path.isfile(path):
             path = raw_input("Enter location of df : ")

    config.set("paths","df",path)
    df_path = path
    
    # Find ps
    for path in ps_paths:
        if os.path.isfile(path):
            break
    else:
        # Prompt the user for the location
        while not os.path.isfile(path):
             path = raw_input("Enter location of ps : ")

    config.set("paths","ps",path)
    ps_path = path

    # Find upsc
    for path in upsc_paths:
        if os.path.isfile(path):
	    break
    else:
        # Prompt the user for the location
        while not os.path.isfile(path):
             path = raw_input("Enter location of upsc : ")
    config.set("paths","upsc",path)
    upsc_path = path




    # Get the path to the rrd files
    rrd_path = os.getenv("HOME") + os.sep + "health_rrd"
    rrd_path = ask_path( "Directory to store rrd files [%s] : ", rrd_path, 0700 )
    config.set("paths","rrd_path",rrd_path)

    # Test to make sure we can write to this directory
    done = 0
    while not done:
        try:
            open(rrd_path + os.sep + "write_test", "w").write("system_health.py test\n")
            os.remove( rrd_path + os.sep + "write_test" )
        except:
            # Can't write to the rrd directory
            print( "Cannot write to %s" % (rrd_path + os.sep + "write_test") )
            raw_input( "Please fix permissions and hit enter : " )
        else:
            done = 1
    
    # Get the path to the .png images
    png_path = os.getenv("HOME") + os.sep + "health_html"
    png_path = ask_path( "Directory to store png and html [%s] : ", png_path, 0755 )
    config.set("paths","png_path",png_path)

    # Test to make sure we can write to this directory
    done = 0
    while not done:
        try:
            open(png_path + os.sep + "write_test", "w").write("system_health.py test\n")
            os.remove( png_path + os.sep + "write_test" )
        except:
            # Can't write to the rrd directory
            print( "Cannot write to %s" % (png_path + os.sep + "write_test") )
            raw_input( "Please fix permissions and hit enter : " )
        else:
            done = 1

    # Get the image width and height
    config.add_section("graphs")
    width = ask_number( "Width of graph images  [%d] : ", width )
    config.set("graphs","width", "%d" % (width) )
    
    height = ask_number( "Height of graph images [%d] : ", height )
    config.set("graphs","height","%d" % (height) )

    # Add rrd_time to the config file
    config.set("graphs","time",rrd_time)

    config.set("paths", "loadavg_rrd", "loadavg" )
    create_loadavg( rrd_path + os.sep + "loadavg.rrd" )

    config.set("paths", "meminfo_rrd", "meminfo" )
    create_meminfo( rrd_path + os.sep + "meminfo.rrd" )

    config.set("paths", "uptime_rrd",  "uptime" )
    create_uptime( rrd_path + os.sep + "uptime.rrd" )

    config.set("paths", "upsc_rrd", "upsc" )
    create_upsc( rrd_path + os.sep + "upsc.rrd" )

    config.add_section("interfaces")    
    # Available interfaces
    ifaces = open( "/proc/net/dev" )

    # Skip the information banner
    ifaces.readline()
    ifaces.readline()

    # Read the rest of the lines
    lines = ifaces.readlines()
    ifaces.close()
    
    # Process the interface lines
    for line in lines:
        # Parse the interface line
        # Interface is followed by a ':' and then bytes, possibly with
        # no spaces between : and bytes
        line = line[:-1]
        (device,data) = line.split(':')

        # Get rid of leading spaces
        device = string.lstrip(device)

        # Ask if they want to monitor device
        answer = raw_input( "Monitor %s: (Y/n)" % (device)).lower()

        if (answer == '') or (answer == 'y'):
            # prompt for base filename (used for .rrd and .png files)
            basename = device
            answer = raw_input( "base name for .rrd and .png: [%s] " % (basename))

            if answer != '':
                basename = answer
    
            # Add it to the interfaces section of the config file
            config.set( 'interfaces', device, basename )
            create_interface( rrd_path + os.sep + basename + ".rrd" )

    config.add_section("drives")
    
    # Available drives
    df_cmd = "%s -lP" % (df_path)
    df = os.popen(df_cmd)
    
    # Discard the banner line
    df.readline()
    
    # Read the rest
    lines = df.readlines()
    df.close()
    
    for line in lines:
        # Strip off \n
        line = line[:-1]
        
        # Split on spaces
        # Filesystem, total, used, available, %, mountpoint
        stats = line.split()

        # ask if they want to monitor stats[0] / stats[5]
        answer = raw_input( "Monitor %s mounted on %s: (Y/n)" % (stats[5],stats[0])).lower()

        if (answer == '') or (answer == 'y'):
            # prompt for base filename (used for .rrd and .png files)
            if stats[5] == '/':
                basename = "root"
            else:
                basename = os.path.basename(stats[5])
                
            answer = raw_input( "base name for .rrd and .png: [%s] " % (basename))

            if answer != '':
                basename = answer
    
            # Add it to the interfaces section of the config file
            config.set( 'drives', stats[5], basename )
            create_drive_space( rrd_path + os.sep + basename + "_space.rrd" )
            create_drive_inodes( rrd_path + os.sep + basename + "_inodes.rrd" )

    config.add_section( "processes" )
    
    # Available processes
    ps_cmd = "%s -A -o comm --no-headers" % (ps_path)
    ps = os.popen(ps_cmd)
    
    # read everything
    lines = ps.readlines()
    ps.close()
    
    process_list = []
    # Unique list of processes
    for line in lines:
        # strip \n
        line = line[:-1]
        
        # If its not already in the list, add it
        if line not in process_list:
            process_list.append(line)
            
    process_list.sort()

    for process in process_list:
        # Prompt user to monitor this process
        answer = raw_input( "Monitor %s: (y/N)" % (process)).lower()

        if answer == 'y':
            basename = process
                
            answer = raw_input( "base name for .rrd and .png: [%s] " % (basename))

            if answer != '':
                basename = answer
    
            # Add it to the interfaces section of the config file
            config.set( 'processes', process, basename )
            create_process( rrd_path + os.sep + basename + ".rrd" )

    # Placeholder for external programs
    config.add_section("external")    

    # Write the new config file
    config.write(cf)
    cf.close()


def new_processes(processes):
    '''
    Check for new processes and prompt to add them
    '''
    global rrdtool_path
    global ps_path

    # Available processes
    ps_cmd = "%s -A -o comm --no-headers" % (ps_path)
    ps = os.popen(ps_cmd)
    
    # read everything
    lines = ps.readlines()
    ps.close()
    
    process_list = []
    # Unique list of processes
    for line in lines:
        # strip \n
        line = line[:-1]
        
        # If its not already in the list, add it
        if line not in process_list:
            process_list.append(line)
            
    process_list.sort()

    for process in process_list:
        if process in processes:
            continue
            
        # Prompt user to monitor this process
        answer = raw_input( "Monitor %s: (y/N)" % (process)).lower()

        if answer == 'y':
            basename = process
                
            answer = raw_input( "base name for .rrd and .png: [%s] " % (basename))

            if answer != '':
                basename = answer
    
            # Add it to the interfaces section of the config file
            config.set( 'processes', process, basename )
            create_process( rrd_path + os.sep + basename + ".rrd" )

    try:
        cf = open( config_file, "w" )
        config.write(cf)
        cf.close()
    except:
        print "Opening %s for writing failed. " % (config_file)
        sys.exit(-1)


def add_external():
    """
    Prompt the user for an external program to be called. It should return
    a single ASCII number (integer or float).
    
    Each external program needs a 'name' used to label the rrd graph, a
    path to the executable, and a name for the rrd file to store the data in.

    The config file must have been previously read into config object
    """
    rrd_path = config.get("paths","rrd_path")
    
    
    # 2. Add an external section if there isn't one already
    # How to check if a section exists?        
    try:
        config.options("external")
    except:
        config.add_section("external")

    # 3. Ask the user for the path to the executable, check that it is
    #    present and executable. display the output of it.
    ext_path = ""
    while not os.path.isfile(ext_path):
        ext_cmd = raw_input("Enter '/path/filename args' to external program : ")
        ext_path = ext_cmd.split()[0]

    # 4. Ask for a name for the graph
    graph_name = raw_input( "Name for graph: " )

    # 5. Ask for a name for the rrd file (use name as a suggestion)
    basename = graph_name
    answer = raw_input( "base name for .rrd and .png: [%s] " % (basename))
    if answer != '':
        basename = answer
    
    # Add it to the external section of the config file, but pickle it first
    p = pickle.dumps([graph_name, basename, ext_cmd])
    config.set( 'external', basename, p )

    # 6. Ask if it is a counter or a gauge (always increments, like a packet
    #    counter or indicates a level like a load or temperature).
    answer = ""
    while answer not in ['g','G','c','C']:
        answer = raw_input( "Is the output a Gauge or Counter (G/C)? : " )
        if answer in ['g','G']:
            create_gauge( rrd_path + os.sep + basename + ".rrd")
        elif answer in ['c','C']:
            create_counter( rrd_path + os.sep + basename + ".rrd")
        else:
            print "Please enter G for GAUGE or C for COUNTER"

    # 7. Write changes to the config file
    try:
        cf = open( config_file, "w" )
        config.write(cf)
        cf.close()
    except:
        print "Opening %s for writing failed. " % (config_file)
        sys.exit(-1)
    

def create_html():
    """
    Create the html pages for viewing the charts. Top level index.html and 
    sub-pages for each device, disk and process showing day, week month and
    year historical graphs.
    """
    # Create the web pages to view the results
    # Top level page with the daily image for each item
    # sub-pages for each item with the day, week, month, year
    f = open( png_path + os.sep + "index.html", "w" )

    f.write("<center>System Health<p>\n")
    f.write("<a href=\"index.html\">3 Hour View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"32hour.html\">32 Hour View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"8day.html\">8 day View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"5week.html\">5 week View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"13month.html\">13 month View</a><p>");
    
    f.write("<b>Network Interfaces</b><table border=1 bgcolor=#EEEEEE><tr>")

    col = 0
    keylist = interfaces_rrd.keys()
    keylist.sort()
    for key in keylist:
        f.write("<td>%s<br><a href=%s.html><img src=%s%s.png></a></td>\n" % (key,interfaces_rrd[key],interfaces_rrd[key],rrd_time[0]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table>\n")
    f.write("<p>\n")

    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    f.write("<td><b>Load</b><br><a href=%s.html><img src=%s%s.png></a></td>\n" % (loadavg_rrd, loadavg_rrd, rrd_time[0]) )
    f.write("<td><b>Uptime</b><br><a href=%s.html><img src=%s%s.png></a></td></tr>\n" % (uptime_rrd, uptime_rrd, rrd_time[0]) )
    f.write("<tr><td><b>Memory</b><br><a href=%s.html><img src=%s%s.png></a></td><tr></tr>\n" % (meminfo_rrd, meminfo_rrd, rrd_time[0] ) )
    f.write("</table>")
    
    f.write("<p><b>Disk Usage, space and inodes</b><br>")
    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    col = 0
    key_list = drives_rrd.keys()
    key_list.sort()
    for key in key_list:
        f.write("<td>%s<br><a href=%s.html><img src=%s_space%s.png></a>\n<br>\n" % (key,drives_rrd[key], drives_rrd[key], rrd_time[0]) )
        f.write("<a href=%s.html><img src=%s_inodes%s.png></a></td>\n" % (drives_rrd[key], drives_rrd[key], rrd_time[0]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table>\n")
    f.write("<p>\n")

    f.write("<b>Processes</b><br>")
    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    col = 0    
    key_list = process_rrd.keys()
    key_list.sort()
    for key in key_list:
        f.write("<td>%s<br><a href=%s.html><img src=%s%s.png></a></td>\n" % (key,process_rrd[key], process_rrd[key], rrd_time[0]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table><p>\n")

    # upsc if it is supported
    if 1:
        f.write("<b>UPS</b><br>")
        f.write("<table border=1 bgcolor=#EEEEEE><tr>")
        col = 0
        upsc_graph.sort()
        for k in upsc_graph:
            f.write("<td>%s<br><a href=upsc_%s.html><img src=upsc_%s%s.png></a></td>\n" % (k,k,k, rrd_time[0]) )
            col = col + 1
            if( col > 1 ):
                f.write("</tr><tr>\n")
                col = 0
        f.write("</tr></table><p>\n")

    f.write("<b>Other</b><br>")
    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    col = 0    
    key_list = external_rrd.keys()
    key_list.sort()
    for key in key_list:
        f.write("<td>%s<br><a href=%s.html><img src=%s%s.png></a></td>\n" % (external_rrd[key][0],external_rrd[key][1], external_rrd[key][1], rrd_time[0]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table><p>\n")

    # Write the footer
    f.write("<hr><p><font size=-2>Created with <a href=\"http://www.brianlane.com/software/systemhealth/\">System Health Monitor</a> by Brian C. Lane</font><p>\n")
    f.write("</center>\n")
    f.close()


    # Create the web pages to view the results
    # Top level page with the daily image for each item
    # sub-pages for each item with the day, week, month, year
    f = open( png_path + os.sep + "32hour.html", "w" )

    f.write("<center>System Health - 32 hour view<p>\n")
    f.write("<a href=\"index.html\">3 Hour View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"32hour.html\">32 Hour View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"8day.html\">8 day View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"5week.html\">5 week View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"13month.html\">13 month View</a><p>");
    
    
    f.write("<b>Network Interfaces</b><table border=1 bgcolor=#EEEEEE><tr>")

    col = 0
    keylist = interfaces_rrd.keys()
    keylist.sort()
    for key in keylist:
        f.write("<td>%s<br><a href=%s.html><img src=%s%s.png></a></td>\n" % (key,interfaces_rrd[key],interfaces_rrd[key],rrd_time[1]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table>\n")
    f.write("<p>\n")

    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    f.write("<td><b>Load</b><br><a href=%s.html><img src=%s%s.png></a></td>\n" % (loadavg_rrd, loadavg_rrd, rrd_time[1]) )
    f.write("<td><b>Uptime</b><br><a href=%s.html><img src=%s%s.png></a></td></tr>\n" % (uptime_rrd, uptime_rrd, rrd_time[1]) )
    f.write("<tr><td><b>Memory</b><br><a href=%s.html><img src=%s%s.png></a></td><tr></tr>\n" % (meminfo_rrd, meminfo_rrd, rrd_time[1] ) )
    f.write("</table>")
    
    f.write("<p><b>Disk Usage, space and inodes</b><br>")
    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    col = 0
    key_list = drives_rrd.keys()
    key_list.sort()
    for key in key_list:
        f.write("<td>%s<br><a href=%s.html><img src=%s_space%s.png></a>\n<br>\n" % (key,drives_rrd[key], drives_rrd[key], rrd_time[1]) )
        f.write("<a href=%s.html><img src=%s_inodes%s.png></a></td>\n" % (drives_rrd[key], drives_rrd[key], rrd_time[1]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table>\n")
    f.write("<p>\n")

    f.write("<b>Processes</b><br>")
    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    col = 0    
    key_list = process_rrd.keys()
    key_list.sort()
    for key in key_list:
        f.write("<td>%s<br><a href=%s.html><img src=%s%s.png></a></td>\n" % (key,process_rrd[key], process_rrd[key], rrd_time[1]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table><p>\n")

    # upsc if it is supported
    if 1:
        f.write("<b>UPS</b><br>")
        f.write("<table border=1 bgcolor=#EEEEEE><tr>")
        col = 0
        upsc_graph.sort()
        for k in upsc_graph:
            f.write("<td>%s<br><a href=upsc_%s.html><img src=upsc_%s%s.png></a></td>\n" % (k,k,k, rrd_time[1]) )
            col = col + 1
            if( col > 1 ):
                f.write("</tr><tr>\n")
                col = 0
        f.write("</tr></table><p>\n")

    f.write("<b>Other</b><br>")
    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    col = 0    
    key_list = external_rrd.keys()
    key_list.sort()
    for key in key_list:
        f.write("<td>%s<br><a href=%s.html><img src=%s%s.png></a></td>\n" % (external_rrd[key][0],external_rrd[key][1], external_rrd[key][1], rrd_time[1]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table><p>\n")

    # Write the footer
    f.write("<hr><p><font size=-2>Created with <a href=\"http://www.brianlane.com/software/systemhealth/\">System Health Monitor</a> by Brian C. Lane</font><p>\n")
    f.write("</center>\n")
    f.close()


    # Create the web pages to view the results
    # Top level page with the daily image for each item
    # sub-pages for each item with the day, week, month, year
    f = open( png_path + os.sep + "8day.html", "w" )

    f.write("<center>System Health - 8 day view<p>\n")
    f.write("<a href=\"index.html\">3 Hour View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"32hour.html\">32 Hour View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"8day.html\">8 day View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"5week.html\">5 week View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"13month.html\">13 month View</a><p>");
    
    
    f.write("<b>Network Interfaces</b><table border=1 bgcolor=#EEEEEE><tr>")

    col = 0
    keylist = interfaces_rrd.keys()
    keylist.sort()
    for key in keylist:
        f.write("<td>%s<br><a href=%s.html><img src=%s%s.png></a></td>\n" % (key,interfaces_rrd[key],interfaces_rrd[key],rrd_time[2]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table>\n")
    f.write("<p>\n")

    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    f.write("<td><b>Load</b><br><a href=%s.html><img src=%s%s.png></a></td>\n" % (loadavg_rrd, loadavg_rrd, rrd_time[2]) )
    f.write("<td><b>Uptime</b><br><a href=%s.html><img src=%s%s.png></a></td></tr>\n" % (uptime_rrd, uptime_rrd, rrd_time[2]) )
    f.write("<tr><td><b>Memory</b><br><a href=%s.html><img src=%s%s.png></a></td><tr></tr>\n" % (meminfo_rrd, meminfo_rrd, rrd_time[2] ) )
    f.write("</table>")
    
    f.write("<p><b>Disk Usage, space and inodes</b><br>")
    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    col = 0
    key_list = drives_rrd.keys()
    key_list.sort()
    for key in key_list:
        f.write("<td>%s<br><a href=%s.html><img src=%s_space%s.png></a>\n<br>\n" % (key,drives_rrd[key], drives_rrd[key], rrd_time[2]) )
        f.write("<a href=%s.html><img src=%s_inodes%s.png></a></td>\n" % (drives_rrd[key], drives_rrd[key], rrd_time[2]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table>\n")
    f.write("<p>\n")

    f.write("<b>Processes</b><br>")
    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    col = 0    
    key_list = process_rrd.keys()
    key_list.sort()
    for key in key_list:
        f.write("<td>%s<br><a href=%s.html><img src=%s%s.png></a></td>\n" % (key,process_rrd[key], process_rrd[key], rrd_time[2]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table><p>\n")

    # upsc if it is supported
    if 1:
        f.write("<b>UPS</b><br>")
        f.write("<table border=1 bgcolor=#EEEEEE><tr>")
        col = 0
        upsc_graph.sort()
        for k in upsc_graph:
            f.write("<td>%s<br><a href=upsc_%s.html><img src=upsc_%s%s.png></a></td>\n" % (k,k,k, rrd_time[2]) )
            col = col + 1
            if( col > 1 ):
                f.write("</tr><tr>\n")
                col = 0
        f.write("</tr></table><p>\n")

    f.write("<b>Other</b><br>")
    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    col = 0    
    key_list = external_rrd.keys()
    key_list.sort()
    for key in key_list:
        f.write("<td>%s<br><a href=%s.html><img src=%s%s.png></a></td>\n" % (external_rrd[key][0],external_rrd[key][1], external_rrd[key][1], rrd_time[2]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table><p>\n")

    # Write the footer
    f.write("<hr><p><font size=-2>Created with <a href=\"http://www.brianlane.com/software/systemhealth/\">System Health Monitor</a> by Brian C. Lane</font><p>\n")
    f.write("</center>\n")
    f.close()




    # Create the web pages to view the results
    # Top level page with the daily image for each item
    # sub-pages for each item with the day, week, month, year
    f = open( png_path + os.sep + "5week.html", "w" )

    f.write("<center>System Health - 8 day view<p>\n")
    f.write("<a href=\"index.html\">3 Hour View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"32hour.html\">32 Hour View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"8day.html\">8 day View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"5week.html\">5 week View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"13month.html\">13 month View</a><p>");
    
    
    f.write("<b>Network Interfaces</b><table border=1 bgcolor=#EEEEEE><tr>")

    col = 0
    keylist = interfaces_rrd.keys()
    keylist.sort()
    for key in keylist:
        f.write("<td>%s<br><a href=%s.html><img src=%s%s.png></a></td>\n" % (key,interfaces_rrd[key],interfaces_rrd[key],rrd_time[3]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table>\n")
    f.write("<p>\n")

    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    f.write("<td><b>Load</b><br><a href=%s.html><img src=%s%s.png></a></td>\n" % (loadavg_rrd, loadavg_rrd, rrd_time[3]) )
    f.write("<td><b>Uptime</b><br><a href=%s.html><img src=%s%s.png></a></td></tr>\n" % (uptime_rrd, uptime_rrd, rrd_time[3]) )
    f.write("<tr><td><b>Memory</b><br><a href=%s.html><img src=%s%s.png></a></td><tr></tr>\n" % (meminfo_rrd, meminfo_rrd, rrd_time[3] ) )
    f.write("</table>")
    
    f.write("<p><b>Disk Usage, space and inodes</b><br>")
    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    col = 0
    key_list = drives_rrd.keys()
    key_list.sort()
    for key in key_list:
        f.write("<td>%s<br><a href=%s.html><img src=%s_space%s.png></a>\n<br>\n" % (key,drives_rrd[key], drives_rrd[key], rrd_time[3]) )
        f.write("<a href=%s.html><img src=%s_inodes%s.png></a></td>\n" % (drives_rrd[key], drives_rrd[key], rrd_time[3]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table>\n")
    f.write("<p>\n")

    f.write("<b>Processes</b><br>")
    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    col = 0    
    key_list = process_rrd.keys()
    key_list.sort()
    for key in key_list:
        f.write("<td>%s<br><a href=%s.html><img src=%s%s.png></a></td>\n" % (key,process_rrd[key], process_rrd[key], rrd_time[3]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table><p>\n")

    # upsc if it is supported
    if 1:
        f.write("<b>UPS</b><br>")
        f.write("<table border=1 bgcolor=#EEEEEE><tr>")
        col = 0
        upsc_graph.sort()
        for k in upsc_graph:
            f.write("<td>%s<br><a href=upsc_%s.html><img src=upsc_%s%s.png></a></td>\n" % (k,k,k, rrd_time[3]) )
            col = col + 1
            if( col > 1 ):
                f.write("</tr><tr>\n")
                col = 0
        f.write("</tr></table><p>\n")

    f.write("<b>Other</b><br>")
    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    col = 0    
    key_list = external_rrd.keys()
    key_list.sort()
    for key in key_list:
        f.write("<td>%s<br><a href=%s.html><img src=%s%s.png></a></td>\n" % (external_rrd[key][0],external_rrd[key][1], external_rrd[key][1], rrd_time[3]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table><p>\n")

    # Write the footer
    f.write("<hr><p><font size=-2>Created with <a href=\"http://www.brianlane.com/software/systemhealth/\">System Health Monitor</a> by Brian C. Lane</font><p>\n")
    f.write("</center>\n")
    f.close()



    # Create the web pages to view the results
    # Top level page with the daily image for each item
    # sub-pages for each item with the day, week, month, year
    f = open( png_path + os.sep + "13month.html", "w" )

    f.write("<center>System Health - 8 day view<p>\n")
    f.write("<a href=\"index.html\">3 Hour View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"32hour.html\">32 Hour View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"8day.html\">8 day View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"5week.html\">5 week View</a>&nbsp;<b>|</b>");
    f.write("<a href=\"13month.html\">13 month View</a><p>");
    
    
    f.write("<b>Network Interfaces</b><table border=1 bgcolor=#EEEEEE><tr>")

    col = 0
    keylist = interfaces_rrd.keys()
    keylist.sort()
    for key in keylist:
        f.write("<td>%s<br><a href=%s.html><img src=%s%s.png></a></td>\n" % (key,interfaces_rrd[key],interfaces_rrd[key],rrd_time[4]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table>\n")
    f.write("<p>\n")

    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    f.write("<td><b>Load</b><br><a href=%s.html><img src=%s%s.png></a></td>\n" % (loadavg_rrd, loadavg_rrd, rrd_time[4]) )
    f.write("<td><b>Uptime</b><br><a href=%s.html><img src=%s%s.png></a></td></tr>\n" % (uptime_rrd, uptime_rrd, rrd_time[4]) )
    f.write("<tr><td><b>Memory</b><br><a href=%s.html><img src=%s%s.png></a></td><tr></tr>\n" % (meminfo_rrd, meminfo_rrd, rrd_time[4] ) )
    f.write("</table>")
    
    f.write("<p><b>Disk Usage, space and inodes</b><br>")
    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    col = 0
    key_list = drives_rrd.keys()
    key_list.sort()
    for key in key_list:
        f.write("<td>%s<br><a href=%s.html><img src=%s_space%s.png></a>\n<br>\n" % (key,drives_rrd[key], drives_rrd[key], rrd_time[4]) )
        f.write("<a href=%s.html><img src=%s_inodes%s.png></a></td>\n" % (drives_rrd[key], drives_rrd[key], rrd_time[4]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table>\n")
    f.write("<p>\n")

    f.write("<b>Processes</b><br>")
    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    col = 0    
    key_list = process_rrd.keys()
    key_list.sort()
    for key in key_list:
        f.write("<td>%s<br><a href=%s.html><img src=%s%s.png></a></td>\n" % (key,process_rrd[key], process_rrd[key], rrd_time[4]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table><p>\n")

    # upsc if it is supported
    if 1:
        f.write("<b>UPS</b><br>")
        f.write("<table border=1 bgcolor=#EEEEEE><tr>")
        col = 0
        upsc_graph.sort()
        for k in upsc_graph:
            f.write("<td>%s<br><a href=upsc_%s.html><img src=upsc_%s%s.png></a></td>\n" % (k,k,k, rrd_time[4]) )
            col = col + 1
            if( col > 1 ):
                f.write("</tr><tr>\n")
                col = 0
        f.write("</tr></table><p>\n")

    f.write("<b>Other</b><br>")
    f.write("<table border=1 bgcolor=#EEEEEE><tr>")
    col = 0    
    key_list = external_rrd.keys()
    key_list.sort()
    for key in key_list:
        f.write("<td>%s<br><a href=%s.html><img src=%s%s.png></a></td>\n" % (external_rrd[key][0],external_rrd[key][1], external_rrd[key][1], rrd_time[4]) )
        col = col + 1
        if( col > 1 ):
            f.write("</tr><tr>\n")
            col = 0
    f.write("</tr></table><p>\n")

    # Write the footer
    f.write("<hr><p><font size=-2>Created with <a href=\"http://www.brianlane.com/software/systemhealth/\">System Health Monitor</a> by Brian C. Lane</font><p>\n")
    f.write("</center>\n")
    f.close()



    # Create individual pages

    # Interface pages
    for key in interfaces_rrd.keys():
        f = open( png_path + os.sep + interfaces_rrd[key] + ".html", "w")
        f.write("<center>")
        f.write("<b>%s</b><p>" % (key) )
        for t in rrd_time:
            f.write("%s<br><img src=%s%s.png><br>\n" % (t,interfaces_rrd[key], t) )
    f.write("<p><hr><p><font size=-2>Created with <a href=\"http://www.brianlane.com/software/systemhealth/\">System Health Monitor</a> by Brian C. Lane</font><p>\n")
    f.write("</center>")
    f.close()
   
    f = open( png_path + os.sep + loadavg_rrd + ".html", "w" )
    f.write("<center>")
    f.write("<b>loadavg</b><p>" )
    for t in rrd_time:
        f.write("%s<br><img src=%s%s.png><br>\n" % (t,loadavg_rrd, t) )
    f.write("<p><hr><p><font size=-2>Created with <a href=\"http://www.brianlane.com/software/systemhealth/\">System Health Monitor</a> by Brian C. Lane</font><p>\n")
    f.write("</center>")
    f.close()

    f = open( png_path + os.sep + uptime_rrd + ".html", "w" )
    f.write("<center>")
    f.write("<b>uptime</b><p>" )
    for t in rrd_time:
        f.write("%s<br><img src=%s%s.png><br>\n" % (t,uptime_rrd, t) )
    f.write("<p><hr><p><font size=-2>Created with <a href=\"http://www.brianlane.com/software/systemhealth/\">System Health Monitor</a> by Brian C. Lane</font><p>\n")
    f.write("</center>")
    f.close()
            
    f = open( png_path + os.sep + meminfo_rrd + ".html", "w" )
    f.write("<center>")
    f.write("<b>meminfo</b><p>" )
    for t in rrd_time:
        f.write("%s<br><img src=%s%s.png><br>\n" % (t,meminfo_rrd, t) )
    f.write("<p><hr><p><font size=-2>Created with <a href=\"http://www.brianlane.com/software/systemhealth/\">System Health Monitor</a> by Brian C. Lane</font><p>\n")
    f.write("</center>")
    f.close()

    for key in drives_rrd.keys():
        f = open( png_path + os.sep + drives_rrd[key] + ".html", "w" )
        f.write("<center>")
        f.write("<b>%s</b><p>" % (key) )
        for t in rrd_time:
            f.write("%s<br><img src=%s_space%s.png><br>\n" % (t,drives_rrd[key], t) )
            f.write("<img src=%s_inodes%s.png><br>\n" % (drives_rrd[key], t) )
        f.write("<p><hr><p><font size=-2>Created with <a href=\"http://www.brianlane.com/software/systemhealth/\">System Health Monitor</a> by Brian C. Lane</font><p>\n")
        f.write("</center>")
        f.close()

    for key in process_rrd.keys():
        f = open( png_path + os.sep + process_rrd[key] + ".html", "w" )
        f.write("<center>")
        f.write("<b>%s</b><p>" % (key) )
        for t in rrd_time:
            f.write("%s<br><img src=%s%s.png><br>\n" % (t,process_rrd[key], t) )
        f.write("<p><hr><p><font size=-2>Created with <a href=\"http://www.brianlane.com/software/systemhealth/\">System Health Monitor</a> by Brian C. Lane</font><p>\n")
        f.write("</center>")
        f.close()

    for key in external_rrd.keys():
        f = open( png_path + os.sep + external_rrd[key][1] + ".html", "w" )
        f.write("<center>")
        f.write("<b>%s</b><p>" % (external_rrd[key][0]) )
        for t in rrd_time:
            f.write("%s<br><img src=%s%s.png><br>\n" % (t,external_rrd[key][1], t) )

        # Write the footer
        f.write("<p><hr><p><font size=-2>Created with <a href=\"http://www.brianlane.com/software/systemhealth/\">System Health Monitor</a> by Brian C. Lane</font><p>\n")
        f.write("</center>")
        f.close()


def check_files():
    """
    Check to make sure all the needed rrd files exist. Create any missing
    files.
    """        
    if not os.path.isfile(  rrd_path + os.sep + loadavg_rrd + ".rrd" ):
        print "Creating " + rrd_path + os.sep + loadavg_rrd + ".rrd"
        create_loadavg( rrd_path + os.sep + loadavg_rrd + ".rrd" )

    if not os.path.isfile( rrd_path + os.sep + meminfo_rrd + ".rrd" ):
        print "Creating " + rrd_path + os.sep + meminfo_rrd + ".rrd"
        create_meminfo( rrd_path + os.sep + meminfo_rrd + ".rrd" )

    if not os.path.isfile( rrd_path + os.sep + uptime_rrd + ".rrd" ):
        print "Creating " + rrd_path + os.sep + uptime_rrd + ".rrd"
        create_uptime( rrd_path + os.sep + uptime_rrd + ".rrd" )
    
    if not os.path.isfile( rrd_path + os.sep + upsc_rrd + ".rrd" ):
        print "Creating " + rrd_path + os.sep + upsc_rrd + ".rrd"
        create_upsc( rrd_path + os.sep + upsc_rrd + ".rrd" )
    
    for iface in interfaces_rrd.keys():
        if not os.path.isfile( rrd_path + os.sep + interfaces_rrd[iface] + ".rrd" ):
            print "Creating " + rrd_path + os.sep + interfaces_rrd[iface] + ".rrd"
            create_interface( rrd_path + os.sep + interfaces_rrd[iface] + ".rrd" )
        
    for key in drives_rrd.keys():
        if not os.path.isfile( rrd_path + os.sep + drives_rrd[key] + "_space.rrd" ):
            print "Creating " + rrd_path + os.sep + interfaces_rrd[iface] + ".rrd"
            create_drive_space( rrd_path + os.sep + drives_rrd[key] + "_space.rrd" )
    
        if not os.path.isfile( rrd_path + os.sep + drives_rrd[key] + "_inodes.rrd" ):
            print "Creating " + rrd_path + os.sep + drives_rrd[key] + "_inodes.rrd"
            create_drive_inodes( rrd_path + os.sep + drives_rrd[key] + "_inodes.rrd" )
    
    for key in process_rrd.keys():
        if not os.path.isfile( rrd_path + os.sep + process_rrd[key] + ".rrd" ):
            print "Creating " + rrd_path + os.sep + process_rrd[key] + ".rrd"
            create_process( rrd_path + os.sep + process_rrd[key] + ".rrd" )


def read_interfaces( interface_rrd ):
    """
    Read the stats from an interface and store it in rrd
    """
    ifaces = open( "/proc/net/dev" )

    # Skip the information banner
    ifaces.readline()
    ifaces.readline()

    # Read the rest of the lines
    lines = ifaces.readlines()
    ifaces.close()
    
    # Process the interface lines
    for line in lines:
        # Parse the interface line
        # Interface is followed by a ':' and then bytes, possibly with
        # no spaces between : and bytes
        line = line[:-1]
        (device,data) = line.split(':')

        # Get rid of leading spaces
        device = string.lstrip(device)

        # get the stats    
        stats = data.split()
    
        if interface_rrd.has_key(device):
            # Update the interface rrd
            rrd_data = "N:" + string.join(stats,':')
            # Run rrdtool in as secure a fashion as possible
            rrd_file = rrd_path + os.sep + interface_rrd[device] + ".rrd"
            rrd_cmd = ("rrdtool","update", rrd_file, rrd_data)

            if debug>0: 
                debug_print(rrd_cmd)
                
            pid = os.spawnv( os.P_NOWAIT, rrdtool_path, rrd_cmd)

def read_loadavg( loadavg_rrd ):
    """"
    Read the current system load from /proc/loadavg
    """
    loadavg = open("/proc/loadavg").readline()
    loadavg = loadavg[:-1]
    
    # Contents are space separated:
    # 5, 10, 15 min avg. load, running proc/total threads, last pid
    stats = loadavg.split()
    running = stats[3].split( "/" )
    
    # Update the interface rrd
    rrd_data = "N:" + string.join(stats[0:3],':') + ":" + string.join( running, ':' )
    
    # Run rrdtool in as secure a fashion as possible
    rrd_file = rrd_path + os.sep + loadavg_rrd + ".rrd"
    rrd_cmd = ("rrdtool","update", rrd_file, rrd_data)

    if debug>0: 
        debug_print(rrd_cmd)
        
    pid = os.spawnv( os.P_NOWAIT, rrdtool_path, rrd_cmd)
    
def read_uptime( uptime_rrd ):
    """
    Read the uptime from /proc/uptime
    """
    uptime = open("/proc/uptime").readline()
    uptime = uptime[:-1]
    
    # Contents are space separated:
    # uptime idle time
    stats = uptime.split()
    
    # Update the interface rrd
    rrd_data = "N:" + string.join(stats,':')
    
    # Run rrdtool in as secure a fashion as possible
    rrd_file = rrd_path + os.sep + uptime_rrd + ".rrd"
    rrd_cmd = ("rrdtool","update", rrd_file, rrd_data)

    if debug>0: 
        debug_print(rrd_cmd)
        
    pid = os.spawnv( os.P_NOWAIT, rrdtool_path, rrd_cmd)
    
def read_meminfo( meminfo_rrd ):
    """
    Read the current status of memory from /proc/meminfo
    """
    meminfo = open("/proc/meminfo")
    
    if kernel_rev <= 2.4:
        # Kernel 2.4 has extra lines of info, duplicate of later info
        meminfo.readline()
        meminfo.readline()
        meminfo.readline()
        
    lines = meminfo.readlines()
    meminfo.close()

    # Stuff the fields into a hash
    meminfo_stats = {}
    for line in lines:
        line = line[:-1]
        stats = line.split()
        meminfo_stats[ stats[0][:-1] ] = stats[1]

    # Creat the rrd data entry    
    rrd_data = "N:"
    for field in meminfo_fields:
        if field in meminfo_stats.keys():
            rrd_data = rrd_data + meminfo_stats[field]  + ":"
        else:
            rrd_data = rrd_data + "U:"

    # remove trailing ':'    
    rrd_data = rrd_data[:-1]

    # Run rrdtool in as secure a fashion as possible
    rrd_file = rrd_path + os.sep + meminfo_rrd + ".rrd"
    rrd_cmd = ("rrdtool","update", rrd_file, rrd_data)

    if debug>0: 
        debug_print(rrd_cmd)
        
    pid = os.spawnv( os.P_NOWAIT, rrdtool_path, rrd_cmd)

    
def read_drive_space( drive_space_rrd ):
    """
    Read the drive space status from the output of 'df -P'
    """
    # Run df -P andgrab its output. Ignore first line of descriptive text
    df_cmd = "%s -lP" % (df_path)
    df = os.popen(df_cmd)
    
    # Discard the banner line
    df.readline()
    
    # Read the rest
    lines = df.readlines()
    df.close()
    
    for line in lines:
        # Strip off \n
        line = line[:-1]
        
        # Split on spaces
        # Filesystem, total, used, available, %, mountpoint
        stats = line.split()

        # If this mountpoint is listed, update it's rrd
        if drive_space_rrd.has_key(stats[5]):
            rrd_data = "N:" + string.join(stats[1:4],":")
            
            # Run rrdtool in as secure a fashion as possible
            rrd_file = rrd_path + os.sep + drives_rrd[stats[5]] + "_space.rrd"
            rrd_cmd = ("rrdtool","update", rrd_file, rrd_data)

            if debug>0: 
                debug_print(rrd_cmd)
                
            pid = os.spawnv( os.P_NOWAIT, rrdtool_path, rrd_cmd)


def read_drive_inodes( drive_inodes_rrd ):
    """
    Read the drive Inode usage from the output of 'df -iP'
    """
    # Run df -iP andgrab its output. Ignore first line of descriptive text
    df_cmd = "%s -iP" % (df_path)
    df = os.popen(df_cmd)
    
    # Discard the banner line
    df.readline()
    
    # Read the rest
    lines = df.readlines()
    df.close()
    
    for line in lines:
        # Strip off \n
        line = line[:-1]
        
        # Split on spaces
        # Filesystem, total, used, available, %, mountpoint
        stats = line.split()

        # If this mountpoint is listed, update it's rrd
        if drive_inodes_rrd.has_key(stats[5]):
            rrd_data = "N:" + string.join(stats[1:4],":")
            
            # Run rrdtool in as secure a fashion as possible
            rrd_file = rrd_path + os.sep + drives_rrd[stats[5]] + "_inodes.rrd"
            rrd_cmd = ("rrdtool","update", rrd_file, rrd_data)

            if debug>0: 
                debug_print(rrd_cmd)
                
            pid = os.spawnv( os.P_NOWAIT, rrdtool_path, rrd_cmd)


        
def read_process_list( process_rrd ):
    """
    Read the running processes from ps and update the rrds
    """
    ps_cmd = "%s -A -o comm --no-headers" % (ps_path)
    ps = os.popen(ps_cmd)
    
    # read everything
    lines = ps.readlines()
    ps.close()
    
    ps_count = {}
    for line in lines:
        # Strip off the \n
        line = line[:-1]
        
        # Add to the ps-count dictionary if not already there
        if ps_count.has_key(line):
            ps_count[line] += 1
        else:
            ps_count[line] = 1
            
    # ps_count now has a count for all the running processes
    # Go through the list of processes to watch
    for key in process_rrd.keys():
        # If there are none running then there won't be a key in ps_count
        if ps_count.has_key(key):
            rrd_data = "N:%d" % (ps_count[key])
        else:
            rrd_data = "N:0"
        
        # Run rrdtool in as secure a fashion as possible
        rrd_file = rrd_path + os.sep + process_rrd[key] + ".rrd"
        rrd_cmd = ("rrdtool","update", rrd_file, rrd_data)

        if debug>0: 
            debug_print(rrd_cmd)
            
        pid = os.spawnv( os.P_NOWAIT, rrdtool_path, rrd_cmd)


def read_external():
    """
    Read the values from the external applications and insert the data into
    their rrd files.
    """
    for key in external_rrd.keys():
        try:
            # Run the external application and grab its first line
            output = os.popen( external_rrd[key][2] ).readline().strip()
            rrd_data = "N:%s" % (output)
        except:
            # If there is a problem, just write a 0
            rrd_data = "N:0"
            print "ERROR: Problem running %s" % (external_rrd[key][2])
   
        # Run rrdtool in as secure a fashion as possible
        rrd_file = rrd_path + os.sep + external_rrd[key][1] + ".rrd"
        rrd_cmd = ("rrdtool","update", rrd_file, rrd_data)

        if debug>0: 
            debug_print(rrd_cmd)

        pid = os.spawnv( os.P_NOWAIT, rrdtool_path, rrd_cmd)


def read_upsc( upsc_rrd ):
    """
    Read the values from upsc and insert them into a rrdfile
    """
    try:
        upsc_cmd = "%s %s" % (upsc_path, upsc_host)
        upsc = os.popen(upsc_cmd)
    
        # read everything
        lines = upsc.readlines()
        upsc.close()
    except:
        raise

    upsc_values = {}
    for line in lines:
        line = line.strip()
        (k,v) = line.split(':')
	upsc_values[k] = v

    rrd_data = "N:" + ":".join([str(upsc_values.get(f[0],'U')) for f in upsc_fields])

    # Run rrdtool in as secure a fashion as possible
    rrd_file = rrd_path + os.sep + upsc_rrd + ".rrd"
    rrd_cmd = ("rrdtool","update", rrd_file, rrd_data)

    if debug>0: 
        debug_print(rrd_cmd)
        
    pid = os.spawnv( os.P_NOWAIT, rrdtool_path, rrd_cmd)





def graph_interfaces( interfaces_rrd ):
    """
    Create .png graph of each of the interfaces
    """
    
    # Create graphs for 24 hours, 1 week, 1 month and 1 year
    for time in rrd_time:
        starttime = "%s" % (time)
        endtime = "now"
        for iface in interfaces_rrd.keys():
            rrd_file = rrd_path + os.sep + interfaces_rrd[iface] + ".rrd"
            png_file = png_path + os.sep + interfaces_rrd[iface] + time + ".png"

            in_print = " GPRINT:in_bits:MIN:\"%-8s %%8.2lf%%s \"" % (iface + " in")
            out_print = " GPRINT:out_bits:MIN:\"%-8s %%8.2lf%%s \"" % (iface + " out")
            width_str = "%d" % (width)
            height_str = "%d" % (height)

            rrd_cmd = ( rrdtool_path, " graph ", png_file, " --imgformat PNG",
                        " --start '", starttime, 
                        "' --end '", endtime, "'",
                        " --width ", width_str,
                        " --height ", height_str,
                        " DEF:in_bytes=", rrd_file, ":rx_bytes:AVERAGE",
                        " DEF:out_bytes=", rrd_file, ":tx_bytes:AVERAGE",
                        " CDEF:in_bits=in_bytes,8,*",
                        " CDEF:out_bits=out_bytes,8,*",
                        " AREA:in_bits#00FF00:'Input bits/s'",
                        " LINE1:out_bits#0000FF:'Output bits/s\\c'",
                        " COMMENT:\"               Min          Max          Avg          Last\\n\"",
                        in_print,
                        " GPRINT:in_bits:MAX:\" %8.2lf%s \"",
                        " GPRINT:in_bits:AVERAGE:\" %8.2lf%s \"",
                        " GPRINT:in_bits:LAST:\" %8.2lf%s \\n\"",
                        out_print,
                        " GPRINT:out_bits:MAX:\" %8.2lf%s \"",
                        " GPRINT:out_bits:AVERAGE:\" %8.2lf%s \"",
                        " GPRINT:out_bits:LAST:\" %8.2lf%s \\n\"",
                        " COMMENT:\"Last Updated ", ctime().replace(":","\:"), "\\c\""
                      )


            if debug>0: 
                debug_print(rrd_cmd)
                
            rrd_string = ""
            for i in rrd_cmd:
                rrd_string = rrd_string + i

            if debug>0: 
                debug_print(rrd_string)
                
            
            output = os.popen( rrd_string ).readlines()


def graph_loadavg( loadavg_rrd ):
    """
    Create .png graphs of the system load
    """

    # Create graphs for 24 hours, 1 week, 1 month and 1 year
    for time in ( rrd_time ):
        starttime = "%s" % (time)
        endtime = "now"
        rrd_file = rrd_path + os.sep + loadavg_rrd + ".rrd"
        png_file = png_path + os.sep + loadavg_rrd + time + ".png"
        width_str = "%d" % (width)
        height_str = "%d" % (height)


        rrd_cmd = ( rrdtool_path, " graph ", png_file, " --imgformat PNG",
                    " --start '", starttime, 
                    "' --end '", endtime, "' ",
                    " --width ", width_str, 
                    " --height ", height_str, 
                    " DEF:load1=", rrd_file, ":load_1:AVERAGE",
                    " DEF:load5=", rrd_file, ":load_5:AVERAGE",
                    " DEF:load15=", rrd_file, ":load_15:AVERAGE",
                    " AREA:load1#00FF00:'1 Min.'",
                    " LINE1:load5#0000FF:'5 Min.'",
                    " LINE1:load15#FF0000:'15 Min.\\c'",
                    " COMMENT:\"              Min          Max           Avg         Last\\n\"",
                    " GPRINT:load1:MIN:\"1 Min.   %8.2lf  \"",
                    " GPRINT:load1:MAX:\" %8.2lf  \"",
                    " GPRINT:load1:AVERAGE:\" %8.2lf  \"",
                    " GPRINT:load1:LAST:\" %8.2lf  \\n\"",
                    " GPRINT:load5:MIN:\"5 Min.   %8.2lf  \"",
                    " GPRINT:load5:MAX:\" %8.2lf  \"",
                    " GPRINT:load5:AVERAGE:\" %8.2lf  \"",
                    " GPRINT:load5:LAST:\" %8.2lf  \\n\"",
                    " GPRINT:load15:MIN:\"15 Min.  %8.2lf  \"",
                    " GPRINT:load15:MAX:\" %8.2lf  \"",
                    " GPRINT:load15:AVERAGE:\" %8.2lf  \"",
                    " GPRINT:load15:LAST:\" %8.2lf  \\n\"",
                    " COMMENT:\"Last Updated ", ctime().replace(":","\:"), " \\c\""
                 ) 

        if debug>0: 
            debug_print(rrd_cmd)
            
        rrd_string = ""
        for i in rrd_cmd:
            rrd_string = rrd_string + i
        
        output = os.popen( rrd_string ).readlines()
    

def graph_uptime( uptime_rrd ):
    """
    Create .png graphs of uptime
    """

    # Create graphs for 24 hours, 1 week, 1 month and 1 year
    for time in rrd_time:
        starttime = "%s" % (time)
        endtime = "now"
        rrd_file = rrd_path + os.sep + uptime_rrd + ".rrd"
        png_file = png_path + os.sep + uptime_rrd + time + ".png"
        width_str = "%d" % (width)
        height_str = "%d" % (height)

        rrd_cmd = ( rrdtool_path, " graph ", png_file, " --imgformat PNG",
                    " --start '", starttime, 
                    "' --end '", endtime, "' ",
                    " --width ", width_str, 
                    " --height ", height_str, 
                    " DEF:uptime=", rrd_file, ":uptime:AVERAGE",
                    " DEF:idletime=", rrd_file, ":idletime:AVERAGE",
                    " AREA:uptime#00FF00:'uptime'",
                    " LINE2:idletime#0000FF:'idletime\\c'",
                    " COMMENT:\"                 Min          Max          Avg          Last\\n\"",
                    " GPRINT:uptime:MIN:\"uptime     %8.2lf%s \"",
                    " GPRINT:uptime:MAX:\" %8.2lf%s \"",
                    " GPRINT:uptime:AVERAGE:\" %8.2lf%s \"",
                    " GPRINT:uptime:LAST:\" %8.2lf%s \\n\"",
                    " GPRINT:idletime:MIN:\"idletime   %8.2lf%s \"",
                    " GPRINT:idletime:MAX:\" %8.2lf%s \"",
                    " GPRINT:idletime:AVERAGE:\" %8.2lf%s \"",
                    " GPRINT:idletime:LAST:\" %8.2lf%s \\n\"",
                    " COMMENT:\"Last Updated ", ctime().replace(":","\:"), " \\c\""
                 ) 

        if debug>0: 
            debug_print(rrd_cmd)
            
        rrd_string = ""
        for i in rrd_cmd:
            rrd_string = rrd_string + i
        
        output = os.popen( rrd_string ).readlines()
    

def graph_meminfo( meminfo_rrd ):
    """
    Create .png graphs of memory usage
    """
    for time in rrd_time:
        starttime = "%s" % (time)
        endtime = "now"
        rrd_file = rrd_path + os.sep + meminfo_rrd + ".rrd"
        png_file = png_path + os.sep + meminfo_rrd + time + ".png"
        width_str = "%d" % (width)
        height_str = "%d" % (height)

        rrd_cmd = ( rrdtool_path, " graph ", png_file, " --imgformat PNG",
                    " --start '", starttime, 
                    "' --end '", endtime, "' ",
                    " --width ", width_str, 
                    " --height ", height_str, 
                    " DEF:MemFreeB=", rrd_file, ":MemFree:AVERAGE",
                    " DEF:SwapFreeB=",rrd_file, ":SwapFree:AVERAGE",
                    " CDEF:MemFreeM=MemFreeB,1024,*",
                    " CDEF:SwapFreeM=SwapFreeB,1024,*",
                    " AREA:MemFreeM#00FF00:'Available Memory'",
                    " LINE2:SwapFreeM#0000FF:'Available Swap\\c'",
                    " COMMENT:\"               Min          Max          Avg          Last\\n\"",
                    " GPRINT:MemFreeM:MIN:\"MemFree  %8.2lf%s \"",
                    " GPRINT:MemFreeM:MAX:\" %8.2lf%s \"",
                    " GPRINT:MemFreeM:AVERAGE:\" %8.2lf%s \"",
                    " GPRINT:MemFreeM:LAST:\" %8.2lf%s \\n\"",
                    " GPRINT:SwapFreeM:MIN:\"SwapFree %8.2lf%s \"",
                    " GPRINT:SwapFreeM:MAX:\" %8.2lf%s \"",
                    " GPRINT:SwapFreeM:AVERAGE:\" %8.2lf%s \"",
                    " GPRINT:SwapFreeM:LAST:\" %8.2lf%s \\n\"",
                    " COMMENT:\"Last Updated ", ctime().replace(":","\:"), "\\c\""
                 ) 

        rrd_string = ""
        for i in rrd_cmd:
            rrd_string = rrd_string + i

        if debug>0: 
            debug_print(rrd_string)

        output = os.popen( rrd_string ).readlines()


    

def graph_drive_space( drives_rrd ):
    """
    Create .png graphs of each drive space usage
    """
    for key in drives_rrd.keys():
        for time in rrd_time :
            starttime = "%s" % (time)
            endtime = "now"
            rrd_file = rrd_path + os.sep + drives_rrd[key] + "_space.rrd"
            png_file = png_path + os.sep + drives_rrd[key] + "_space" + time + ".png"

            drive_print = " GPRINT:AvailableM:MIN:\"%-15s %%6.2lf%%s \"" % (key)
            width_str = "%d" % (width)
            height_str = "%d" % (height)

            rrd_cmd = ( rrdtool_path, " graph ", png_file, " --imgformat PNG",
                        " --start '", starttime, 
                        "' --end '", endtime, "' ",
                        " --width ", width_str, 
                        " --height ", height_str, 
                        " DEF:Available=", rrd_file, ":Available:AVERAGE",
                        " CDEF:AvailableM=Available,1024,*",
                        " AREA:AvailableM#00FF00:'Available Space\\c'",
                        " COMMENT:\"                    Min        Max        Avg        Last\\n\"",
                        drive_print,
                        " GPRINT:AvailableM:MAX:\" %6.2lf%s \"",
                        " GPRINT:AvailableM:AVERAGE:\" %6.2lf%s \"",
                        " GPRINT:AvailableM:LAST:\" %6.2lf%s \\n\"",
                        " COMMENT:\"Last Updated ", ctime().replace(":","\:"), "\\c\""
                     ) 

            rrd_string = ""
            for i in rrd_cmd:
                rrd_string = rrd_string + i

            if debug>0: 
                debug_print(rrd_string)

            output = os.popen( rrd_string ).readlines()


def graph_drive_inodes( drives_rrd ):
    """
    Create .png graphs of each drive's inode usage
    """

    for key in drives_rrd.keys():
        for time in rrd_time:
            starttime = "%s" % (time)
            endtime = "now"
            rrd_file = rrd_path + os.sep + drives_rrd[key] + "_inodes.rrd"
            png_file = png_path + os.sep + drives_rrd[key] + "_inodes" + time + ".png"

            drive_print = " GPRINT:IFree:MIN:\"%-15s %%6.2lf%%s \"" % (key)
            width_str = "%d" % (width)
            height_str = "%d" % (height)

            rrd_cmd = ( rrdtool_path, " graph ", png_file, " --imgformat PNG",
                        " --start '", starttime, 
                        "' --end '", endtime, "' ",
                        " --width ", width_str, 
                        " --height ", height_str, 
                        " DEF:IFree=", rrd_file, ":IFree:AVERAGE",
                        " AREA:IFree#00FF00:'Free Inodes\\c'",
                        " COMMENT:\"                   Min        Max        Avg        Last\\n\"",
                        drive_print,
                        " GPRINT:IFree:MAX:\" %6.2lf%s \"",
                        " GPRINT:IFree:AVERAGE:\" %6.2lf%s \"",
                        " GPRINT:IFree:LAST:\" %6.2lf%s \\n\"",
                        " COMMENT:\"Last Updated ", ctime().replace(":","\:"), "\\c\""
                     ) 

            rrd_string = ""
            for i in rrd_cmd:
                rrd_string = rrd_string + i

            if debug>0: 
                debug_print(rrd_string)

            output = os.popen( rrd_string ).readlines()
    
    
def graph_process_list( process_rrd ):
    """
    Create .png graphs of the processes being monitored
    """
    for key in process_rrd.keys():
        for time in rrd_time:
            starttime = "%s" % (time)
            endtime = "now"
            rrd_file = rrd_path + os.sep + process_rrd[key] + ".rrd"
            png_file = png_path + os.sep + process_rrd[key] + time + ".png"

            proc_print = " GPRINT:running:MIN:\"%-15s %%6.2lf%%s \"" % (key)
            width_str = "%d" % (width)
            height_str = "%d" % (height)

            rrd_cmd = ( rrdtool_path, " graph ", png_file, " --imgformat PNG",
                        " --start '", starttime, 
                        "' --end '", endtime, "' ",
                        " --width ", width_str, 
                        " --height ", height_str, 
                        " DEF:running=", rrd_file, ":running:AVERAGE",
                        " LINE2:running#0000FF:'",key,"\\c'",
                        " COMMENT:\"                   Min        Max        Avg        Last\\n\"",
                        proc_print,
                        " GPRINT:running:MAX:\" %6.2lf%s \"",
                        " GPRINT:running:AVERAGE:\" %6.2lf%s \"",
                        " GPRINT:running:LAST:\" %6.2lf%s \\n\"",
                        " COMMENT:\"Last Updated ", ctime().replace(":","\:"), "\\c\""
                     ) 

            rrd_string = ""
            for i in rrd_cmd:
                rrd_string = rrd_string + i

            if debug>0: 
                debug_print(rrd_string)

            output = os.popen( rrd_string ).readlines()

def graph_upsc( upsc_rrd ):
    """
    Graph the UPS stats
    """
    upsc_graph.sort()
    for k in upsc_graph:
        for t in rrd_time:
            starttime = "%s" % (t)
            endtime = "now"
            rrd_file = rrd_path + os.sep + upsc_rrd + ".rrd"
            png_file = os.path.join(png_path,"upsc_%s%s.png" % (k,t))

            name_width = len(k)
            width_str = "%d" % (width)
            height_str = "%d" % (height)

            rrd_cmd = [ rrdtool_path, " graph ", png_file, " --imgformat PNG",
                        " --start '", starttime, 
                        "' --end '", endtime, "' ",
                        " --width ", width_str, 
                        " --height ", height_str, 
                        " DEF:value=%s:%s:AVERAGE" % (rrd_file,k),
                        " LINE2:value#0000FF:'%s\\c'" % (k),
                        " COMMENT:\""+" "*name_width+"      Min          Max           Avg         Last\\n\"",
                        " GPRINT:value:MIN:\"%s %%8.2lf%%s \"" % (k),
                        " GPRINT:value:MAX:\" %8.2lf%s \"",
                        " GPRINT:value:AVERAGE:\" %8.2lf%s \"",
                        " GPRINT:value:LAST:\" %8.2lf%s \\n\"",
                        " COMMENT:\"Last Updated ", ctime().replace(":","\:"), "\\c\""
                     ]

            rrd_string = ""
            for i in rrd_cmd:
                rrd_string = rrd_string + i

            if debug>0: 
                debug_print(rrd_string)

            output = os.popen( rrd_string ).readlines()


def graph_external():
    """
    Graph the external applications
    """
    for key in external_rrd.keys():
        for time in rrd_time:
            starttime = "%s" % (time)
            endtime = "now"
            rrd_file = rrd_path + os.sep + external_rrd[key][1] + ".rrd"
            png_file = png_path + os.sep + external_rrd[key][1] + time + ".png"

            name_width = len(external_rrd[key][0])
            ext_print = " GPRINT:value:MIN:\"%s %%8.2lf%%s \"" % (external_rrd[key][0])
            width_str = "%d" % (width)
            height_str = "%d" % (height)

            rrd_cmd = ( rrdtool_path, " graph ", png_file, " --imgformat PNG",
                        " --start '", starttime, 
                        "' --end '", endtime, "' ",
                        " --width ", width_str, 
                        " --height ", height_str, 
                        " DEF:value=", rrd_file, ":value:AVERAGE",
                        " LINE2:value#0000FF:'",external_rrd[key][0],"\\c'",
                        " COMMENT:\""+" "*name_width+"      Min          Max           Avg         Last\\n\"",
                        ext_print,
                        " GPRINT:value:MAX:\" %8.2lf%s \"",
                        " GPRINT:value:AVERAGE:\" %8.2lf%s \"",
                        " GPRINT:value:LAST:\" %8.2lf%s \\n\"",
                        " COMMENT:\"Last Updated ", ctime().replace(":","\:"), "\\c\""
                     ) 

            rrd_string = ""
            for i in rrd_cmd:
                rrd_string = rrd_string + i

            if debug>0: 
                debug_print(rrd_string)

            output = os.popen( rrd_string ).readlines()
        


# ========================================================================
# Main code execution begins here
# ========================================================================        

# Check for running as root, exit and complain if so
if os.getuid() == 0:
    sys.stderr.write("Please do not run System Health as root, use an unprivledged user")
    sys.exit(-1)

# Determine the kernel version (some /proc interfaces are different)
# from /proc/version
version = open("/proc/version").readline()
#kernel_rev = float(re.search(r'(\d+\.\d+)\.\d+-', version).group(1))
kernel_rev = float(re.search(r'version (\d+\.\d+)\.\d+', version).group(1))
if (kernel_rev > 2.6) or (kernel_rev < 2.4):
    sys.stderr.write("Sorry, kernel v%0.1f is not supported\n" % kernel_rev)
    sys.exit(-1)


# Process command line arguments
opts, args = getopt( sys.argv[1:], "", ["log","graph","setup","check","new","html","add", "debug"])

if not opts:
    usage()
    sys.exit(-1)
    
for i,value in opts:
    command[i] = value

if command.has_key('--debug'):
    debug = 1

config = ConfigParser.ConfigParser()
    
# Setup a new monitor
if command.has_key('--setup'):
    setup_monitor()

# Read the config file (new if --setup was run)
if not os.path.isfile( config_file ):
    print "ERROR: Configuration file (%s) not found." % (config_file)
    print "ERROR: Do you need to run --setup?"
    sys.exit(-1)
config.read( config_file )

width        = int(config.get("graphs", "width"))
height       = int(config.get("graphs", "height"))

rrdtool_path = config.get("paths","rrdtool")
df_path      = config.get("paths","df")
ps_path      = config.get("paths","ps")
rrd_path     = config.get("paths","rrd_path")
png_path     = config.get("paths","png_path")

meminfo_rrd  = config.get("paths","meminfo_rrd")
loadavg_rrd  = config.get("paths","loadavg_rrd")
uptime_rrd   = config.get("paths","uptime_rrd")

try:
    upsc_path = config.get("paths","upsc")
except ConfigParser.NoOptionError:
    config.set("paths","upsc", upsc_paths[0])
    upsc_path = upsc_paths[0]

try:
    upsc_rrd     = config.get("paths","upsc_rrd")
except ConfigParser.NoOptionError:
    config.set("paths", "upsc_rrd", "upsc" )
    upsc_rrd     = config.get("paths","upsc_rrd")


# Add an external command
if command.has_key('--add'):
    add_external()

# Get the interfaces
interfaces_rrd = {}
ifaces = config.options("interfaces")
for i in ifaces:
    interfaces_rrd[i] = config.get("interfaces",i)

# Get the drives
drives_rrd = {}
drives = config.options("drives")
for d in drives:
    drives_rrd[d] = config.get("drives",d)

# Get the processes
process_rrd = {}
processes = config.options("processes")
for p in processes:
    process_rrd[p] = config.get("processes",p)

# Get the external commands
external_rrd = {}
try:
    external = config.options("external")
    for e in external:
        external_rrd[e] = pickle.loads(config.get("external",e))
except:
    pass

# Add new processes
if command.has_key('--new'):
    new_processes(processes)

# Create HTML pages after all the info has been reloaded from config
if command.has_key('--setup') or command.has_key("--html"):
    create_html()

# Check for missing rrd files
if command.has_key('--check'):
    check_files()

# Check to make sure all the rrd files are available
startup_ok = 1
for file in [ df_path, ps_path, rrdtool_path ]:
    if not os.path.isfile( file ):
        sys.stderr.write("ERROR: Missing system binary - %s\n" % (file))
        startup_ok = 0
        
if not os.path.isdir(rrd_path):
    sys.stderr.write("ERROR: RRD log directory is missing - %s\n" (rrd_path))
    sys.exit(-1)
    
# Make a list of the rrd files
rrd_files = [ loadavg_rrd + ".rrd", meminfo_rrd + ".rrd", uptime_rrd + ".rrd" ]
for key in interfaces_rrd.keys():
    rrd_files.append( interfaces_rrd[key] + ".rrd" )
    
for key in process_rrd.keys():
    rrd_files.append( process_rrd[key] + ".rrd" )
    
for key in drives_rrd.keys():
    rrd_files.append( drives_rrd[key] + "_space.rrd" )
    rrd_files.append( drives_rrd[key] + "_inodes.rrd" )

# Check for the rrd files
for file in rrd_files:
    if not os.path.isfile( rrd_path + os.sep + file):
        sys.stderr.write("ERROR: Missing rrd file - %s\n" % (rrd_path + os.sep + file))
        startup_ok = 0

if not os.path.isdir(png_path):
    sys.stderr.write("ERROR: png image directory is missing - %s\n" (png_path))
    startup_ok = 0
    
# If there were any errors, don't start        
if not startup_ok:
    sys.exit(-1)


if command.has_key('--log'):
    # Update the interface statistics
    read_interfaces( interfaces_rrd )
    read_loadavg( loadavg_rrd )
    read_uptime( uptime_rrd )
    read_meminfo( meminfo_rrd )
    read_drive_space( drives_rrd )
    read_drive_inodes( drives_rrd )
    read_process_list( process_rrd )
    read_upsc( upsc_rrd )
    read_external()
    
if command.has_key('--graph'):
    graph_interfaces( interfaces_rrd )
    graph_loadavg( loadavg_rrd )
    graph_uptime( uptime_rrd )
    graph_meminfo( meminfo_rrd )
    graph_drive_space( drives_rrd )
    graph_drive_inodes( drives_rrd )
    graph_process_list( process_rrd )
    graph_upsc( upsc_rrd )
    graph_external()
    
