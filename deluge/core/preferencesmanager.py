#
# preferencesmanager.py
#
# Copyright (C) 2008-2010 Andrew Resch <andrewresch@gmail.com>
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
# 	The Free Software Foundation, Inc.,
# 	51 Franklin Street, Fifth Floor
# 	Boston, MA  02110-1301, USA.
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


import os
import logging
import threading
from twisted.internet.task import LoopingCall

from deluge._libtorrent import lt

from deluge.event import *
import deluge.configmanager
import deluge.common
import deluge.component as component

log = logging.getLogger(__name__)

DEFAULT_PREFS = {
    "send_info": False,
    "info_sent": 0.0,
    "daemon_port": 58846,
    "allow_remote": False,
    "compact_allocation": False,
    "download_location": deluge.common.get_default_download_dir(),
    "listen_ports": [6881, 6891],
    "listen_interface": "",
    "copy_torrent_file": False,
    "del_copy_torrent_file": False,
    "torrentfiles_location": deluge.common.get_default_download_dir(),
    "plugins_location": os.path.join(deluge.configmanager.get_config_dir(), "plugins"),
    "prioritize_first_last_pieces": False,
    "sequential_download": False,
    "random_port": True,
    "dht": True,
    "upnp": True,
    "natpmp": True,
    "utpex": True,
    "lsd": True,
    "enc_in_policy": 1,
    "enc_out_policy": 1,
    "enc_level": 2,
    "enc_prefer_rc4": True,
    "connections_limit_per_torrent": -1,
    "unchoke_slots_limit_per_torrent": -1,
    "upload_rate_limit_per_torrent": -1,
    "download_rate_limit_per_torrent": -1,
    "enabled_plugins": [],
    "add_paused": False,
    "queue_new_to_top": False,
    "stop_seed_at_ratio": False,
    "remove_seed_at_ratio": False,
    "stop_seed_ratio": 2.00,
    "auto_managed": True,
    "move_completed": False,
    "move_completed_path": deluge.common.get_default_download_dir(),
    "new_release_check": True,
    "proxies": {
        "peer": {
            "type": 0,
            "hostname": "",
            "username": "",
            "password": "",
            "port": 8080
        },
        "web_seed": {
            "type": 0,
            "hostname": "",
            "username": "",
            "password": "",
            "port": 8080
        },
        "tracker": {
            "type": 0,
            "hostname": "",
            "username": "",
            "password": "",
            "port": 8080
        },
        "dht": {
            "type": 0,
            "hostname": "",
            "username": "",
            "password": "",
            "port": 8080
        },

    },
    "random_outgoing_ports": True,
    "geoip_db_location": "/usr/share/GeoIP/GeoIP.dat",
    "shared": False
}

OLD_PREFS_MAP = {
    # Old migration
    "public": "shared",
    # Migrate libtorrent session_settings to have lt prefix
    "peer_tos": "lt.peer_tos",
    "max_connections_per_second": "lt.connection_speed",
    "ignore_limits_on_local_network": "lt.ignore_limits_on_local_network",
    "share_ratio_limit": "lt.share_ratio_limit",
    "seed_time_ratio_limit": "lt.seed_time_ratio_limit",
    "seed_time_limit": "lt.seed_time_limit", # *60
    "max_active_downloading": "lt.active_downloads",
    "max_active_seeding": "lt.active_seeds",
    "max_active_limit": "lt.active_limit",
    "dont_count_slow_torrents": "lt.dont_count_slow_torrents",
    "rate_limit_ip_overhead": "lt.rate_limit_ip_overhead",
    "cache_size": "lt.cache_size",
    "cache_expiry": "lt.cache_expiry",
    "auto_manage_prefer_seeds": "lt.auto_manage_prefer_seeds",
    "outgoing_ports": "lt.outgoing_ports",
    "max_half_open_connections": "lt.half_open_limit",
    "max_upload_speed": "lt.upload_rate_limit",
    "max_download_speed": "lt.download_rate_limit",
    "max_upload_slots_global": "lt.unchoke_slots_limit",
    "max_connections_global": "lt.connections_limit",
    "max_connections_per_torrent": "connections_limit_per_torrent",
    "max_upload_slots_per_torrent": "unchoke_slots_limit_per_torrent",
    "max_upload_speed_per_torrent": "download_rate_limit_per_torrent",
    "max_download_speed_per_torrent": "upload_rate_limit_per_torrent"
    }

