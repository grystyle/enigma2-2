from __future__ import print_function
from __future__ import absolute_import
import threading
import urllib.request
import urllib.error
import urllib.parse
import os
import shutil
import tempfile
from json import loads
from enigma import eDVBDB, eEPGCache
from Screens.MessageBox import MessageBox
from Components.config import config
from Tools import Notifications
from base64 import encodebytes
from six.moves.urllib.parse import quote
from time import sleep
import xml.etree.ElementTree as et
import six

settingfiles = ('lamedb', 'bouquets.', 'userbouquet.', 'blacklist', 'whitelist', 'alternatives.')


class ImportChannels():

	def __init__(self):
		if config.usage.remote_fallback_enabled.value and config.usage.remote_fallback_import.value and config.usage.remote_fallback.value and not "ChannelsImport" in [x.name for x in threading.enumerate()]:
			self.header = None
			if config.usage.remote_fallback_enabled.value and config.usage.remote_fallback_import.value and config.usage.remote_fallback_import_url.value != "same" and config.usage.remote_fallback_import_url.value:
				self.url = config.usage.remote_fallback_import_url.value.rsplit(":", 1)[0]
			else:
				self.url = config.usage.remote_fallback.value.rsplit(":", 1)[0]
			if config.usage.remote_fallback_openwebif_customize.value:
				self.url = "%s:%s" % (self.url, config.usage.remote_fallback_openwebif_port.value)
				if config.usage.remote_fallback_openwebif_userid.value and config.usage.remote_fallback_openwebif_password.value:
					self.header = "Basic %s" % encodebytes("%s:%s" % (config.usage.remote_fallback_openwebif_userid.value, config.usage.remote_fallback_openwebif_password.value)).strip()
			self.remote_fallback_import = config.usage.remote_fallback_import.value
			self.thread = threading.Thread(target=self.threaded_function, name="ChannelsImport")
			self.thread.start()

	def getUrl(self, url, timeout=5):
		request = urllib.request.Request(url)
		if self.header:
			request.add_header("Authorization", self.header)
		try:
			result = urllib.request.urlopen(request, timeout=timeout)
		except urllib2.URLError as e:
			if "[Errno -3]" in str(e.reason):
				print("[Import Channels] Network is not up yet, delay 5 seconds")
				# network not up yet
				sleep(5)
				return self.getUrl(url, timeout)
			print("[Import Channels] URLError ", e)
			raise(e)
		return result

	def getTerrestrialUrl(self):
		url = config.usage.remote_fallback_dvb_t.value
		return url[:url.rfind(":")] if url else self.url

	def getFallbackSettings(self):
		return self.getUrl("%s/web/settings" % self.getTerrestrialUrl()).read()

	def getFallbackSettingsValue(self, settings, e2settingname):
		root = et.fromstring(settings)
		for e2setting in root:
			if e2settingname in e2setting[0].text:
				return e2setting[1].text
		return ""

	def getTerrestrialRegion(self, settings):
		description = ""
		descr = self.getFallbackSettingsValue(settings, ".terrestrial")
		if "Europe" in descr:
			description = "fallback DVB-T/T2 Europe"
		if "Australia" in descr:
			description = "fallback DVB-T/T2 Australia"
		config.usage.remote_fallback_dvbt_region.value = description

	def threaded_function(self):
		settings = self.getFallbackSettings()
		self.getTerrestrialRegion(settings)
		self.tmp_dir = tempfile.mkdtemp(prefix="ImportChannels")
		if "epg" in self.remote_fallback_import:
			print( "[Import Channels] Writing epg.dat file on sever box")
			try:
				self.getUrl("%s/web/saveepg" % self.url, timeout=30).read()
			except:
				self.ImportChannelsDone(False, _("Error when writing epg.dat on server"))
				return
			print("[Import Channels] Get EPG Location")
			try:
				epgdatfile = self.getFallbackSettingsValue(settings, "config.misc.epgcache_filename") or "/hdd/epg.dat"
				try:
					files = [_file for _file in loads(self.getUrl("%s/file?dir=%s" % (self.url, os.path.dirname(epgdatfile))).read())["files"] if os.path.basename(_file).startswith(os.path.basename(epgdatfile))]
				except:
					files = [_file for _file in loads(self.getUrl("%s/file?dir=/" % self.url).read())["files"] if os.path.basename(_file).startswith("epg.dat")]
				epg_location = files[0] if files else None
			except:
				self.ImportChannelsDone(False, _("Error while retreiving location of epg.dat on server"))
				return
			if epg_location:
				print("[Import Channels] Copy EPG file...")
				try:
					open(os.path.join(self.tmp_dir, "epg.dat"), "wb").write(self.getUrl("%s/file?file=%s" % (self.url, epg_location)).read())
					shutil.move(os.path.join(self.tmp_dir, "epg.dat"), config.misc.epgcache_filename.value)
				except:
					self.ImportChannelsDone(False, _("Error while retreiving epg.dat from server"))
					return
			else:
				self.ImportChannelsDone(False, _("No epg.dat file found server"))
		if "channels" in self.remote_fallback_import:
			print("[Import Channels] reading dir")
			try:
				files = [_file for _file in loads(self.getUrl("%s/file?dir=/etc/enigma2" % self.url).read())["files"] if os.path.basename(_file).startswith(settingfiles)]
				for _file in files:
					_file = six.ensure_str(_file)
					print("[Import Channels] Downloading %s" % _file)
					try:
						open(os.path.join(self.tmp_dir, os.path.basename(_file)), "wb").write(self.getUrl("%s/file?file=%s" % (self.url, _file)).read())
					except:
						self.ImportChannelsDone(False, _("ERROR downloading file %s") % _file)
						return
			except:
				self.ImportChannelsDone(False, _("Error %s") % self.url)
				return

			print("[Import Channels] Removing files...")
			files = [_file for _file in os.listdir("/etc/enigma2") if _file.startswith(settingfiles)]
			for _file in files:
				os.remove("/etc/enigma2/%s" % _file)
			print("[Import Channels] copying files...")
			files = [x for x in os.listdir("/tmp/tmp") if x.startswith(settingfiles)]
			for _file in files:
				shutil.move(os.path.join(self.tmp_dir, _file), os.path.join("/etc/enigma2", _file))
		self.ImportChannelsDone(True, {"channels": _("Channels"), "epg": _("EPG"), "channels_epg": _("Channels and EPG")}[self.remote_fallback_import])

	def ImportChannelsDone(self, flag, message=None):
		shutil.rmtree(self.tmp_dir, True)
		if flag:
			Notifications.AddNotificationWithID("ChannelsImportOK", MessageBox, _("%s imported from fallback tuner") % message, type=MessageBox.TYPE_INFO, timeout=5)
		else:
			Notifications.AddNotificationWithID("ChannelsImportNOK", MessageBox, _("Import from fallback tuner failed, %s") % message, type=MessageBox.TYPE_ERROR, timeout=5)
