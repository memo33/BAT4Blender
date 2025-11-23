archive:
	rm -rf ./BAT4Blender
	mkdir ./BAT4Blender
	cp -p ./source/*.py ./BAT4Blender/
	mkdir ./BAT4Blender/assets
	cp -p ./source/assets/*.{blend,txt} ./BAT4Blender/assets/
	zip -r "BAT4Blender-0.5.0-$(shell git rev-parse --short HEAD).zip" BAT4Blender
	rm -rf ./BAT4Blender