class PreferencesManager(component.Component):
    def __init__(self, default_session_settings):
        component.Component.__init__(self, "PreferencesManager")

        # Add the libtorrent session_settings to our defaults
        defaults = dict(map(lambda key, val: ("lt." + key, val), default_session_settings.iteritems()))
        defaults.update(DEFAULT_PREFS)

        self.config = deluge.configmanager.ConfigManager("core.conf", defaults)
        # Migrate any old settings to their new name
        for key in OLD_PREFS_MAP:
            if key in self.config:
                log.debug("Updating configuration file: Renamed %s to %s" %
                    (key, OLD_PREFS_MAP[key]))
                self.config[OLD_PREFS_MAP[key]] = self.config[key]
                del self.config[key]

    def start(self):
        self.core = component.get("Core")
        self.session = component.get("Core").session
        self.new_release_timer = None

        # Set the initial preferences on start-up
        for key in DEFAULT_PREFS:
            self.do_config_set_func(key, self.config[key])

        self.config.register_change_callback(self._on_config_value_change)

    def stop(self):
        if self.new_release_timer and self.new_release_timer.running:
            self.new_release_timer.stop()

    # Config set functions
    def do_config_set_func(self, key, value):
        log.debug("%s set to %s", key, value)
        on_set_func = getattr(self, "_on_set_" + key.replace(".", "_"), None)
        if on_set_func:
            on_set_func(value)
        elif key.startswith("lt."):
            self.set_session_setting(key[3:], value)

    def set_session_setting(self, key, value):
        settings = self.session.get_settings()
        settings[key] = value
        self.session.set_settings(settings)

    def _on_config_value_change(self, key, value):
        self.do_config_set_func(key, value)
        component.get("EventManager").emit(ConfigValueChangedEvent(key, value))

    # These are pure deluge settings
    def _on_set_torrentfiles_location(self, value):
        if self.config["copy_torrent_file"]:
            try:
                os.makedirs(value)
            except Exception, e:
                log.debug("Unable to make directory: %s", e)

    def _on_set_send_info(self, value):
        """sends anonymous stats home"""
        log.debug("Sending anonymous stats..")
        class Send_Info_Thread(threading.Thread):
            def __init__(self, config):
                self.config = config
                threading.Thread.__init__(self)
            def run(self):
                import time
                now = time.time()
                # check if we've done this within the last week or never
                if (now - self.config["info_sent"]) >= (60 * 60 * 24 * 7):
                    import deluge.common
                    from urllib import quote_plus
                    from urllib2 import urlopen
                    import platform
                    try:
                        url = "http://deluge-torrent.org/stats_get.php?processor=" +\
                              platform.machine() + "&python=" + platform.python_version()\
                              + "&deluge=" + deluge.common.get_version()\
                              + "&os=" + platform.system()\
                              + "&plugins=" + quote_plus(":".join(self.config["enabled_plugins"]))
                        urlopen(url)
                    except IOError, e:
                        log.debug("Network error while trying to send info: %s", e)
                    else:
                        self.config["info_sent"] = now
        if value:
            Send_Info_Thread(self.config).start()

    def _on_set_new_release_check(self, value):
        if value:
            log.debug("Checking for new release..")
            threading.Thread(target=self.core.get_new_release).start()
            if self.new_release_timer and self.new_release_timer.running:
                self.new_release_timer.stop()
                # Set a timer to check for a new release every 3 days
            self.new_release_timer = LoopingCall(
                self._on_set_new_release_check, "new_release_check", True)
            self.new_release_timer.start(72 * 60 * 60, False)
        else:
            if self.new_release_timer and self.new_release_timer.running:
                self.new_release_timer.stop()

    # These are libtorrent settings not part of session_settings
    def _on_set_listen_ports(self, value):
        # Only set the listen ports if random_port is not true
        if self.config["random_port"] is not True:
            log.debug("listen port range set to %s-%s", value[0], value[1])
            self.session.listen_on(
                value[0], value[1], str(self.config["listen_interface"])
            )

    def _on_set_listen_interface(self, value):
        # Call the random_port callback since it'll do what we need
        self._on_set_random_port("random_port", self.config["random_port"])

    def _on_set_random_port(self, value):
        # We need to check if the value has been changed to true and false
        # and then handle accordingly.
        if value:
            import random
            listen_ports = []
            randrange = lambda: random.randrange(49152, 65525)
            listen_ports.append(randrange())
            listen_ports.append(listen_ports[0]+10)
        else:
            listen_ports = self.config["listen_ports"]

        # Set the listen ports
        log.debug("listen port range set to %s-%s", listen_ports[0],
            listen_ports[1])
        self.session.listen_on(
            listen_ports[0], listen_ports[1],
            str(self.config["listen_interface"])
        )

    def _on_set_dht(self, value):
        state_file = deluge.configmanager.get_config_dir("dht.state")
        if value:
            state = None
            try:
                state = lt.bdecode(open(state_file, "rb").read())
            except Exception, e:
                log.warning("Unable to read DHT state file: %s", e)

            try:
                self.session.start_dht(state)
            except Exception, e:
                log.warning("Restoring old DHT state failed: %s", e)
                self.session.start_dht(None)
            self.session.add_dht_router("router.bittorrent.com", 6881)
            self.session.add_dht_router("router.utorrent.com", 6881)
            self.session.add_dht_router("router.bitcomet.com", 6881)
        else:
            self.core.save_dht_state()
            self.session.stop_dht()

    def _on_set_upnp(self, value):
        if value:
            self.session.start_upnp()
        else:
            self.session.stop_upnp()

    def _on_set_natpmp(self, value):
        if value:
            self.session.start_natpmp()
        else:
            self.session.stop_natpmp()

    def _on_set_lsd(self, value):
        if value:
            self.session.start_lsd()
        else:
            self.session.stop_lsd()

    def _on_set_utpex(self, value):
        if value:
            # Note: All libtorrent python bindings to set plugins/extensions need to be disabled
            # due to  GIL issue. https://code.google.com/p/libtorrent/issues/detail?id=369
            #self.session.add_extension(lt.create_ut_pex_plugin)
            pass

    def _on_set_enc_in_policy(self, value):
        self._on_set_encryption("enc_in_policy", value)

    def _on_set_enc_out_policy(self, value):
        self._on_set_encryption("enc_out_policy", value)

    def _on_set_enc_level(self, value):
        self._on_set_encryption("enc_level", value)

    def _on_set_enc_prefer_rc4(self, value):
        self._on_set_encryption("enc_prefer_rc4", value)

    def _on_set_encryption(self, key, value):
        log.debug("encryption value %s set to %s..", key, value)
        pe_settings = lt.pe_settings()
        pe_settings.out_enc_policy = \
            lt.enc_policy(self.config["enc_out_policy"])
        pe_settings.in_enc_policy = lt.enc_policy(self.config["enc_in_policy"])
        pe_settings.allowed_enc_level = lt.enc_level(self.config["enc_level"])
        pe_settings.prefer_rc4 = self.config["enc_prefer_rc4"]
        self.session.set_pe_settings(pe_settings)
        set = self.session.get_pe_settings()
        log.debug("encryption settings:\n\t\t\tout_policy: %s\n\t\t\
        in_policy: %s\n\t\t\tlevel: %s\n\t\t\tprefer_rc4: %s",
            set.out_enc_policy,
            set.in_enc_policy,
            set.allowed_enc_level,
            set.prefer_rc4)

    def _on_set_proxies(self, value):
        for k, v in value.items():
            if v["type"]:
                proxy_settings = lt.proxy_settings()
                proxy_settings.type = lt.proxy_type(v["type"])
                proxy_settings.username = str(v["username"])
                proxy_settings.password = str(v["password"])
                proxy_settings.hostname = str(v["hostname"])
                proxy_settings.port = v["port"]
                log.debug("setting %s proxy settings", k)
                getattr(self.session, "set_%s_proxy" % k)(proxy_settings)

    def _on_set_geoip_db_location(self, value):
        # Load the GeoIP DB for country look-ups if available
        geoip_db = ""
        if os.path.exists(value):
            geoip_db = value
        elif os.path.exists(deluge.common.resource_filename("deluge", os.path.join("data", "GeoIP.dat"))):
            geoip_db = deluge.common.resource_filename(
                "deluge", os.path.join("data", "GeoIP.dat")
            )
        else:
            log.warning("Unable to find GeoIP database file!")

        if geoip_db:
            try:
                self.session.load_country_db(str(geoip_db))
            except Exception, e:
                log.error("Unable to load geoip database!")
                log.exception(e)

    def _on_set_random_outgoing_ports(self, value):
        if value:
            self.set_session_setting("outgoing_ports", (0, 0))
        else:
            self.set_session_setting("outgoing_ports", self.config["lt.outgoing_ports"])

    # There are several libtorrent session_settings that we manipulate before sending to libtorrent
    def _on_set_lt_outgoing_ports(self, value):
        self._on_set_random_outgoing_ports(self.config["random_outgoing_ports"])

    def _on_set_lt_peer_tos(self, value):
        try:
            self.set_session_setting("peer_tos", chr(int(value, 16)))
        except ValueError, e:
            log.debug("Invalid tos byte: %s", e)
            return

    def _on_set_lt_seed_time_limit(self, value):
        # This value is stored in minutes in deluge, but libtorrent wants seconds
        self.set_session_setting("seed_time_limit", int(value * 60))

    def _on_set_lt_upload_rate_limit(self, value):
        # We need to convert Kb/s to B/s
        if value < 0:
            v = -1
        else:
            v = int(value * 1024)

        self.set_session_setting("upload_rate_limit", v)

    def _on_set_lt_download_rate_limit(self, value):
        # We need to convert Kb/s to B/s
        if value < 0:
            v = -1
        else:
            v = int(value * 1024)
        self.set_session_setting("download_rate_limit", v)
