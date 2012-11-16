#
# common.py
#
# Copyright (C) 2007, 2008 Andrew Resch <andrewresch@gmail.com>
#
# Deluge is free software.
#
# You may redistribute it and/or modify it under the terms of the
# GNU General Public License, as published by the Free Software
# Foundation; either version 3 of the License, or (at your option)
# any later version.
#
# deluge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with deluge.    If not, write to:
#   The Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor
#   Boston, MA  02110-1301, USA.
#
#    In addition, as a special exception, the copyright holders give
#    permission to link the code of portions of this program with the OpenSSL
#    library.
#    You must obey the GNU General Public License in all respects for all of
#    the code used other than OpenSSL. If you modify file(s) with this
#    exception, you may extend this exception to your version of the file(s),
#    but you are not obligated to do so. If you do not wish to do so, delete
#    this exception statement from your version. If you delete this exception
#    statement from all source files in the program, then also delete it here.
#
#


"""Common functions for various parts of Deluge to use."""

import os
import time
import subprocess
import platform
import chardet
import logging

try:
    import json
except ImportError:
    import simplejson as json

log = logging.getLogger(__name__)

# Do a little hack here just in case the user has json-py installed since it
# has a different api
if not hasattr(json, "dumps"):
    json.dumps = json.write
    json.loads = json.read

    def dump(obj, fp, **kw):
        fp.write(json.dumps(obj))

    def load(fp, **kw):
        return json.loads(fp.read())

    json.dump = dump
    json.load = load

import pkg_resources
import gettext
import locale
import sys

from deluge.error import *

LT_TORRENT_STATE = {
    "Queued": 0,
    "Checking": 1,
    "Downloading Metadata": 2,
    "Downloading": 3,
    "Finished": 4,
    "Seeding": 5,
    "Allocating": 6,
    "Checking Resume Data": 7,
    0: "Queued",
    1: "Checking",
    2: "Downloading Metadata",
    3: "Downloading",
    4: "Finished",
    5: "Seeding",
    6: "Allocating",
    7: "Checking Resume Data"
}


TORRENT_STATE = [
    "Allocating",
    "Checking",
    "Downloading",
    "Seeding",
    "Paused",
    "Error",
    "Queued"
]

FILE_PRIORITY = {
    0: "Do Not Download",
    1: "Normal Priority",
    2: "High Priority",
    3: "High Priority",
    4: "High Priority",
    5: "High Priority",
    6: "High Priority",
    7: "Highest Priority",
    "Do Not Download": 0,
    "Normal Priority": 1,
    "High Priority": 5,
    "Highest Priority": 7
}

def get_version():
    """
    Returns the program version from the egg metadata

    :returns: the version of Deluge
    :rtype: string

    """
    return pkg_resources.require("Deluge")[0].version

def get_default_config_dir(filename=None):
    """
    :param filename: if None, only the config path is returned, if provided, a path including the filename will be returned
    :type filename: string
    :returns: a file path to the config directory and optional filename
    :rtype: string

    """
    if windows_check():
        if filename:
            return os.path.join(os.environ.get("APPDATA"), "deluge", filename)
        else:
            return os.path.join(os.environ.get("APPDATA"), "deluge")
    else:
        import xdg.BaseDirectory
        if filename:
            return os.path.join(xdg.BaseDirectory.save_config_path("deluge"), filename)
        else:
            return xdg.BaseDirectory.save_config_path("deluge")

def get_default_download_dir():
    """
    :returns: the default download directory
    :rtype: string

    """
    if windows_check():
        return os.path.join(os.path.expanduser("~"), 'Downloads')
    else:
        from xdg.BaseDirectory import xdg_config_home
        userdir_file = os.path.join(xdg_config_home, 'user-dirs.dirs')
        try:
            for line in open(userdir_file, 'r'):
                if not line.startswith('#') and 'XDG_DOWNLOAD_DIR' in line:
                        download_dir = os.path.expandvars(\
                                        line.partition("=")[2].rstrip().strip('"'))
                        if os.path.isdir(download_dir):
                            return download_dir
        except IOError:
            pass

        return os.environ.get("HOME")

