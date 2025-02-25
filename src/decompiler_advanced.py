import os
import subprocess
import tempfile
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk, font
import urllib.request
from tkinter.constants import *
import re
import threading
import time
import ast
from typing import Dict, Set

# Path for storing CFR JAR file
DECOMP_DIR = os.path.dirname(os.path.abspath(__file__))
CFR_JAR_PATH = os.path.join(DECOMP_DIR, "cfr-0.152.jar")

class LineNumberCanvas(tk.Canvas):
    def __init__(self, parent, text_widget, *args, **kwargs):
        tk.Canvas.__init__(self, parent, *args, **kwargs)
        self.text_widget = text_widget
        self.breakpoints = set()
        self.text_widget.bind("<Configure>", self.on_text_changed)
        self.text_widget.bind("<KeyRelease>", self.on_text_changed)
        self.text_widget.bind("<MouseWheel>", self.on_text_changed)
        self.bind("<Button-1>", self.toggle_breakpoint)
        
        # Configure text widget to update on scrolling
        self.text_widget.bind("<<Modified>>", self.on_text_changed)
        
    def toggle_breakpoint(self, event):
        # Get the y coordinate of the click
        y = event.y
        
        # Find the closest line number to the click
        first_line = int(self.text_widget.index("@0,0").split('.')[0])
        last_line = int(self.text_widget.index(f"@0,{self.text_widget.winfo_height()}").split('.')[0])
        
        for line_num in range(first_line, last_line + 1):
            line_info = self.text_widget.dlineinfo(f"{line_num}.0")
            if line_info:  # line_info can be None if the line is not visible
                line_y = line_info[1]  # y-coordinate of the line
                line_height = line_info[3]  # height of the line
                
                # Check if click is on this line
                if line_y <= y <= line_y + line_height:
                    # Toggle breakpoint
                    if line_num in self.breakpoints:
                        self.breakpoints.remove(line_num)
                    else:
                        self.breakpoints.add(line_num)
                    self.redraw()
                    return
        
    def get_breakpoints(self):
        return sorted(list(self.breakpoints))
        
    def on_text_changed(self, event=None):
        self.redraw()
            
    def redraw(self):
        self.delete("all")
        
        # Get the first and last visible line of the text widget
        first_line = int(self.text_widget.index("@0,0").split('.')[0])
        last_line = int(self.text_widget.index(f"@0,{self.text_widget.winfo_height()}").split('.')[0])
        
        # Calculate the width needed for line numbers
        width = int(self.cget("width"))
        
        # Draw each line number
        for line_num in range(first_line, last_line + 1):
            y = self.text_widget.dlineinfo(f"{line_num}.0")
            if y:
                text_x = width - 8
                if line_num in self.breakpoints:
                    # Draw a red circle for breakpoints
                    circle_x = width - 12
                    circle_y = y[1] + y[3]//2
                    radius = 6
                    self.create_oval(circle_x-radius, circle_y-radius, 
                                    circle_x+radius, circle_y+radius, 
                                    fill="red", outline="red")
                
                # Always draw the line number
                self.create_text(text_x, y[1], anchor="ne", text=str(line_num))

def download_cfr():
    """Download CFR decompiler if not already present"""
    if not os.path.exists(CFR_JAR_PATH):
        print("Downloading CFR decompiler...")
        url = "https://www.benf.org/other/cfr/cfr-0.152.jar"
        urllib.request.urlretrieve(url, CFR_JAR_PATH)
        print("CFR decompiler downloaded successfully.")

def disassemble_class(class_file):
    """Disassemble Java class file using javap"""
    result = subprocess.run(['javap', '-c', '-l', '-verbose', class_file], capture_output=True, text=True)
    return result.stdout

