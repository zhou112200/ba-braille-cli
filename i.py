#!/usr/bin/env python3
import sys
import subprocess
import argparse
from pathlib import Path
import math

def rgb_to_ansi256(r, g, b):
    """Convert RGB color to 256-color index"""
    if r == g == b:
        # Grayscale processing
        if r < 8:
            return 16
        if r > 248:
            return 231
        return round((r - 8) / 247 * 24) + 232
    else:
        # Color processing - improved conversion algorithm
        r = max(0, min(5, round(r / 51.0)))
        g = max(0, min(5, round(g / 51.0)))
        b = max(0, min(5, round(b / 51.0)))
        return 16 + 36 * r + 6 * g + b

def ansi256_fg(color_index):
    """Return 256-color foreground escape sequence"""
    return f"\033[38;5;{color_index}m"

def ansi256_bg(color_index):
    """Return 256-color background escape sequence"""
    return f"\033[48;5;{color_index}m"

def ansi_reset():
    """Return ANSI reset escape sequence"""
    return "\033[0m"

def pixel_to_braille(blocks, avg_color):
    """
    Convert 2x4 pixel block to Braille character
    Also receives average color for coloring
    
    Braille dot layout (0-7):
    0 3
    1 4
    2 5
    6 7
    """
    if not blocks:
        return chr(0x2800)  # Empty Braille character
    
    braille_code = 0
    positions = [0, 3, 1, 4, 2, 5, 6, 7]
    
    for i, pos in enumerate(positions):
        if i < len(blocks) and blocks[i] is not None:
            try:
                if isinstance(blocks[i], (tuple, list)) and len(blocks[i]) == 3:
                    r, g, b = blocks[i]
                    # Improved brightness calculation considering human eye sensitivity to green
                    brightness = 0.2126 * r + 0.7152 * g + 0.0722 * b
                    if brightness > 128:  # Adaptive threshold
                        braille_code |= 1 << pos  # Fixed: use correct bit position
            except (ValueError, TypeError):
                continue
    
    return chr(0x2800 + braille_code)

