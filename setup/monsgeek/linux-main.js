"use strict";
// Entry point that runs the MonsGeek Driver v4 UI (the Windows Electron app) on a native
// Linux Electron. Installed by setup/monsgeek-driver.sh next to the app's own main.js,
// which it loads unchanged after adapting the three Windows assumptions below.
const { app, session, shell } = require("electron");

const MONSGEEK_VID = 0x3151;

// The UI detects its platform from the user agent and only knows mac/win64/windows;
// on a Linux UA it never leaves the loading screen. Present the Windows x64 UA it ships with.
app.userAgentFallback = app.userAgentFallback.replace(/\(X11; Linux x86_64\)/, "(Windows NT 10.0; Win64; x64)");

// Before connecting, the UI copies its bundled iot_driver.exe to userData and launches it with
// shell.openPath. On Linux the native iot_driver service (monsgeek-akko-linux) already serves
// 127.0.0.1:3814, so report that launch as successful without running anything
// (resources/app/iot_driver.exe is an empty placeholder that only satisfies the copy).
const openPath = shell.openPath.bind(shell);
shell.openPath = (path) => (/iot_driver[^/\\]*\.exe$/i.test(path) ? Promise.resolve("") : openPath(path));

// WebHID fallback: Electron denies navigator.hid unless the main process grants it.
// Only MonsGeek devices are granted.
app.on("ready", () => {
  const ses = session.defaultSession;

  ses.on("select-hid-device", (event, details, callback) => {
    event.preventDefault();
    const device = (details.deviceList || []).find((d) => d.vendorId === MONSGEEK_VID);
    callback(device ? device.deviceId : "");
  });

  // Electron's default when no handler is set is to grant every check; keep that, HID included.
  ses.setPermissionCheckHandler(() => true);

  ses.setDevicePermissionHandler((details) => details.deviceType === "hid" && details.device.vendorId === MONSGEEK_VID);
});

require("./main.js");
