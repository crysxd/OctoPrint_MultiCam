# coding=utf-8
from __future__ import absolute_import

import requests

import octoprint.plugin
import octoprint.settings
from octoprint.schema.webcam import RatioEnum, Webcam, WebcamCompatibility
from octoprint.webcams import WebcamNotAbleToTakeSnapshotException, get_webcams


class MultiCamPlugin(octoprint.plugin.StartupPlugin,
                      octoprint.plugin.TemplatePlugin,
                      octoprint.plugin.SettingsPlugin,
                      octoprint.plugin.AssetPlugin,
                      octoprint.plugin.WebcamProviderPlugin,
                      octoprint.plugin.ReloadNeedingPlugin):

    def __init__(self):
        self.streamTimeout = 15
        self.snapshotTimeout = 15
        self.cacheBuster = True
        self.snapshotSslValidation = True
        self.webRtcServers = []

    def get_assets(self):
        return dict(
            js=["js/multicam.js"],
            css=["css/multicam.css"]
        )

    def on_after_startup(self):
        self._logger.info("MultiCam Loaded! (more: %s)" % self._settings.get(["multicam_profiles"]))

    def get_settings_version(self):
        return 3

    def on_settings_migrate(self, target, current=None):
        if current is None or current < self.get_settings_version():
            self._logger.debug("Settings Migration Needed! Resetting to defaults!")
            profiles = self._settings.get(['multicam_profiles'])
            # Migrate to 2
            if current < 2:
                for profile in profiles:
                    profile['snapshot'] = octoprint.settings.settings().get(["webcam","snapshot"])
                    profile['flipH'] = octoprint.settings.settings().get(["webcam","flipH"])
                    profile['flipV'] = octoprint.settings.settings().get(["webcam","flipV"])
                    profile['rotate90'] = octoprint.settings.settings().get(["webcam","rotate90"])
            # Migrate to 3
            if current < 3:
                for profile in profiles:
                    profile['streamRatio'] = octoprint.settings.settings().get(["webcam","streamRatio"])
            # If script migration is up to date we migrate, else we reset to default
            if (self.get_settings_version() == 3):
                self._settings.set(['multicam_profiles'], profiles)
            else:
                # Reset plug settings to defaults.
                self._settings.set(['multicam_profiles'], self.get_settings_defaults()["multicam_profiles"])

    def get_settings_defaults(self):
        return dict(multicam_profiles=[{
            'name':'Default',
            'URL': octoprint.settings.settings().get(["webcam","stream"]),
            'snapshot': octoprint.settings.settings().get(["webcam","snapshot"]),
            'streamRatio': octoprint.settings.settings().get(["webcam","streamRatio"]),
            'flipH':octoprint.settings.settings().get(["webcam","flipH"]),
            'flipV':octoprint.settings.settings().get(["webcam","flipV"]),
            'rotate90':octoprint.settings.settings().get(["webcam","rotate90"]),
            'isButtonEnabled':'true'}])
    
    def get_sorting_key(self, context):
        return None

    def get_template_configs(self):
        webcams = self.get_webcam_configurations()
        
        def webcam_to_template(webcam):
            return dict(type="webcam", template="multicam.jinja2", custom_bindings=True)
    
        settings_templates = [dict(type="settings", template="multicam_settings.jinja2", custom_bindings=True)]
        webcam_templates = list(map(webcam_to_template, list(webcams)))

        return settings_templates + webcam_templates
    
    # ~~ WebcamProviderPlugin API
    
    def get_webcam_configurations(self):
        profiles = enumerate(self._settings.get(['multicam_profiles']))

        def profile_to_webcam(profile):
            flipH = profile.get("flipH", None) or False
            flipV = profile.get("flipV", None) or False
            rotate90 = profile.get("rotate90", None) or False
            snapshot = profile.get("snapshot", None)
            stream = profile.get("URL", None) or ""
            streamRatio = profile.get("streamRatio", None) or "4:3"
            canSnapshot = snapshot != "" and snapshot is not None
            name = profile.get("name", None) or "default"
                               
            return Webcam(
                name="multicam/%s" % name,
                displayName=name,
                flipH=flipH,
                flipV=flipV,
                rotate90=rotate90,
                snapshotDisplay=snapshot,
                canSnapshot=canSnapshot,
                compat=WebcamCompatibility(
                    stream=stream,
                    streamTimeout=self.streamTimeout,
                    streamRatio=streamRatio,
                    cacheBuster=self.cacheBuster,
                    streamWebrtcIceServers=self.webRtcServers,
                    snapshot=snapshot,
                    snapshotTimeout=self.snapshotTimeout,
                    snapshotSslValidation=self.snapshotSslValidation,
                ),
                extras=dict(
                    stream=stream,
                    streamTimeout=self.streamTimeout,
                    streamRatio=streamRatio,
                    cacheBuster=self.cacheBuster,
                ),
            )

        return list(map(profile_to_webcam, profiles))

    def take_webcam_snapshot(self, name):
        webcam = next(webcam for webcam in self.get_webcam_configurations if webcam.name == name)
        if webcam is None:
            raise WebcamNotAbleToTakeSnapshotException(self._webcam_name)

        snapshot_url = webcam.snapshot_url
        can_snapshot = snapshot_url is not None and snapshot_url != "http://" and snapshot_url != ""

        if not can_snapshot:
            raise WebcamNotAbleToTakeSnapshotException(self._webcam_name)

        with self._capture_mutex:
            self._logger.debug(f"Capturing image from {snapshot_url}")
            r = requests.get(
                snapshot_url,
                stream=True,
                timeout=self.snapshotTimeout,
                verify=self.snapshotSslValidation,
            )
            r.raise_for_status()
            return r.iter_content(chunk_size=1024)

    ##~~ Softwareupdate hook
    def get_version(self):
        return self._plugin_version

    def get_update_information(self):
        return dict(
            multicam=dict(
                displayName="MultiCam",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="mikedmor",
                repo="OctoPrint_MultiCam",
                current=self._plugin_version,

                # update method: pip
                pip="https://github.com/mikedmor/OctoPrint_MultiCam/archive/{target_version}.zip"
            )
        )

__plugin_name__ = "MultiCam"
__plugin_pythoncompat__ = ">=2.7,<4"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = MultiCamPlugin()

    global __plugin_helpers__
    __plugin_helpers__ = dict(get_webcam_profiles=__plugin_implementation__.get_webcam_profiles)


    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }



