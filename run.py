import sys
import os

plugindir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, plugindir)
sys.path.insert(0, os.path.join(plugindir, "lib"))
sys.path.insert(0, os.path.join(plugindir, "plugin"))

from plugin.main import GithubNotifications

if __name__ == "__main__":
    GithubNotifications()