# ba-braille-cli
# Terminal Image Viewer (Braille Edition)

Display images in your terminal using Braille characters with 256 colors.

## Quick Start

### Windows
1. Install Python from [python.org](https://python.org)
2. Install ImageMagick from [imagemagick.org](https://imagemagick.org)
3. Download the script
4. Run: `python i.py image.jpg`

### Linux/macOS
```bash
# Install dependencies
sudo apt install python3 imagemagick  # Ubuntu/Debian
# or: brew install python3 imagemagick  # macOS

# Run the script
python3 i.py image.jpg
```

## Basic Usage

```bash
# Display image
python i.py image.jpg

# Custom width (100 characters)
python i.py photo.jpg -w 100

# Invert colors
python i.py image.png -i

# Test 256-color support
python i.py --test
```

## Features

- Uses Braille characters for high resolution (2×4 pixels per character)
- 256-color support with accurate color mapping
- Multiple display modes: foreground/background, inverted colors, dithering
- Preserves image aspect ratio
- Cross-platform (Windows, Linux, macOS)

## Options

- `-w N` Set display width in characters (default: 80)
- `-b` Use background color mode (clearer)
- `-i` Invert colors
- `-d` Use dithering for better gradients
- `-t` Test terminal color support

## Windows Tips

1. Use **Windows Terminal** (from Microsoft Store)
2. Install ImageMagick and add to PATH
3. Use fonts like Cascadia Code or Consolas
4. For best results, run in PowerShell or Windows Terminal

## Troubleshooting

- **"ImageMagick not found"**: Install ImageMagick and restart terminal
- **Colors don't show**: Run `python i.py --test` to check terminal support
- **Permission denied**: Run as administrator or check Python PATH

## Example

```bash
# High-quality display
python i.py photo.jpg -w 120 -d

# Dark mode (inverted)
python i.py screenshot.png -i

# Background mode for clearer images
python i.py artwork.png -b -w 100
```

## Requirements

- Python 3.6+
- ImageMagick
- Terminal with 256-color support