def windows_check():
    """
    Checks if the current platform is Windows

    :returns: True or False
    :rtype: bool

    """
    return platform.system() in ('Windows', 'Microsoft')

def vista_check():
    """
    Checks if the current platform is Windows Vista

    :returns: True or False
    :rtype: bool

    """
    return platform.release() == "Vista"

def osx_check():
    """
    Checks if the current platform is Mac OS X

    :returns: True or False
    :rtype: bool

    """
    return platform.system() == "Darwin"

def get_pixmap(fname):
    """
    Provides easy access to files in the deluge/ui/data/pixmaps folder within the Deluge egg

    :param fname: the filename to look for
    :type fname: string
    :returns: a path to a pixmap file included with Deluge
    :rtype: string

    """
    return resource_filename("deluge", os.path.join("ui", "data", "pixmaps", fname))

def resource_filename(module, path):
    # While developing, if there's a second deluge package, installed globally
    # and another in develop mode somewhere else, while pkg_resources.require("Deluge")
    # returns the proper deluge instance, pkg_resources.resource_filename does
    # not, it returns the first found on the python path, which is not good
    # enough.
    # This is a work-around that.
    return pkg_resources.require("Deluge>=%s" % get_version())[0].get_resource_filename(
        pkg_resources._manager, os.path.join(*(module.split('.')+[path]))
    )

def open_file(path):
    """
    Opens a file or folder using the system configured program

    :param path: the path to the file or folder to open
    :type path: string

    """
    if windows_check():
        os.startfile("%s" % path)
    elif osx_check():
        subprocess.Popen(["open", "%s" % path])
    else:
        subprocess.Popen(["xdg-open", "%s" % path])

def open_url_in_browser(url):
    """
    Opens a url in the desktop's default browser

    :param url: the url to open
    :type url: string

    """
    import webbrowser
    webbrowser.open(url)

## Formatting text functions

def fsize(fsize_b):
    """
    Formats the bytes value into a string with KiB, MiB or GiB units

    :param fsize_b: the filesize in bytes
    :type fsize_b: int
    :returns: formatted string in KiB, MiB or GiB units
    :rtype: string

    **Usage**

    >>> fsize(112245)
    '109.6 KiB'

    """
    fsize_kb = fsize_b / 1024.0
    if fsize_kb < 1024:
        return "%.1f %s" % (fsize_kb, _("KiB"))
    fsize_mb = fsize_kb / 1024.0
    if fsize_mb < 1024:
        return "%.1f %s" % (fsize_mb, _("MiB"))
    fsize_gb = fsize_mb / 1024.0
    return "%.1f %s" % (fsize_gb, _("GiB"))

def fsize_short(fsize_b):
    """
    Formats the bytes value into a string with K, M or G units

    :param fsize_b: the filesize in bytes
    :type fsize_b: int
    :returns: formatted string in K, M or G units
    :rtype: string

    **Usage**

    >>> fsize(112245)
    '109.6 K'

    """
    fsize_kb = fsize_b / 1024.0
    if fsize_kb < 1024:
        return "%.1f %s" % (fsize_kb, _("K"))
    fsize_mb = fsize_kb / 1024.0
    if fsize_mb < 1024:
        return "%.1f %s" % (fsize_mb, _("M"))
    fsize_gb = fsize_mb / 1024.0
    return "%.1f %s" % (fsize_gb, _("G"))

def fpcnt(dec):
    """
    Formats a string to display a percentage with two decimal places

    :param dec: the ratio in the range [0.0, 1.0]
    :type dec: float
    :returns: a formatted string representing a percentage
    :rtype: string

    **Usage**

    >>> fpcnt(0.9311)
    '93.11%'

    """
    return '%.2f%%' % (dec * 100)

