# Bundled fonts

Every letter in an Inside Joke GIF is drawn by `inside_joke/render.py` with one of the fonts below. They ship with the repo so output looks the same on macOS, Linux and CI. All 7 families use the SIL Open Font License 1.1. Each license file is in [`LICENSES/`](LICENSES/).

Files were downloaded on 2026-11-24 from the `main` branch of [github.com/google/fonts](https://github.com/google/fonts) and are unmodified. 4 files were renamed to drop the `[axis]` brackets from the filename, which break shell globs and Make; the font data and internal names are untouched.

| Render key | Family and style | File | Bytes | Source path in google/fonts | License |
|---|---|---|---|---|---|
| `impact` | Anton Regular | `Anton-Regular.ttf` | 170,812 | `ofl/anton/Anton-Regular.ttf` | [Anton-OFL.txt](LICENSES/Anton-OFL.txt) |
| `black` | Archivo Black Regular | `ArchivoBlack-Regular.ttf` | 90,988 | `ofl/archivoblack/ArchivoBlack-Regular.ttf` | [ArchivoBlack-OFL.txt](LICENSES/ArchivoBlack-OFL.txt) |
| `bold` | Inter Bold (variable, instance 7) | `Inter-Variable.ttf` | 876,576 | `ofl/inter/Inter[opsz,wght].ttf` | [Inter-OFL.txt](LICENSES/Inter-OFL.txt) |
| `regular` | Inter Regular (variable, instance 4) | `Inter-Variable.ttf` | same file | same file | same |
| `rounded` | Nunito ExtraBold (variable, instance 7) | `Nunito-Variable.ttf` | 276,932 | `ofl/nunito/Nunito[wght].ttf` | [Nunito-OFL.txt](LICENSES/Nunito-OFL.txt) |
| `serif_bold`, `didot` | Playfair Display Bold (variable, instance 4) | `PlayfairDisplay-Variable.ttf` | 300,724 | `ofl/playfairdisplay/PlayfairDisplay[wght].ttf` | [PlayfairDisplay-OFL.txt](LICENSES/PlayfairDisplay-OFL.txt) |
| `serif_italic` | Playfair Display Italic (variable, instance 1) | `PlayfairDisplay-Italic-Variable.ttf` | 278,688 | `ofl/playfairdisplay/PlayfairDisplay-Italic[wght].ttf` | [PlayfairDisplay-OFL.txt](LICENSES/PlayfairDisplay-OFL.txt) |
| `comic` | Comic Neue Bold | `ComicNeue-Bold.ttf` | 55,716 | `ofl/comicneue/ComicNeue-Bold.ttf` | [ComicNeue-OFL.txt](LICENSES/ComicNeue-OFL.txt) |
| `mono` | Courier Prime Bold | `CourierPrime-Bold.ttf` | 72,856 | `ofl/courierprime/CourierPrime-Bold.ttf` | [CourierPrime-OFL.txt](LICENSES/CourierPrime-OFL.txt) |

## Variable fonts

google/fonts ships Inter, Nunito and Playfair Display only as variable fonts. Pillow loads them at the default weight unless told otherwise, and `render.py` calls `ImageFont.truetype(path, size, index=idx)` with no other options.

FreeType reads the high 16 bits of the face index as a 1-based named-instance number. `inside_joke/config.py` sets `index = instance << 16`, so `bold` opens Inter at its Bold instance with no change to `render.py`. `tests/test_render.py` loads every key and asserts the family and style name FreeType reports (for example `("Inter", "Bold")`), so a font update that reorders instances fails CI.

## Fallback

If a bundled file is missing, `config.py` falls back to the matching macOS system font in `/System/Library/Fonts/Supplemental`. The bundled files are the default everywhere.

## Updating a font

1. Download the new file from the same google/fonts path.
2. Replace the file and its OFL text.
3. Run `make test`. If `FontTest` fails, fix the instance number in `config.py`.
4. Update the byte counts in this table and note the change in `CHANGELOG.md`.
