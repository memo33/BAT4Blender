# BAT4Blender

## Installing the Add-on

The general gist of it is as follows.
1. download the `source` folder.
2. rename the folder to BAT4Blender and zip it (the files inside the zip should end up inside a BAT4Blender subfolder).
3. open Blender and go to `Edit` -> `Preferences` -> `Add-ons` -> `Install..`
4. navigate to the zip file created in step 2.
5. select `Install Add-on from File..`.
6. the Add-on is now installed and available in the `Properties` context menu in the `Scene` tab.

Notes
- in Blender, print output is sent to system console, not to the Python console. Go to 'Window' -> 'Toggle System Console' to open it.

### Prerequisites

- Blender 3.6 or 4.2+
- **ImageMagick** ([Windows](https://imagemagick.org/script/download.php#windows)/[macOS](https://imagemagick.org/script/download.php#macos)/[Linux](https://imagemagick.org/script/download.php#linux))
  is needed for Super-Sampling
- [fshgen](https://github.com/memo33/fshgen/releases)
  for converting render output to SC4Model files (see below)

## Usage

- Render Engine: Choose `Cycles` as Render Engine.

- Super-Sampling (`Properties` -> `Scene` -> `BAT4Blender`):
  Enable this to render images at 2× resolution for sharper results (requires ImageMagick).
  As this means you render 4 times as many pixels,
  you may decrease the Max Samples to 25 % of your previous setting or increase the Noise Threshold (`Properties` -> `Render` -> `Sampling`)
  to keep the rendering time the same.
  Afterwards, the image is down-sampled back to the original 1× resolution, which increases the sharpness of the image.

- Post-Processing (`Properties` -> `Scene` -> `BAT4Blender`):
  Enable this to automatically convert the exported LODs (OBJ files) and rendered images (PNG files) to an SC4Model file (requires fshgen).

- Click "Render all zooms & rotations" to render images and export LODs. They are saved in your current working directory from which Blender was launched.

## Roadmap

- [x] alpha version (camera positioning, LOD creation, rendering of small objects)
- [x] slicing of rendered images if larger than 256 px
- [x] slicing of LODs
- [x] uv-mapping of LODs
- [x] zoom-dependent LODs
- [ ] renderer settings (lighting/shading/materials/…)
- [ ] nightlights
- [ ] darknite settings
- [x] HD rendering
- [x] conversion of LODs to S3D: Using [fshgen](https://github.com/memo33/fshgen/releases):
  ```
  fshgen import -o output.SC4Model --force --with-BAT-models --format Dxt1 --gid 0xffffffff *.obj *.png
  ```
  This is executed automatically if Post-Processing is enabled (see above).
- [x] showing progress while rendering: Go to the Rendering workspace to see the current image. Press ESC to cancel rendering.
- [x] super-sampling (for sharper renderings)