def fspeed(bps):
    """
    Formats a string to display a transfer speed utilizing :func:`fsize`

    :param bps: bytes per second
    :type bps: int
    :returns: a formatted string representing transfer speed
    :rtype: string

    **Usage**

    >>> fspeed(43134)
    '42.1 KiB/s'

    """
    fspeed_kb = bps / 1024.0
    if fspeed_kb < 1024:
        return "%.1f %s" % (fspeed_kb, _("KiB/s"))
    fspeed_mb = fspeed_kb / 1024.0
    if fspeed_mb < 1024:
        return "%.1f %s" % (fspeed_mb, _("MiB/s"))
    fspeed_gb = fspeed_mb / 1024.0
    return "%.1f %s" % (fspeed_gb, _("GiB/s"))

def fpeer(num_peers, total_peers):
    """
    Formats a string to show 'num_peers' ('total_peers')

    :param num_peers: the number of connected peers
    :type num_peers: int
    :param total_peers: the total number of peers
    :type total_peers: int
    :returns: a formatted string: num_peers (total_peers), if total_peers < 0, then it will not be shown
    :rtype: string

    **Usage**

    >>> fpeer(10, 20)
    '10 (20)'
    >>> fpeer(10, -1)
    '10'

    """
    if total_peers > -1:
        return "%d (%d)" % (num_peers, total_peers)
    else:
        return "%d" % num_peers

def ftime(seconds):
    """
    Formats a string to show time in a human readable form

    :param seconds: the number of seconds
    :type seconds: int
    :returns: a formatted time string, will return '' if seconds == 0
    :rtype: string

    **Usage**

    >>> ftime(23011)
    '6h 23m'

    """
    if seconds == 0:
        return ""
    if seconds < 60:
        return '%ds' % (seconds)
    minutes = seconds / 60
    if minutes < 60:
        seconds = seconds % 60
        return '%dm %ds' % (minutes, seconds)
    hours = minutes / 60
    if hours < 24:
        minutes = minutes % 60
        return '%dh %dm' % (hours, minutes)
    days = hours / 24
    if days < 7:
        hours = hours % 24
        return '%dd %dh' % (days, hours)
    weeks = days / 7
    if weeks < 52:
        days = days % 7
        return '%dw %dd' % (weeks, days)
    years = weeks / 52
    weeks = weeks % 52
    return '%dy %dw' % (years, weeks)

def fdate(seconds):
    """
    Formats a date time string in the locale's date representation based on the systems timezone

    :param seconds: time in seconds since the Epoch
    :type seconds: float
    :returns: a string in the locale's datetime representation or "" if seconds < 0
    :rtype: string

    """
    if seconds < 0:
        return ""
    return time.strftime("%x %X", time.localtime(seconds))

def is_url(url):
    """
    A simple test to check if the URL is valid

    :param url: the url to test
    :type url: string
    :returns: True or False
    :rtype: bool

    **Usage**

    >>> is_url("http://deluge-torrent.org")
    True

    """
    return url.partition('://')[0] in ("http", "https", "ftp", "udp")

def is_magnet(uri):
    """
    A check to determine if a uri is a valid bittorrent magnet uri

    :param uri: the uri to check
    :type uri: string
    :returns: True or False
    :rtype: bool

    **Usage**

    >>> is_magnet("magnet:?xt=urn:btih:SU5225URMTUEQLDXQWRB2EQWN6KLTYKN")
    True

    """
    if uri[:20] == "magnet:?xt=urn:btih:":
        return True
    return False

def create_magnet_uri(infohash, name=None, trackers=[]):
    """
    Creates a magnet uri

    :param infohash: the info-hash of the torrent
    :type infohash: string
    :param name: the name of the torrent (optional)
    :type name: string
    :param trackers: the trackers to announce to (optional)
    :type trackers: list of strings

    :returns: a magnet uri string
    :rtype: string

    """
    from base64 import b32encode
    uri = "magnet:?xt=urn:btih:" + b32encode(infohash.decode("hex"))
    if name:
        uri = uri + "&dn=" + name
    if trackers:
        for t in trackers:
            uri = uri + "&tr=" + t

    return uri

