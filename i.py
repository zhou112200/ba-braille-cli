#!/usr/bin/env python3
import sys
import subprocess
import argparse
from pathlib import Path
import math

def rgb_to_ansi256(r, g, b):
    """将RGB颜色转换为256色索引"""
    if r == g == b:
        # 灰度处理
        if r < 8:
            return 16
        if r > 248:
            return 231
        return round((r - 8) / 247 * 24) + 232
    else:
        # 彩色处理 - 改进的转换算法
        r = max(0, min(5, round(r / 51.0)))
        g = max(0, min(5, round(g / 51.0)))
        b = max(0, min(5, round(b / 51.0)))
        return 16 + 36 * r + 6 * g + b

def ansi256_fg(color_index):
    """返回256色前景色转义序列"""
    return f"\033[38;5;{color_index}m"

def ansi256_bg(color_index):
    """返回256色背景色转义序列"""
    return f"\033[48;5;{color_index}m"

def ansi_reset():
    """返回ANSI重置转义序列"""
    return "\033[0m"

def pixel_to_braille(blocks, avg_color):
    """
    将2x4像素块转换为Braille字符
    同时接收平均颜色用于着色
    
    Braille点阵布局 (0-7):
    0 3
    1 4
    2 5
    6 7
    """
    if not blocks:
        return chr(0x2800)  # 空白Braille字符
    
    braille_code = 0
    positions = [0, 3, 1, 4, 2, 5, 6, 7]
    
    for i, pos in enumerate(positions):
        if i < len(blocks) and blocks[i] is not None:
            try:
                if isinstance(blocks[i], (tuple, list)) and len(blocks[i]) == 3:
                    r, g, b = blocks[i]
                    # 改进的亮度计算，考虑人眼对绿色的敏感性
                    brightness = 0.2126 * r + 0.7152 * g + 0.0722 * b
                    if brightness > 128:  # 自适应阈值
                        braille_code |= 1 << pos  # 修正：使用正确的位位置
            except (ValueError, TypeError):
                continue
    
    return chr(0x2800 + braille_code)

