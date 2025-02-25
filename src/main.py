import os
import subprocess
import argparse
import tkinter as tk
from decompiler_advanced import DecompilerApp, download_cfr, CFR_JAR_PATH

def check_java():
    """Check if Java is installed"""
    try:
        subprocess.run(['java', '-version'], capture_output=True)
        return True
    except:
        print("Error: Java is not installed or not in PATH")
        return False

def check_dependencies():
    """Check and download dependencies"""
    if not os.path.exists(CFR_JAR_PATH):
        download_cfr()

def show_about():
    """Show information about the decompiler"""
    print("-" * 50)
    print("Java Decompiler and Disassembler")
    print("Inspired by JD-GUI (https://java-decompiler.github.io/)")
    print("Uses CFR decompiler (https://www.benf.org/other/cfr/)")
    print("-" * 50)
    print("Features:")
    print("- Decompile Java bytecode to Java source code")
    print("- Disassemble Java bytecode")
    print("- Debug view with breakpoints")
    print("- Simple bytecode execution simulation")
    print("-" * 50)

def main():
    parser = argparse.ArgumentParser(description='Java Decompiler and Disassembler')
    parser.add_argument('file', nargs='?', help='Java class file to decompile')
    parser.add_argument('--about', action='store_true', help='Show information about the decompiler')
    args = parser.parse_args()

    if args.about:
        show_about()
        return

    if not check_java():
        return

    check_dependencies()

    if args.file:
        # CLI mode - decompile specified file
        class_file = args.file
        if not os.path.exists(class_file):
            print(f"Error: File {class_file} not found")
            return
        
        if not class_file.endswith('.class'):
            print("Error: Only .class files are supported")
            return
            
        print(f"Decompiling {class_file}...")
        
        # Decompile
        from decompiler_advanced import decompile_class, disassemble_class
        decompiled = decompile_class(class_file)
        disassembled = disassemble_class(class_file)
        print("Decompiled code:")
        print(decompiled)
        print("Disassembled code:")
        print(disassembled)
    else:
        # GUI mode
        root = tk.Tk()
        app = DecompilerApp(root)
        root.mainloop()

if __name__ == "__main__":
    main()
