# App icon

Back to the [README](../README.md).

One source image drives every icon: `frontend/brand/app-icon-source.png`.
To change it, run:

```bash
python scripts/generate_icons.py path/to/new-icon.png
```

The script replaces the source image and regenerates every icon:

| File | Use |
|---|---|
| `frontend/app/favicon.ico`, `frontend/app/icon.png` | Browser tab, from a tight crop of the ball |
| `frontend/app/apple-icon.png` | iPhone home screen (180 px, full-bleed; iOS rounds the corners) |
| `frontend/public/icons/icon-192.png`, `icon-512.png`, `icon-maskable-512.png` | Install / Android, listed in `frontend/app/manifest.ts` |
| `frontend/public/icons/logo-mark.png` | The logo in the app header |

The crop boxes are at the top of the script. Check the contact sheet it
writes to `frontend/brand/icon-preview.png` before you commit. Pillow is
required (`python -m pip install pillow`).
