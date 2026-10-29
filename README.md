# Rai

Rai is a Windows desktop application for live visual performance. Work with
images, backgrounds, and object states, respond to audio, and send your visuals
to a separate display or projector.

## Features

- Image objects with editable transforms and opacity.
- Two background image slots, A and B, with a manual crossfade.
- Image preparation with **Apply** and **Cancel**, so you can prepare a
  replacement while the current scene continues.
- Image replacement that preserves the current scene's transforms and states.
- Audio input from microphones and supported system-audio loopback sources.
- Beat sensitivity and visual transition controls.
- A separate projector output without editor controls or overlays.

## Download and install

1. Open this repository's **Releases** section.
2. Download the `Rai-Setup-….exe` attachment for the release you want.
3. Run the installer and enter the password shared privately for that release.
4. Complete installation, then launch **Rai** from the Start menu. You can also
   choose to create a desktop shortcut during installation.

The installer includes the application and its runtime. You do not need to
install Python separately. The current build targets 64-bit Windows.

### Installer password

The installer is encrypted and requires a shared release password. The password
is distributed separately through private email or Patreon; it is not included
on the public download page.

Use the password supplied for the specific installer you downloaded. A new
release may use a different password. Changing a release password does not
change older installers or affect copies already installed. Rai does not ask
for the installer password when you launch it.

### Windows warning

The current installer is unsigned, so Windows may display an unrecognized-app
warning. Verify that the file came from the intended release before running it.

## Getting started

1. Use the **Object** and **Background** controls to prepare your scene.
2. When replacing an image, review the preparation preview and select **Apply**.
3. Adjust object states, transforms, opacity, and the background A/B crossfade.
4. For audio response, open **Audio**, choose an **Audio Source**, select
   **Enable Audio**, and adjust **Beat Sensitivity**.
5. For external output, connect your display, select it under **Display**, and
   choose **Open Projector**. Use **Refresh Displays** if needed.

The dashed rectangle in the editor marks the projector region. It covers the
center half of the canvas width and height. That region fills the output
display; a different display aspect ratio may stretch the image.

## Running from source

From the project folder in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

The current packaged release was built with Python 3.14 and PySide6. Runtime
dependencies are listed in [requirements.txt](requirements.txt).

## Building an installer

```powershell
.\build_windows.ps1 -Installer
```

The build prompts for the release password. See [INSTALLER.md](INSTALLER.md)
for compiler setup, rebuilding, and release instructions. Keep passwords out
of the repository and public release attachments.

## Feedback

When reporting a problem, include the Rai version, your Windows version, the
steps to reproduce it, and any relevant audio device or display details.
Do not include your installer password in a public issue.
