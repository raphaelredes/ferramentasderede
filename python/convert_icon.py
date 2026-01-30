from PIL import Image
import os

def convert_to_ico(source, target):
    try:
        img = Image.open(source)
        # Save as ICO with multiple sizes for best quality
        img.save(target, format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        print(f"Successfully converted {source} to {target}")
    except Exception as e:
        print(f"Error converting image: {e}")

if __name__ == "__main__":
    # Source: Electron public logo (assuming this is the correct one)
    source_path = "../electron/public/logo.png"
    # Target: Python assets folder
    target_path = "assets/logo_fixed.ico"
    
    convert_to_ico(source_path, target_path)
