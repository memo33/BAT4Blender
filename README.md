# BAT4Blender

## Installing the Add-on

1. Download the [latest release](https://github.com/memo33/BAT4Blender/releases).
2. Open Blender and go to *Edit → Preferences → Add-ons → Install..* (or *→ "∨" → Install from Disk..*)
3. Navigate to the downloaded ZIP file.
4. Select `Install Add-on from File..`.
5. Optionally configure the Preferences of the Add-on.
6. The Add-on is now installed and available in the `Properties` context menu in the `Scene` tab.

Notes
- in Blender, print output is sent to system console, not to the Python console. Go to *Window → Toggle System Console* to open it.

### Prerequisites

- Blender 3.6 or 4.2+ or 5.0+
- **ImageMagick** ([Windows](https://imagemagick.org/script/download.php#windows)/[macOS](https://imagemagick.org/script/download.php#macos)/[Linux](https://imagemagick.org/script/download.php#linux))
  is needed for Super-Sampling
- [fshgen](https://github.com/memo33/fshgen/releases)
  for converting render output to SC4Model files (see below)

## Usage

The Add-on panel is available under *Properties → Scene → BAT4Blender*.

- Render Engine: Choose `Cycles` as Render Engine (*Properties → Render*).

- Setup: Configure the `World` and `Compositing` setup once. This loads the relevant data from the linked asset library.

- `Day`/`Night` collections: This is an easy way to hide some objects for the day or for the night render.
  - Create collections named `Day` and `Night` (or `Night.001` etc.) and place your objects inside them.
    These collections are enabled/disabled automatically by BAT4Blender when switching between day and night.

- Night lights using Drivers (advanced): As an alternative to the `Day`/`Night` collections, you can customize the night renderings using Drivers:
  - Right click on the `Day | MN | DN` panel and _Copy as New Driver_.
  - Right click on any property that should depend on the day/night state (e.g. _Strength_ of a light source, or _Disable in Render_ button) and _Paste Driver_.
  - Right click the property and _Edit Driver_.
  - Set _Type_ to _Scripted Expression_.
  - Adjust the _Expression_. Examples:
    - `2.5 if night else 10.0` for a Float value
    - `not night` for a Boolean value
    - `1.5 if night == 2 else 2.5 if night == 1 else 10.0` to distinguish between DN, MN and Day
  - Copy the driver to any other property that should use the same expression.

- Super-Sampling (*Properties → Scene → BAT4Blender*):
  Enable this to render images at 2× resolution for sharper results (requires ImageMagick).
  As this means you render 4 times as many pixels,
  you may decrease the Max Samples to 25 % of your previous setting or increase the Noise Threshold (*Properties → Render → Sampling*)
  to keep the rendering time the same.
  Afterwards, the image is down-sampled back to the original 1× resolution, which increases the sharpness of the image.

- Post-Processing (*Properties → Scene → BAT4Blender*):
  Enable this to automatically convert the exported LODs (OBJ files) and rendered images (PNG files) to an SC4Model file (requires fshgen).
  (Currently, the XML file gets generated as a separate file. You need to manually add it to the SC4Model file, using a tool like ilive's Reader.)

- *Preview*: After the preview render result is complete, make sure to select the *Composite* image (instead of *View Layer*) to see the result.
  (Otherwise, e.g. nightlighting might not be visible.)

- Click "Render all zooms & rotations" to render images and export LODs. They are saved in your current working directory from which Blender was launched.

## Roadmap

- [x] alpha version (camera positioning, LOD creation, rendering of small objects)
- [x] slicing of rendered images if larger than 256 px
- [x] slicing of LODs
- [x] uv-mapping of LODs
- [x] zoom-dependent LODs
- [x] renderer settings (lighting/shading/materials/…)
- [x] nightlights
- [x] Day/Night collections
- [x] darknite settings
- [x] HD rendering
- [x] conversion of LODs to S3D: Using [fshgen](https://github.com/memo33/fshgen/releases):
  ```bash
  # Day only
  fshgen import --output model.SC4Model --force --with-BAT-models --format Dxt1 --gid 0xffffffff *.obj *_Day.png

  # Maxis Night and Dark Night
  fshgen import --output model-MN.SC4Model --force --with-BAT-models --format Dxt1 --gid 0xffffffff *.obj *_Day.png *_MN.png
  fshgen import --output model-DN.SC4Model --force --with-BAT-models --format Dxt1 --gid 0xffffffff *.obj *_Day.png *_DN.png

  # Alternatively, append MN/DN textures to existing SC4Model files
  fshgen import --output model-MN.SC4Model --append --format Dxt1 --gid 0xffffffff *_MN.png
  fshgen import --output model-DN.SC4Model --append --format Dxt1 --gid 0xffffffff *_DN.png
  ```
  This is executed automatically if Post-Processing is enabled (see above).
- [x] showing progress while rendering: Go to the Rendering workspace to see the current image. Press ESC to cancel rendering.
- [x] super-sampling (for sharper renderings)
- [x] generate `SC4PLUGINDESC` XML file

## Developer Notes

Bundling a new release:

- copy the files from `source` into a new folder `BAT4Blender`
- restore the latest `BAT4Blender/assets` folder from the previous release
- zip the folder `BAT4Blender` (the files inside the zip should end up inside a BAT4Blender subfolder)