def decompile_class(class_file):
    """Decompile Java class file using CFR"""
    try:
        # Ensure CFR is downloaded
        if not os.path.exists(CFR_JAR_PATH):
            download_cfr()
        
        # Run CFR decompiler
        result = subprocess.run(['java', '-jar', CFR_JAR_PATH, class_file], 
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            return f"Error decompiling: {result.stderr}"
        
        return result.stdout
    except Exception as e:
        return f"Error: {str(e)}"

class JavaVirtualDebugger:
    def __init__(self, bytecode):
        self.bytecode = bytecode
        self.instructions = self.parse_bytecode(bytecode)
        self.breakpoints = []
        self.output = []
        self.variables = {}
        self.stack = []
        self.pc = 0  # Program counter
        self.current_instruction_index = 0  # Index in the instructions list
        self.execution_state = "stopped"  # Can be "stopped", "running", "paused"
        self.line_to_instruction = self._build_line_map()
        self.last_breakpoint_hit = None  # Track the last breakpoint hit
        self.program_output = []  # Store program output
        self.string_constants = {}  # Store string constants from constant pool
        self.parse_constant_pool(bytecode)

    def _build_line_map(self):
        """Create a mapping from source lines to instruction indexes"""
        line_map = {}
        for idx, instr in enumerate(self.instructions):
            if instr['line'] is not None:
                if instr['line'] not in line_map:
                    line_map[instr['line']] = []
                line_map[instr['line']].append(idx)
        return line_map
        
    def parse_bytecode(self, bytecode):
        instructions = []
        current_line = None
        
        # Simple parser for javap output
        for line in bytecode.split('\n'):
            # Detect line numbers
            line_match = re.search(r"line (\d+):", line)
            if line_match:
                current_line = int(line_match.group(1))
                
            # Detect bytecode instructions
            instr_match = re.search(r"^\s*(\d+): ([a-zA-Z_]+)(.*?)(?://.*)?$", line)
            if instr_match:
                offset = int(instr_match.group(1))
                opcode = instr_match.group(2)
                operands = instr_match.group(3).strip()
                instructions.append({
                    'offset': offset,
                    'opcode': opcode,
                    'operands': operands,
                    'line': current_line
                })
                
        return instructions
    
    def parse_constant_pool(self, bytecode):
        """Parse constant pool entries for strings"""
        in_constant_pool = False
        for line in bytecode.split('\n'):
            if 'Constant pool:' in line:
                in_constant_pool = True
                continue
            if in_constant_pool:
                if line.strip() == '':
                    in_constant_pool = False
                    continue
                # Match string constants
                string_match = re.search(r'#\d+\s+=\s+String\s+#\d+\s+//\s+(.+)$', line)
                if string_match:
                    string_value = string_match.group(1)
                    index = int(re.search(r'#(\d+)', line).group(1))
                    self.string_constants[index] = string_value
                # Match UTF8 constants
                utf8_match = re.search(r'#\d+\s+=\s+Utf8\s+(.+)$', line)
                if utf8_match:
                    string_value = utf8_match.group(1)
                    index = int(re.search(r'#(\d+)', line).group(1))
                    self.string_constants[index] = string_value

    def reset(self):
        """Reset execution state"""
        self.output = []
        self.variables = {"a": 5, "b": 10}  # Simulate initial variables
        self.stack = []
        self.current_instruction_index = 0
        self.execution_state = "stopped"
        self.output.append("Program reset. Ready to run.")
        self.program_output = []  # Clear program output
        return "\n".join(self.output)
    
    def step(self):
        """Execute a single instruction"""
        self.execution_state = "paused"
        
        if self.current_instruction_index >= len(self.instructions):
            self.output.append("End of program reached.")
            self.execution_state = "stopped"
            return "\n".join(self.output)
        
        # Get the current instruction
        instr = self.instructions[self.current_instruction_index]
        current_offset = instr['offset']
        
        # Clear the output list for a cleaner display
        self.output = []
        
        # Show the instruction being executed
        self.output.append(f"Executing: {current_offset}: {instr['opcode']} {instr['operands']}")
        if instr['line'] is not None:
            self.output.append(f"Source line: {instr['line']}")
        
        # Simulate execution of this instruction
        self._simulate_instruction(instr)
        
        # Move to next instruction
        self.current_instruction_index += 1
        
        # Show the state
        self._show_state()
        
        return "\n".join(self.output)
    
    def _simulate_instruction(self, instr):
        """Simulate the execution of an instruction"""
        opcode = instr['opcode']
        operands = instr['operands']
        
        if opcode == 'ldc':
            # Load constant from constant pool
            const_index = int(re.search(r'#(\d+)', operands).group(1))
            if const_index in self.string_constants:
                self.stack.append(self.string_constants[const_index])
                self.output.append(f"Loaded string constant: {self.string_constants[const_index]}")
            else:
                try:
                    # Try to parse as number if it's not a string
                    value = float(operands.strip())
                    self.stack.append(value)
                    self.output.append(f"Loaded constant: {value}")
                except:
                    self.stack.append(None)
        elif opcode == 'getstatic' and 'java/lang/System.out' in operands:
            # System.out reference - no action needed
            pass
        elif opcode == 'invokevirtual':
            if 'println' in operands:
                # Handle different println overloads
                if len(self.stack) >= 1:
                    value = self.stack.pop()
                    output_str = str(value)
                    self.output.append(f"Program output: {output_str}")
                    self.program_output.append(f"{output_str}\n")
            elif 'append' in operands:
                # Handle StringBuilder append
                if len(self.stack) >= 2:
                    value = self.stack.pop()
                    builder = self.stack.pop()
                    result = str(builder) + str(value)
                    self.stack.append(result)
                    self.output.append(f"Appended: {value} to {builder}")
            elif 'toString' in operands:
                # Handle toString calls
                if len(self.stack) >= 1:
                    value = self.stack.pop()
                    result = str(value)
                    self.stack.append(result)
                    self.output.append(f"Converted to string: {result}")
        elif opcode == 'new' and 'java/lang/StringBuilder' in operands:
            # Initialize new StringBuilder
            self.stack.append("")
            self.output.append("Created new StringBuilder")
        else:
            # Handle other numeric operations
            # ...existing numeric operation handling...
            if opcode == 'istore_1':
                # Store top of stack to local variable 1
                if self.stack:
                    self.variables["a"] = self.stack.pop()
                    self.output.append(f"Set variable 'a' = {self.variables['a']}")
            elif opcode == 'istore_2':
                # Store top of stack to local variable 2
                if self.stack:
                    self.variables["b"] = self.stack.pop()
                    self.output.append(f"Set variable 'b' = {self.variables['b']}")
            elif opcode == 'iconst_5':
                # Push constant 5 to stack
                self.stack.append(5)
                self.output.append("Pushed constant 5 to stack")
            elif opcode == 'bipush':
                # Push byte constant
                value = int(operands.strip())
                self.stack.append(value)
                self.output.append(f"Pushed constant {value} to stack")
            elif opcode == 'iadd':
                # Add top two stack values
                if len(self.stack) >= 2:
                    b = self.stack.pop()
                    a = self.stack.pop()
                    result = a + b
                    self.stack.append(result)
                    self.output.append(f"Added {a} + {b} = {result}")
            elif opcode == 'isub':
                # Subtract top two stack values
                if len(self.stack) >= 2:
                    b = self.stack.pop()
                    a = self.stack.pop()
                    result = a - b
                    self.stack.append(result)
                    self.output.append(f"Subtracted {a} - {b} = {result}")
            elif opcode in ['imul', 'idiv', 'irem']:
                # Other operations
                if len(self.stack) >= 2:
                    b = self.stack.pop()
                    a = self.stack.pop()
                    if opcode == 'imul':
                        result = a * b
                        self.output.append(f"Multiplied {a} * {b} = {result}")
                    elif opcode == 'idiv':
                        result = a // b
                        self.output.append(f"Divided {a} / {b} = {result}")
                    elif opcode == 'irem':
                        result = a % b
                        self.output.append(f"Remainder {a} % {b} = {result}")
                    self.stack.append(result)
    
    def _show_state(self):
        """Show the current program state"""
        self.output.append("\nCurrent State:")
        self.output.append(f"PC: {self.current_instruction_index}")
        
        # Show stack
        stack_str = ", ".join(str(item) for item in self.stack)
        self.output.append(f"Stack: [{stack_str}]")
        
        # Show variables
        var_str = ", ".join(f"{k}={v}" for k, v in self.variables.items())
        self.output.append(f"Variables: {var_str}")
        self.output.append("")  # Empty line for readability
    
    def run_to_next_breakpoint(self):
        """Run execution until next breakpoint is hit or program ends"""
        self.execution_state = "running"
        self.output = []
        
        # Skip the current breakpoint if we're already on it
        skip_current = False
        if self.current_instruction_index < len(self.instructions):
            current_offset = self.instructions[self.current_instruction_index]['offset']
            if current_offset in self.breakpoints and current_offset == self.last_breakpoint_hit:
                skip_current = True
        
        while self.current_instruction_index < len(self.instructions):
            current_instr = self.instructions[self.current_instruction_index]
            current_offset = current_instr['offset']
            
            # Check if this instruction is at a breakpoint
            if current_offset in self.breakpoints and (not skip_current or current_offset != self.last_breakpoint_hit):
                self.execution_state = "paused"
                self.last_breakpoint_hit = current_offset
                self._show_state()
                return "\n".join(self.output)
            
            # After processing the first instruction, we're past any skipped breakpoint
            skip_current = False
            
            # Simulate execution (minimal output during run to breakpoint)
            self._simulate_instruction(current_instr)
            self.current_instruction_index += 1
        
        self.execution_state = "stopped"
        self._show_state()
        return "\n".join(self.output)
    
    def run_to_breakpoint(self):
        # For backward compatibility
        return self.run_to_next_breakpoint()
    
    def get_current_instruction_index(self):
        """Get the current instruction index for highlighting"""
        return self.current_instruction_index if self.current_instruction_index < len(self.instructions) else None
    
    def get_current_line(self):
        """Get the current source line number for highlighting"""
        if self.current_instruction_index < len(self.instructions):
            return self.instructions[self.current_instruction_index].get('line')
        return None

class ProjectExplorer(ttk.Frame):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.class_references: Dict[str, Set[str]] = {}  # Store class dependencies
        
        # Create navigation frame
        self.nav_frame = ttk.Frame(self)
        self.nav_frame.pack(side=TOP, fill=X)
        
        # Add navigation buttons
        self.back_button = ttk.Button(self.nav_frame, text="⬅ Back", command=self.go_back)
        self.back_button.pack(side=LEFT, padx=2)
        
        self.forward_button = ttk.Button(self.nav_frame, text="➡ Forward", command=self.go_forward)
        self.forward_button.pack(side=LEFT, padx=2)
        
        self.up_button = ttk.Button(self.nav_frame, text="⬆ Up", command=self.go_up)
        self.up_button.pack(side=LEFT, padx=2)
        
        # Add "Show Dependencies" button
        self.dep_button = ttk.Button(self.nav_frame, text="🔍 Dependencies", command=self.show_dependencies)
        self.dep_button.pack(side=LEFT, padx=2)
        
        # Create path label
        self.path_label = ttk.Label(self, text="", wraplength=200)
        self.path_label.pack(side=TOP, fill=X, padx=5, pady=2)
        
        # Create treeview with columns for name and type
        self.tree = ttk.Treeview(self, selectmode='browse', columns=('type', 'path'))
        self.tree.heading('#0', text='Name', anchor=W)
        self.tree.heading('type', text='Type', anchor=W)
        self.tree.column('type', width=100)
        self.tree.column('path', width=0, stretch=NO)  # Hidden column for full path
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(self, orient=VERTICAL, command=self.tree.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Bind events
        self.tree.bind('<Double-1>', self.on_double_click)
        self.tree.bind('<<TreeviewSelect>>', self.on_select)
        
        # Initialize history
        self.history = []
        self.current_index = -1
        
        # Load current directory
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.load_directory(self.current_dir)
    
    def load_directory(self, path):
        """Load a directory and analyze Java project structure"""
        self.current_dir = path
        self.tree.delete(*self.tree.get_children())
        self.path_label.config(text=path)
        
        # Add to history
        if self.current_index == -1 or path != self.history[self.current_index]:
            self.history = self.history[:self.current_index + 1]
            self.history.append(path)
            self.current_index = len(self.history) - 1
        
        try:
            entries = os.listdir(path)
            
            # Add parent directory entry if not at root
            parent_path = os.path.dirname(path)
            if parent_path != path:  # Not at root
                self.tree.insert('', 0, text="📂 ..", values=('Directory', parent_path), tags=('parent',))
            
            # Group entries by type
            dirs = []
            class_files = []
            java_files = []
            other_files = []
            
            for entry in entries:
                full_path = os.path.join(path, entry)
                if os.path.isdir(full_path):
                    if not entry.startswith('.'):
                        dirs.append((entry, full_path))
                elif entry.endswith('.class'):
                    class_files.append((entry, full_path))
                elif entry.endswith('.java'):
                    java_files.append((entry, full_path))
                elif entry.endswith(('.jar', '.war', '.ear')):
                    other_files.append((entry, full_path))
            
            # Add directories first
            for name, full_path in sorted(dirs):
                icon = '📂' if name in ['src', 'bin', 'build', 'target'] else '📁'
                self.tree.insert('', 'end', text=f"{icon} {name}", 
                               values=('Directory', full_path))
            
            # Add class files
            for name, full_path in sorted(class_files):
                self.tree.insert('', 'end', text=f"☕ {name}", 
                               values=('Class', full_path))
                self.analyze_class_file(full_path)
            
            # Add Java source files
            for name, full_path in sorted(java_files):
                self.tree.insert('', 'end', text=f"📝 {name}", 
                               values=('Source', full_path))
            
            # Add other Java-related files
            for name, full_path in sorted(other_files):
                self.tree.insert('', 'end', text=f"📦 {name}", 
                               values=('Archive', full_path))
            
        except Exception as e:
            print(f"Error loading directory {path}: {e}")
        
        self.update_nav_buttons()
    
    def analyze_class_file(self, class_file):
        """Analyze a class file for dependencies"""
        try:
            output = disassemble_class(class_file)
            # Find references to other classes
            refs = set()
            for line in output.split('\n'):
                # Look for class references in constant pool
                if 'Class' in line and 'java/lang' not in line:
                    match = re.search(r'Class\s+(.+?)[\s/]', line)
                    if match:
                        refs.add(match.group(1))
            self.class_references[os.path.basename(class_file)] = refs
        except Exception as e:
            print(f"Error analyzing {class_file}: {e}")
    
    def show_dependencies(self):
        """Show dependencies of selected class file"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = selection[0]
        item_type = self.tree.item(item)['values'][0]
        if item_type != 'Class':
            return
        
        class_name = os.path.basename(self.tree.item(item)['values'][1])
        if class_name not in self.class_references:
            return
        
        # Create dependencies window
        dep_window = tk.Toplevel(self)
        dep_window.title(f"Dependencies for {class_name}")
        dep_window.geometry("400x300")
        
        # Add dependencies view
        deps_frame = ttk.Frame(dep_window)
        deps_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        # References to other classes
        ttk.Label(deps_frame, text="References:").pack(anchor=W)
        refs_text = scrolledtext.ScrolledText(deps_frame, height=5)
        refs_text.pack(fill=BOTH, expand=True)
        for ref in sorted(self.class_references[class_name]):
            refs_text.insert(END, f"• {ref}\n")
        refs_text.config(state=DISABLED)
        
        # Classes that reference this class
        ttk.Label(deps_frame, text="Referenced by:").pack(anchor=W)
        refs_by_text = scrolledtext.ScrolledText(deps_frame, height=5)
        refs_by_text.pack(fill=BOTH, expand=True)
        for other_class, refs in self.class_references.items():
            if class_name.replace('.class', '') in refs:
                refs_by_text.insert(END, f"• {other_class}\n")
        refs_by_text.config(state=DISABLED)
    
    def on_select(self, event):
        """Handle tree item selection"""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            item_type = self.tree.item(item)['values'][0]
            self.dep_button.state(['!disabled'] if item_type == 'Class' else ['disabled'])
    
    def go_back(self):
        """Navigate to previous directory"""
        if self.current_index > 0:
            self.current_index -= 1
            self.load_directory(self.history[self.current_index])
    
    def go_forward(self):
        """Navigate to next directory in history"""
        if self.current_index < len(self.history) - 1:
            self.current_index += 1
            self.load_directory(self.history[self.current_index])
    
    def update_nav_buttons(self):
        """Update navigation button states"""
        self.back_button.state(['!disabled'] if self.current_index > 0 else ['disabled'])
        self.forward_button.state(['!disabled'] if self.current_index < len(self.history) - 1 else ['disabled'])
        self.up_button.state(['!disabled'] if self.current_dir != os.path.dirname(self.current_dir) else ['disabled'])
    
    def on_double_click(self, event):
        """Handle double-click on tree item"""
        item = self.tree.selection()[0]
        path = self.tree.item(item)['values'][1]
        if os.path.isdir(path):
            self.load_directory(path)
        elif path.endswith('.class'):
            self.callback(path)
    
    def go_up(self):
        """Navigate to parent directory"""
        parent = os.path.dirname(self.current_dir)
        if (parent != self.current_dir):  # Prevent going above root
            self.load_directory(parent)
    
    def refresh(self):
        """Refresh the current directory view"""
        self.load_directory(self.current_dir)

class DecompilerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Java Advanced Decompiler")
        self.root.geometry("1000x600")
        
        # Main application style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configure a custom font
        self.code_font = font.Font(family="Consolas", size=10)
        
        # Create the main container
        self.main_container = ttk.Frame(root)
        self.main_container.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        # Create the top frame for title only
        self.top_frame = ttk.Frame(self.main_container)
        self.top_frame.pack(fill=X, pady=5)
        
        # Title label
        title_label = ttk.Label(self.top_frame, text="Java Decompiler and Debugger", font=("Arial", 14, "bold"))
        title_label.pack(side=LEFT, padx=5)
        
        # Create main horizontal paned window
        self.main_pane = ttk.PanedWindow(self.main_container, orient=HORIZONTAL)
        self.main_pane.pack(fill=BOTH, expand=True)
        
        # Create file explorer frame
        self.explorer_frame = ttk.LabelFrame(self.main_pane, text="File Explorer")
        self.main_pane.add(self.explorer_frame, weight=1)
        
        # Create file explorer
        self.file_explorer = ProjectExplorer(self.explorer_frame, self.open_class_file)
        self.file_explorer.pack(fill=BOTH, expand=True)
        
        # Create main content frame
        self.content_frame = ttk.Frame(self.main_pane)
        self.main_pane.add(self.content_frame, weight=4)
        
        # Create and pack notebook in content frame
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=BOTH, expand=True)
        
        # Create frames for each tab
        self.disasm_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.disasm_frame, text="Bytecode")
        
        self.decompiled_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.decompiled_frame, text="Decompiled Source")

        self.debugger_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.debugger_frame, text="Debug View")
        
        # Set up the debugger view with a horizontal paned window
        self.debug_pane = ttk.PanedWindow(self.debugger_frame, orient=HORIZONTAL)
        self.debug_pane.pack(fill=BOTH, expand=True)
        
        # Left side: bytecode with line numbers
        self.debug_bytecode_frame = ttk.Frame(self.debug_pane)
        self.debug_pane.add(self.debug_bytecode_frame, weight=2)
        
        # Configure bytecode text widget with line numbers
        self.debug_bytecode_container = ttk.Frame(self.debug_bytecode_frame)
        self.debug_bytecode_container.pack(fill=BOTH, expand=True)
        
        self.debug_bytecode_text = scrolledtext.ScrolledText(
            self.debug_bytecode_container, 
            wrap=NONE, 
            font=self.code_font
        )
        self.debug_bytecode_text.pack(side=RIGHT, fill=BOTH, expand=True)
        
        # Line numbers for debug bytecode
        self.debug_line_numbers = LineNumberCanvas(
            self.debug_bytecode_container,
            self.debug_bytecode_text,
            width=50, 
            background='#f0f0f0'
        )
        self.debug_line_numbers.pack(side=LEFT, fill=Y)
        
        # Right side: console output and controls
        self.debug_console_frame = ttk.Frame(self.debug_pane)
        self.debug_pane.add(self.debug_console_frame, weight=1)
        
        # Add run control buttons
        self.debug_controls = ttk.Frame(self.debug_console_frame)
        self.debug_controls.pack(fill=X)
        
        self.reset_button = ttk.Button(self.debug_controls, text="Reset", command=self.reset_debugger)
        self.reset_button.pack(side=LEFT, padx=5, pady=5)
        
        self.step_button = ttk.Button(self.debug_controls, text="Step", command=self.step_execution)
        self.step_button.pack(side=LEFT, padx=5, pady=5)
        
        self.run_button = ttk.Button(self.debug_controls, text="Run", command=self.run_to_breakpoint)
        self.run_button.pack(side=LEFT, padx=5, pady=5)
        
        # Console output label
        self.console_label = ttk.Label(self.debug_console_frame, text="Console Output:")
        self.console_label.pack(anchor=W, padx=5)
        
        # Console output text
        self.console_text = scrolledtext.ScrolledText(
            self.debug_console_frame, 
            wrap=WORD,
            font=self.code_font,
            height=10
        )
        self.console_text.pack(fill=BOTH, expand=True, padx=5, pady=5)
        
        # Program output label
        self.program_output_label = ttk.Label(self.debug_console_frame, text="Program Output:")
        self.program_output_label.pack(anchor=W, padx=5)
        
        # Program output text
        self.program_output_text = scrolledtext.ScrolledText(
            self.debug_console_frame, 
            wrap=WORD,
            font=self.code_font,
            height=10
        )
        self.program_output_text.pack(fill=BOTH, expand=True, padx=5, pady=5)
        
        # Highlight tags
        self.debug_bytecode_text.tag_configure("current_line", background="#ffff99")
        
        # Set up the disassembly view
        self.disasm_container = ttk.Frame(self.disasm_frame)
        self.disasm_container.pack(fill=BOTH, expand=True)
        
        self.disasm_text = scrolledtext.ScrolledText(
            self.disasm_container, 
            wrap=NONE,
            font=self.code_font
        )
        self.disasm_text.pack(side=RIGHT, fill=BOTH, expand=True)
        
        self.disasm_line_numbers = LineNumberCanvas(
            self.disasm_container,
            self.disasm_text,
            width=50, 
            background='#f0f0f0'
        )
        self.disasm_line_numbers.pack(side=LEFT, fill=Y)
        
        # Set up the decompiled view
        self.decompiled_container = ttk.Frame(self.decompiled_frame)
        self.decompiled_container.pack(fill=BOTH, expand=True)
        
        self.decompiled_text = scrolledtext.ScrolledText(
            self.decompiled_container, 
            wrap=NONE,
            font=self.code_font
        )
        self.decompiled_text.pack(side=RIGHT, fill=BOTH, expand=True)
        
        self.decompiled_line_numbers = LineNumberCanvas(
            self.decompiled_container,
            self.decompiled_text,
            width=50, 
            background='#f0f0f0'
        )
        self.decompiled_line_numbers.pack(side=LEFT, fill=Y)
        
        # Status bar with updated legend
        self.status_frame = ttk.Frame(root)
        self.status_frame.pack(side=BOTTOM, fill=X)
        
        self.status_var = tk.StringVar()
        self.status_var.set("Double-click a .class file to decompile and debug")
        self.status_bar = ttk.Label(
            self.status_frame, 
            textvariable=self.status_var, 
            relief=SUNKEN, 
            anchor=W
        )
        self.status_bar.pack(side=LEFT, fill=X, expand=True)
        
        # Updated legend
        self.legend_label = ttk.Label(
            self.status_frame,
            text="📁 Folder  📂 Project  ☕ Class (double-click to open)  📝 Source",
            padding=(5, 0)
        )
        self.legend_label.pack(side=RIGHT)
        
        # Store the current class file
        self.current_class_file = None
        self.debugger = None
        self.last_highlight = None  # Track the last highlighted line
        
        # Check for Java
        try:
            subprocess.run(['java', '-version'], capture_output=True)
        except:
            messagebox.showerror("Error", "Java is not installed or not in PATH")
            root.destroy()
    
    def reset_debugger(self):
        if not self.debugger:
            self.console_text.delete(1.0, END)
            self.console_text.insert(END, "No bytecode loaded. Please open a class file first.")
            return
            
        output = self.debugger.reset()
        self.update_console(output)
        
        # Reset the last breakpoint hit
        self.debugger.last_breakpoint_hit = None
        
        # Clear highlighting
        if self.last_highlight:
            self.debug_bytecode_text.tag_remove("current_line", self.last_highlight, f"{self.last_highlight}+1line")
            self.last_highlight = None
        
        # Clear program output
        self.program_output_text.delete(1.0, END)
    
    def step_execution(self):
        if not self.debugger:
            self.console_text.delete(1.0, END)
            self.console_text.insert(END, "No bytecode loaded. Please open a class file first.")
            return
        
        output = self.debugger.step()
        self.update_console(output)
        
        # Update highlighting for current instruction
        self.highlight_current_instruction()
        
        # Update program output
        self.update_program_output()
    
    def highlight_current_instruction(self):
        """Highlight the current instruction in the bytecode view"""
        # Remove previous highlighting
        if self.last_highlight:
            self.debug_bytecode_text.tag_remove("current_line", self.last_highlight, f"{self.last_highlight}+1line")
        
        current_idx = self.debugger.get_current_instruction_index()
        if current_idx is not None and current_idx < len(self.debugger.instructions):
            # Find the line in the text widget that corresponds to this instruction
            for line_num in range(1, int(self.debug_bytecode_text.index('end').split('.')[0])):
                line_text = self.debug_bytecode_text.get(f"{line_num}.0", f"{line_num}.end")
                instr_offset = self.debugger.instructions[current_idx]['offset']
                
                if line_text.strip().startswith(f"{instr_offset}:"):
                    self.debug_bytecode_text.tag_add("current_line", f"{line_num}.0", f"{line_num}.end")
                    self.debug_bytecode_text.see(f"{line_num}.0")  # Ensure the line is visible
                    self.last_highlight = f"{line_num}.0"
                    break
    
    def run_to_breakpoint(self):
        if not self.debugger:
            self.console_text.delete(1.0, END)
            self.console_text.insert(END, "No bytecode loaded. Please open a class file first.")
            return
            
        # Get breakpoints from the line number widget
        breakpoints = self.debug_line_numbers.get_breakpoints()
        if not breakpoints:
            self.console_text.delete(1.0, END)
            self.console_text.insert(END, "No breakpoints set. Click on the line numbers to set breakpoints.")
            return
            
        # Convert line numbers to bytecode offsets
        bytecode_breakpoints = []
        for line in breakpoints:
            line_text = self.debug_bytecode_text.get(f"{line}.0", f"{line}.end")
            offset_match = re.match(r'^\s*(\d+):', line_text)
            if offset_match:
                bytecode_breakpoints.append(int(offset_match.group(1)))
        
        self.debugger.breakpoints = bytecode_breakpoints
        
        # Run the simulation
        self.status_var.set("Running to next breakpoint...")
        output = self.debugger.run_to_next_breakpoint()
        self.update_console_and_highlight(output)
        
        # Update program output
        self.update_program_output()
    
    def update_console_and_highlight(self, output):
        self.update_console(output)
        self.highlight_current_instruction()
        
        if self.debugger.execution_state == "stopped":
            self.status_var.set("Program execution completed")
        else:
            self.status_var.set("Paused at breakpoint")
    
    def update_console(self, output):
        self.console_text.delete(1.0, END)
        self.console_text.insert(END, output)
        self.console_text.see(END)  # Scroll to the end
    
    def update_program_output(self):
        self.program_output_text.delete(1.0, END)
        self.program_output_text.insert(END, "".join(self.debugger.program_output))
        self.program_output_text.see(END)  # Scroll to the end
    
    def open_class_file(self, class_file):
        """Open a class file from the explorer"""
        self.current_class_file = class_file
        self.status_var.set(f"Processing: {os.path.basename(class_file)}")
        self.root.update_idletasks()
        
        # Clear existing breakpoints in all views
        self.debug_line_numbers.breakpoints.clear()
        self.disasm_line_numbers.breakpoints.clear()
        self.decompiled_line_numbers.breakpoints.clear()
        
        # Force redraw of line number canvases
        self.debug_line_numbers.redraw()
        self.disasm_line_numbers.redraw()
        self.decompiled_line_numbers.redraw()
        
        def process_file():
            try:
                disassembled_code = disassemble_class(class_file)
                decompiled_code = decompile_class(class_file)
                self.debugger = JavaVirtualDebugger(disassembled_code)
                self.debugger.breakpoints = []  # Reset debugger breakpoints
                self.root.after(0, lambda: self.update_ui(disassembled_code, decompiled_code))
                self.status_var.set(f"Loaded: {os.path.basename(class_file)}")
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
                self.root.after(0, lambda: self.status_var.set("Error occurred"))
        
        thread = threading.Thread(target=process_file)
        thread.daemon = True
        thread.start()
    
    def update_ui(self, disassembled_code, decompiled_code):
        # Update disassembly tab
        self.disasm_text.delete(1.0, END)
        self.disasm_text.insert(END, disassembled_code)
        
        # Update decompiled tab
        self.decompiled_text.delete(1.0, END)
        self.decompiled_text.insert(END, decompiled_code)
        
        # Update debug view
        self.debug_bytecode_text.delete(1.0, END)
        
        # Format the bytecode for easier debugging
        formatted_bytecode = ""
        for instr in self.debugger.instructions:
            line = f"{instr['offset']}: {instr['opcode']} {instr['operands']}"
            formatted_bytecode += line + "\n"
            
        self.debug_bytecode_text.insert(END, formatted_bytecode)
        
        # Clear console
        self.console_text.delete(1.0, END)
        self.console_text.insert(END, "Click 'Step' to execute one instruction at a time.\n")
        self.console_text.insert(END, "Click 'Run to Breakpoint' to execute until the next breakpoint.\n")
        self.console_text.insert(END, "Click 'Reset' to start over from the beginning.\n")
        self.console_text.insert(END, "Set breakpoints by clicking on the line numbers.")
        
        self.status_var.set("Ready")

# Main entry point
if __name__ == "__main__":
    # Ensure CFR is downloaded
    download_cfr()
    
    # Start the application
    root = tk.Tk()
    app = DecompilerApp(root)
    root.mainloop()
