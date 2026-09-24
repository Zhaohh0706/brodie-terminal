# assets

- `logo.webp`: the $BRODIE V2 artwork at 360 px, used in the top bar.
- `brodie-walk.mp4`: hero video, 480 px H.264 at 24 fps (CRF 33, no audio).
- `walk-poster.webp`: first frame of the video, shown until it starts playing.
- `memes/s/`: hero stickers, 360 px. `memes/g/`: story gallery, 720 px.
  Both are listed in `STICKERS` / `GALLERY` in `index.html` and rotate per visit.

To re-encode the video:

    ffmpeg -i source.mp4 -an -vf fps=24 -c:v libx264 -preset veryslow -crf 33 \
      -pix_fmt yuv420p -movflags +faststart brodie-walk.mp4