def get_path_size(path):
    """
    Gets the size in bytes of 'path'

    :param path: the path to check for size
    :type path: string
    :returns: the size in bytes of the path or -1 if the path does not exist
    :rtype: int

    """
    if not os.path.exists(path):
        return -1

    if os.path.isfile(path):
        return os.path.getsize(path)

    dir_size = 0
    for (p, dirs, files) in os.walk(path):
        for file in files:
            filename = os.path.join(p, file)
            dir_size += os.path.getsize(filename)
    return dir_size

def free_space(path):
    """
    Gets the free space available at 'path'

    :param path: the path to check
    :type path: string
    :returns: the free space at path in bytes
    :rtype: int

    :raises InvalidPathError: if the path is not valid

    """
    if not os.path.exists(path):
        raise InvalidPathError("%s is not a valid path" % path)

    if windows_check():
        import win32file
        sectors, bytes, free, total = map(long, win32file.GetDiskFreeSpace(path))
        return (free * sectors * bytes)
    else:
        disk_data = os.statvfs(path.encode("utf8"))
        block_size = disk_data.f_frsize
        return disk_data.f_bavail * block_size

def is_ip(ip):
    """
    A simple test to see if 'ip' is valid

    :param ip: the ip to check
    :type ip: string
    :returns: True or False
    :rtype: bool

    ** Usage **

    >>> is_ip("127.0.0.1")
    True

    """
    import socket
    #first we test ipv4
    try:
        if socket.inet_pton(socket.AF_INET, "%s" % (ip)):
            return True
    except socket.error:
        if not socket.has_ipv6:
            return False
    #now test ipv6
    try:
        if socket.inet_pton(socket.AF_INET6, "%s" % (ip)):
            return True
    except socket.error:
        return False

def path_join(*parts):
    """
    An implementation of os.path.join that always uses / for the separator
    to ensure that the correct paths are produced when working with internal
    paths on Windows.
    """
    path = ''
    for part in parts:
        if not part:
            continue
        elif part[0] == '/':
            path = part
        elif not path:
            path = part
        else:
            path += '/' + part
    return path

XML_ESCAPES = (
    ('&', '&amp;'),
    ('<', '&lt;'),
    ('>', '&gt;'),
    ('"', '&quot;'),
    ("'", '&apos;')
)

def xml_decode(string):
    """
    Unescape a string that was previously encoded for use within xml.

    :param string: The string to escape
    :type string: string
    :returns: The unescaped version of the string.
    :rtype: string
    """
    for char, escape in XML_ESCAPES:
        string = string.replace(escape, char)
    return string

def xml_encode(string):
    """
    Escape a string for use within an xml element or attribute.

    :param string: The string to escape
    :type string: string
    :returns: An escaped version of the string.
    :rtype: string
    """
    for char, escape in XML_ESCAPES:
        string = string.replace(char, escape)
    return string

def decode_string(s, encoding="utf8"):
    """
    Decodes a string and re-encodes it in utf8.  If it cannot decode using
    `:param:encoding` then it will try to detect the string encoding and
    decode it.

    :param s: string to decode
    :type s: string
    :keyword encoding: the encoding to use in the decoding
    :type encoding: string

    """

    try:
        s = s.decode(encoding).encode("utf8", "ignore")
    except UnicodeDecodeError:
        s = s.decode(chardet.detect(s)["encoding"], "ignore").encode("utf8", "ignore")
    return s

def utf8_encoded(s):
    """
    Returns a utf8 encoded string of s

    :param s: (unicode) string to (re-)encode
    :type s: basestring
    :returns: a utf8 encoded string of s
    :rtype: str

    """
    if isinstance(s, str):
        s = decode_string(s)
    elif isinstance(s, unicode):
        s = s.encode("utf8", "ignore")
    return s

