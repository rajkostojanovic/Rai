# Building a password-protected Rai release

Run from PowerShell in this folder:

```powershell
.\build_windows.ps1 -Installer
```

The build prompts for a password with hidden input. Choose a new password for
each release if desired. The installer encrypts its bundled files and requests
this password during installation. A missing password stops compilation.
For automated builds, supply `RAI_INSTALLER_PASSWORD` as a private environment
secret. Do not commit passwords or put them in public release notes.

If Inno Setup is missing, add `-InstallInnoSetup`. To repackage an app that has
already been built, use `-Installer -SkipAppBuild`. Only skip the app build when
`dist\Rai` contains the intended version of the application.

Upload the new `.exe` from `installer-dist` as a GitHub Release attachment.
Share its password separately by private email or a private Patreon post.
The executable includes Rai and its runtime; recipients do not need Python.

A new password applies only to the new installer. Older installers retain
their original passwords. Installed applications do not request the password
again. A shared password can be forwarded; this is not individual activation
or subscription enforcement.

These builds are unsigned unless a signing process is added separately.
