from Screen import Screen
from Components.ActionMap import NumberActionMap
from Components.config import config, ConfigNothing, ConfigText, ConfigPassword
from Components.Label import Label
from Components.SystemInfo import SystemInfo
from Components.ConfigList import ConfigListScreen
from Components.Pixmap import Pixmap
from Components.Sources.StaticText import StaticText
from Components.Sources.Boolean import Boolean
from enigma import eEnv

import xml.etree.cElementTree

# FIXME: use resolveFile!
# read the setupmenu
try:
	# first we search in the current path
	setupfile = file('data/setup.xml', 'r')
except:
	# if not found in the current path, we use the global datadir-path
	setupfile = file(eEnv.resolve('${datadir}/enigma2/setup.xml'), 'r')
setupdom = xml.etree.cElementTree.parse(setupfile)
setupfile.close()


def getConfigMenuItem(configElement):
	for item in setupdom.getroot().findall('./setup/item/.'):
		if item.text == configElement:
			return _(item.attrib["text"]), eval(configElement)
	return "", None


class SetupError(Exception):
	def __init__(self, message):
		self.msg = message

	def __str__(self):
		return self.msg


class SetupSummary(Screen):

	def __init__(self, session, parent):
		Screen.__init__(self, session, parent=parent)
		self["SetupTitle"] = StaticText(parent.getTitle())
		self["SetupEntry"] = StaticText("")
		self["SetupValue"] = StaticText("")
		if hasattr(self.parent, "onChangedEntry"):
			self.onShow.append(self.addWatcher)
			self.onHide.append(self.removeWatcher)

	def addWatcher(self):
		if hasattr(self.parent, "onChangedEntry"):
			self.parent.onChangedEntry.append(self.selectionChanged)
			self.parent["config"].onSelectionChanged.append(self.selectionChanged)
			self.selectionChanged()

	def removeWatcher(self):
		if hasattr(self.parent, "onChangedEntry"):
			self.parent.onChangedEntry.remove(self.selectionChanged)
			self.parent["config"].onSelectionChanged.remove(self.selectionChanged)

	def selectionChanged(self):
		self["SetupEntry"].text = self.parent.getCurrentEntry()
		self["SetupValue"].text = self.parent.getCurrentValue()
		if hasattr(self.parent, "getCurrentDescription") and "description" in self.parent:
			self.parent["description"].text = self.parent.getCurrentDescription()


class Setup(ConfigListScreen, Screen):

	ALLOW_SUSPEND = True

	def removeNotifier(self):
		self.onNotifiers.remove(self.levelChanged)

	def levelChanged(self, configElement):
		list = []
		self.refill(list)
		self["config"].setList(list)

	def refill(self, list):
		xmldata = setupdom.getroot()
		for x in xmldata.findall("setup"):
			if x.get("key") != self.setup:
				continue
			self.addItems(list, x)
			self.setup_title = x.get("title", "").encode("UTF-8")
			self.seperation = int(x.get('separation', '0'))

	def __init__(self, session, setup):
		Screen.__init__(self, session)
		# for the skin: first try a setup_<setupID>, then Setup
		self.skinName = ["setup_" + setup, "Setup"]
		self.item = None
		self.onChangedEntry = []
		self.setup = setup
		self.setup_title = ''
		list = []
		self.onNotifiers = []
		self.refill(list)
		ConfigListScreen.__init__(self, list, session=session, on_change=self.changedEntry)
		self.createSetup()

		#check for list.entries > 0 else self.close
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("OK"))
		self["description"] = Label("")
		self["HelpWindow"] = Pixmap()
		self["HelpWindow"].hide()
		self["VKeyIcon"] = Boolean(False)

		self["actions"] = NumberActionMap(["SetupActions", "MenuActions"],
			{
				"cancel": self.keyCancel,
				"save": self.keySave,
				"menu": self.closeRecursive,
			}, -2)

		self.changedEntry()
		self.setTitle(_(self.setup_title))

	def createSetup(self):
		list = []
		self.refill(list)
		self["config"].setList(list)
		if config.usage.sort_settings.value:
			self["config"].list.sort()
		self.moveToItem(self.item)

	def getIndexFromItem(self, item):
		if item is not None:
			for x in range(len(self["config"].list)):
				if self["config"].list[x][0] == item[0]:
					return x
		return None

	def moveToItem(self, item):
		newIdx = self.getIndexFromItem(item)
		if newIdx is None:
			newIdx = 0
		self["config"].setCurrentIndex(newIdx)

	# for summary:
	def changedEntry(self):
		self.item = self["config"].getCurrent()
		try:
			if isinstance(self["config"].getCurrent()[1], ConfigYesNo) or isinstance(self["config"].getCurrent()[1], ConfigSelection):
				self.createSetup()
		except:
			pass

	def addItems(self, list, parentNode):
		for x in parentNode:
			if not x.tag:
				continue
			if x.tag == 'item':
				item_level = int(x.get("level", 0))

				if not self.onNotifiers:
					self.onNotifiers.append(self.levelChanged)
					self.onClose.append(self.removeNotifier)

				if item_level > config.usage.setup_level.index:
					continue

				requires = x.get("requires")
				if requires:
					if requires[0] == '!':
						if SystemInfo.get(requires[1:], False):
							continue
					elif not SystemInfo.get(requires, False):
						continue
				conditional = x.get("conditional")
				if conditional and not eval(conditional):
					continue

				item_text = _(x.get("text", "??").encode("UTF-8"))
				item_description = _(x.get("description", " ").encode("UTF-8")) # don't change
				b = eval(x.text or "")
				if b == "":
					continue
				#add to configlist
				item = b
				# the first b is the item itself, ignored by the configList.
				# the second one is converted to string.
				if not isinstance(item, ConfigNothing):
					list.append((item_text, item, item_description))

	def run(self):
		self.keySave()


def getSetupTitle(id):
	xmldata = setupdom.getroot()
	for x in xmldata.findall("setup"):
		if x.get("key") == id:
			return x.get("title", "").encode("UTF-8")
	raise SetupError("unknown setup id '%s'!" % repr(id))


def getSetupTitleLevel(id):
	try:
		xmldata = setupdom().getroot()
		for x in xmldata.findall("setup"):
			if x.get("key") == id:
				return int(x.get("level", 0))
		raise SetupError("unknown setup level id '%s'!" % repr(id))
		return 0
	except:
		pass