class VersionSplit(object):
    """
    Used for comparing version numbers.

    :param ver: the version
    :type ver: string

    """
    def __init__(self, ver):
        ver = ver.lower()
        vs = ver.replace("_", "-").split("-")
        self.version = [int(x) for x in vs[0].split(".")]
        self.suffix = None
        self.dev = False
        if len(vs) > 1:
            if vs[1].startswith(("rc", "alpha", "beta")):
                self.suffix = vs[1]
            if vs[-1] == 'dev':
                self.dev = True

    def __cmp__(self, ver):
        """
        The comparison method.

        :param ver: the version to compare with
        :type ver: VersionSplit

        """

        # If there is no suffix we use z because we want final
        # to appear after alpha, beta, and rc alphabetically.
        v1 = [self.version, self.suffix or 'z', self.dev]
        v2 = [ver.version, ver.suffix or 'z', ver.dev]
        return cmp(v1, v2)


# Common AUTH stuff
AUTH_LEVEL_NONE = 0
AUTH_LEVEL_READONLY = 1
AUTH_LEVEL_NORMAL = 5
AUTH_LEVEL_ADMIN = 10
AUTH_LEVEL_DEFAULT = AUTH_LEVEL_NORMAL

def create_auth_file():
    import stat, configmanager
    auth_file = configmanager.get_config_dir("auth")
    # Check for auth file and create if necessary
    if not os.path.exists(auth_file):
        fd = open(auth_file, "w")
        fd.flush()
        os.fsync(fd.fileno())
        fd.close()
        # Change the permissions on the file so only this user can read/write it
        os.chmod(auth_file, stat.S_IREAD | stat.S_IWRITE)

def create_localclient_account(append=False):
    import configmanager, random
    auth_file = configmanager.get_config_dir("auth")
    if not os.path.exists(auth_file):
        create_auth_file()

    try:
        from hashlib import sha1 as sha_hash
    except ImportError:
        from sha import new as sha_hash
    fd = open(auth_file, "a" if append else "w")
    fd.write(":".join([
        "localclient",
        sha_hash(str(random.random())).hexdigest(),
        str(AUTH_LEVEL_ADMIN)
    ]) + '\n')
    fd.flush()
    os.fsync(fd.fileno())
    fd.close()


# Initialize gettext
def setup_translations(setup_pygtk=False):
    translations_path = resource_filename("deluge", "i18n")
    log.info("Setting up translations from %s", translations_path)

    try:
        if hasattr(locale, "bindtextdomain"):
            locale.bindtextdomain("deluge", translations_path)
        if hasattr(locale, "textdomain"):
            locale.textdomain("deluge")
        gettext.install("deluge", translations_path, unicode=True)
        if setup_pygtk:
            # Even though we're not using glade anymore, let's set it up so that
            # plugins still using it get properly translated.
            log.info("Setting up GTK translations from %s", translations_path)
            import gtk
            import gtk.glade
            gtk.glade.bindtextdomain("deluge", translations_path)
            gtk.glade.textdomain("deluge")
    except Exception, e:
        log.error("Unable to initialize gettext/locale!")
        log.exception(e)
        import __builtin__
        __builtin__.__dict__["_"] = lambda x: x

def unicode_argv():
    """ Gets sys.argv as list of unicode objects on any platform."""
    if windows_check():
        # Versions 2.x of Python don't support Unicode in sys.argv on
        # Windows, with the underlying Windows API instead replacing multi-byte
        # characters with '?'.
        from ctypes import POINTER, byref, cdll, c_int, windll
        from ctypes.wintypes import LPCWSTR, LPWSTR

        GetCommandLineW = cdll.kernel32.GetCommandLineW
        GetCommandLineW.argtypes = []
        GetCommandLineW.restype = LPCWSTR

        CommandLineToArgvW = windll.shell32.CommandLineToArgvW
        CommandLineToArgvW.argtypes = [LPCWSTR, POINTER(c_int)]
        CommandLineToArgvW.restype = POINTER(LPWSTR)

        cmd = GetCommandLineW()
        argc = c_int(0)
        argv = CommandLineToArgvW(cmd, byref(argc))
        if argc.value > 0:
            # Remove Python executable and commands if present
            start = argc.value - len(sys.argv)
            return [argv[i] for i in
                    xrange(start, argc.value)]
    else:
        # On other platforms, decode the arguments using sys.stdin.encoding
        [arg.decode(sys.stdin.encoding) for arg in sys.argv[1:]]