def get_image_dimensions(image_path):
    """获取图片尺寸"""
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
    """使用Braille字符显示图片（每个字符代表2x4像素）"""
    path = Path(image_path)
    if not path.exists():
        print(f"错误: 文件不存在 {image_path}")
        return
    
    # 获取原始尺寸
    orig_width, orig_height = get_image_dimensions(image_path)
    if orig_width and orig_height:
        print(f"原始尺寸: {orig_width}x{orig_height}")
    
    try:
        # 计算最佳尺寸，保持宽高比
        pixel_width = width * 2
        
        # 构建ImageMagick命令
        cmd = ["convert", str(path)]
        
        # 添加抖动选项
        if dither:
            cmd.extend(["-dither", "FloydSteinberg"])
        
        # 优化缩放参数
        cmd.extend([
            "-resize", f"{pixel_width}x",
            "-unsharp", "0.5x0.5+0.5+0.008",  # 轻微锐化
            "-colorspace", "RGB",
            "txt:-"
        ])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"ImageMagick错误: {result.stderr}")
            return
        
        # 解析像素数据
        pixels = {}
        current_x = 0
        current_y = 0
        max_x = 0
        max_y = 0
        
        for line in result.stdout.split('\n'):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # 更高效的解析
            if ':' in line:
                try:
                    pos_part, color_part = line.split(":", 1)
                    x_str, y_str = pos_part.split(",")
                    x, y = int(x_str), int(y_str)
                    
                    # 更新最大坐标
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
                    
                    # 提取RGB值 - 优化解析
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
            print("错误: 无法解析像素数据")
            return
        
        # 计算字符网格尺寸
        char_width = (max_x + 2) // 2  # 向上取整
        char_height = (max_y + 4) // 4  # 向上取整
        
        print(f"显示图片: {path.name} ({max_x+1}x{max_y+1}) - 使用Braille字符")
        print(f"字符尺寸: {char_width}x{char_height}")
        print("=" * min(80, char_width))
        
        # 预计算颜色转换
        color_cache = {}
        
        # 显示图片，使用Braille字符
        for char_y in range(char_height):
            line_chars = []
            line_colors = []
            
            for char_x in range(char_width):
                # 收集2x4像素块
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
                
                # 计算该块的平均颜色
                valid_colors = [c for c in block_colors if c is not None]
                
                if valid_colors:
                    # 计算加权平均颜色
                    total_r = total_g = total_b = 0
                    for r, g, b in valid_colors:
                        total_r += r
                        total_g += g
                        total_b += b
                    
                    avg_r = total_r // len(valid_colors)
                    avg_g = total_g // len(valid_colors)
                    avg_b = total_b // len(valid_colors)
                    
                    # 缓存颜色转换结果
                    color_key = (avg_r, avg_g, avg_b)
                    if color_key not in color_cache:
                        color_cache[color_key] = rgb_to_ansi256(avg_r, avg_g, avg_b)
                    
                    color_index = color_cache[color_key]
                    
                    # 生成Braille字符
                    braille_char = pixel_to_braille(blocks, (avg_r, avg_g, avg_b))
                    
                    # 存储字符和颜色
                    line_chars.append(braille_char)
                    line_colors.append(color_index)
                else:
                    # 空白区域
                    line_chars.append(" ")
                    line_colors.append(None)
            
            # 构建输出行，优化颜色转义序列的使用
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
            
            # 行结束重置颜色
            if last_color is not None:
                output_line += ansi_reset()
            
            print(output_line)
        
        print("=" * min(80, char_width))
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(
        description="在终端显示图片（Braille字符版） - 高分辨率优化版",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s image.jpg -w 100      # 宽度100字符显示
  %(prog)s image.png -b -i       # 背景色模式，反色显示
  %(prog)s image.gif -d          # 使用抖动提高质量
  %(prog)s --test                # 测试256色支持
        """
    )
    
    parser.add_argument("image", nargs="?", help="图片文件路径")
    parser.add_argument("-w", "--width", type=int, default=80, 
                       help="显示宽度（字符数，默认80）")
    parser.add_argument("-b", "--bg", action="store_true", 
                       help="使用背景色模式（更清晰但可能有闪烁）")
    parser.add_argument("-i", "--invert", action="store_true", 
                       help="反色显示")
    parser.add_argument("-d", "--dither", action="store_true",
                       help="使用Floyd-Steinberg抖动提高色彩质量")
    parser.add_argument("-t", "--test", action="store_true", 
                       help="测试256色支持")
    
    args = parser.parse_args()
    
    if args.test:
        # 增强的256色测试
        print("256色终端支持测试")
        print("=" * 60)
        
        print("\n1. 系统颜色 (0-15):")
        for i in range(8):
            print(f"\033[48;5;{i}m   \033[0m", end="")
        print()
        for i in range(8, 16):
            print(f"\033[48;5;{i}m   \033[0m", end="")
        print()
        
        print("\n2. 216色立方 (16-231):")
        print("R轴 → , G轴 ↓ , B轴 每行变化")
        for g in range(6):
            for r in range(6):
                line = ""
                for b in range(6):
                    code = 16 + 36 * r + 6 * g + b
                    line += f"\033[48;5;{code}m  \033[0m"
                print(f"R{r}G{g}: {line}")
        
        print("\n3. 灰度渐变 (232-255):")
        grayscale = ""
        for i in range(232, 256):
            grayscale += f"\033[48;5;{i}m  \033[0m"
        print(grayscale)
        
        print("\n4. Braille字符测试:")
        for i in range(0x2800, 0x2820):
            print(chr(i), end=" " if (i - 0x2800) % 16 != 15 else "\n")
        
        print("\n5. 颜色精度测试:")
        test_colors = [
            (255, 0, 0),    # 红
            (0, 255, 0),    # 绿
            (0, 0, 255),    # 蓝
            (255, 255, 0),  # 黄
            (255, 0, 255),  # 紫
            (0, 255, 255),  # 青
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