def get_image_dimensions(image_path):
    """Get image dimensions"""
    try:
        cmd = ["identify", "-format", "%w %h", str(image_path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            width, height = map(int, result.stdout.strip().split())
            return width, height
    except:
        pass
    return None, None

def display_image_braille(image_path, width=80, use_bg=False, invert=False, dither=False):
    """Display image using Braille characters (each character represents 2x4 pixels)"""
    path = Path(image_path)
    if not path.exists():
        print(f"Error: File does not exist {image_path}")
        return
    
    # Get original dimensions
    orig_width, orig_height = get_image_dimensions(image_path)
    if orig_width and orig_height:
        print(f"Original dimensions: {orig_width}x{orig_height}")
    
    try:
        # Calculate optimal dimensions, maintaining aspect ratio
        pixel_width = width * 2
        
        # Build ImageMagick command
        cmd = ["convert", str(path)]
        
        # Add dither option
        if dither:
            cmd.extend(["-dither", "FloydSteinberg"])
        
        # Optimize scaling parameters
        cmd.extend([
            "-resize", f"{pixel_width}x",
            "-unsharp", "0.5x0.5+0.5+0.008",  # Slight sharpening
            "-colorspace", "RGB",
            "txt:-"
        ])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"ImageMagick error: {result.stderr}")
            return
        
        # Parse pixel data
        pixels = {}
        current_x = 0
        current_y = 0
        max_x = 0
        max_y = 0
        
        for line in result.stdout.split('\n'):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # More efficient parsing
            if ':' in line:
                try:
                    pos_part, color_part = line.split(":", 1)
                    x_str, y_str = pos_part.split(",")
                    x, y = int(x_str), int(y_str)
                    
                    # Update maximum coordinates
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
                    
                    # Extract RGB values - optimized parsing
                    rgb_start = color_part.find("(")
                    rgb_end = color_part.find(")", rgb_start)
                    if rgb_start != -1 and rgb_end != -1:
                        rgb_str = color_part[rgb_start+1:rgb_end]
                        parts = rgb_str.split(",")
                        
                        if len(parts) >= 3:
                            if "%" in parts[0]:
                                r = int(float(parts[0].strip('%')) * 255 / 100)
                                g = int(float(parts[1].strip('%')) * 255 / 100)
                                b = int(float(parts[2].strip('%')) * 255 / 100)
                            else:
                                r = int(parts[0].strip())
                                g = int(parts[1].strip())
                                b = int(parts[2].strip())
                            
                            if invert:
                                r, g, b = 255 - r, 255 - g, 255 - b
                            
                            pixels[(x, y)] = (r, g, b)
                except (ValueError, IndexError) as e:
                    continue
        
        if not pixels:
            print("Error: Unable to parse pixel data")
            return
        
        # Calculate character grid dimensions
        char_width = (max_x + 2) // 2  # Round up
        char_height = (max_y + 4) // 4  # Round up
        
        print(f"Displaying image: {path.name} ({max_x+1}x{max_y+1}) - Using Braille characters")
        print(f"Character dimensions: {char_width}x{char_height}")
        print("=" * min(80, char_width))
        
        # Pre-calculate color conversion
        color_cache = {}
        
        # Display image using Braille characters
        for char_y in range(char_height):
            line_chars = []
            line_colors = []
            
            for char_x in range(char_width):
                # Collect 2x4 pixel block
                blocks = []
                block_colors = []
                
                for py in range(4):
                    for px in range(2):
                        pixel_x = char_x * 2 + px
                        pixel_y = char_y * 4 + py
                        
                        if (pixel_x, pixel_y) in pixels:
                            color = pixels[(pixel_x, pixel_y)]
                            blocks.append(color)
                            block_colors.append(color)
                        else:
                            blocks.append(None)
                
                # Calculate average color for this block
                valid_colors = [c for c in block_colors if c is not None]
                
                if valid_colors:
                    # Calculate weighted average color
                    total_r = total_g = total_b = 0
                    for r, g, b in valid_colors:
                        total_r += r
                        total_g += g
                        total_b += b
                    
                    avg_r = total_r // len(valid_colors)
                    avg_g = total_g // len(valid_colors)
                    avg_b = total_b // len(valid_colors)
                    
                    # Cache color conversion result
                    color_key = (avg_r, avg_g, avg_b)
                    if color_key not in color_cache:
                        color_cache[color_key] = rgb_to_ansi256(avg_r, avg_g, avg_b)
                    
                    color_index = color_cache[color_key]
                    
                    # Generate Braille character
                    braille_char = pixel_to_braille(blocks, (avg_r, avg_g, avg_b))
                    
                    # Store character and color
                    line_chars.append(braille_char)
                    line_colors.append(color_index)
                else:
                    # Empty area
                    line_chars.append(" ")
                    line_colors.append(None)
            
            # Build output line, optimize use of color escape sequences
            output_line = ""
            last_color = None
            for char, color_idx in zip(line_chars, line_colors):
                if color_idx is not None:
                    if use_bg:
                        if last_color != color_idx:
                            output_line += ansi256_bg(color_idx)
                            last_color = color_idx
                    else:
                        if last_color != color_idx:
                            output_line += ansi256_fg(color_idx)
                            last_color = color_idx
                    output_line += char
                else:
                    if last_color is not None:
                        output_line += ansi_reset()
                        last_color = None
                    output_line += char
            
            # Reset color at end of line
            if last_color is not None:
                output_line += ansi_reset()
            
            print(output_line)
        
        print("=" * min(80, char_width))
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(
        description="Display images in terminal (Braille character version) - High resolution optimized",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s image.jpg -w 100      # Display with 100 character width
  %(prog)s image.png -b -i       # Background color mode, invert colors
  %(prog)s image.gif -d          # Use dithering for better quality
  %(prog)s --test                # Test 256-color support
        """
    )
    
    parser.add_argument("image", nargs="?", help="Image file path")
    parser.add_argument("-w", "--width", type=int, default=80, 
                       help="Display width (in characters, default 80)")
    parser.add_argument("-b", "--bg", action="store_true", 
                       help="Use background color mode (clearer but may flicker)")
    parser.add_argument("-i", "--invert", action="store_true", 
                       help="Invert colors")
    parser.add_argument("-d", "--dither", action="store_true",
                       help="Use Floyd-Steinberg dithering for better color quality")
    parser.add_argument("-t", "--test", action="store_true", 
                       help="Test 256-color support")
    
    args = parser.parse_args()
    
    if args.test:
        # Enhanced 256-color test
        print("256-color Terminal Support Test")
        print("=" * 60)
        
        print("\n1. System colors (0-15):")
        for i in range(8):
            print(f"\033[48;5;{i}m   \033[0m", end="")
        print()
        for i in range(8, 16):
            print(f"\033[48;5;{i}m   \033[0m", end="")
        print()
        
        print("\n2. 216-color cube (16-231):")
        print("R-axis → , G-axis ↓ , B-axis changes per line")
        for g in range(6):
            for r in range(6):
                line = ""
                for b in range(6):
                    code = 16 + 36 * r + 6 * g + b
                    line += f"\033[48;5;{code}m  \033[0m"
                print(f"R{r}G{g}: {line}")
        
        print("\n3. Grayscale gradient (232-255):")
        grayscale = ""
        for i in range(232, 256):
            grayscale += f"\033[48;5;{i}m  \033[0m"
        print(grayscale)
        
        print("\n4. Braille character test:")
        for i in range(0x2800, 0x2820):
            print(chr(i), end=" " if (i - 0x2800) % 16 != 15 else "\n")
        
        print("\n5. Color accuracy test:")
        test_colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
        ]
        for r, g, b in test_colors:
            idx = rgb_to_ansi256(r, g, b)
            print(f"\033[48;5;{idx}m RGB({r:3d},{g:3d},{b:3d}) → {idx:3d} \033[0m")
        
    elif args.image:
        display_image_braille(args.image, args.width, args.bg, args.invert, args.dither)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
