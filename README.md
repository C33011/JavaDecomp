# Java Bytecode Explorer

This is a python program made to act as a decompiler and debugger for Java bytecode. It lets you open .class files to see how they are compiled, and see how the bytecode runs.

## Features

- Opens `.class` files and shows you the Java source code inside
- Shows you the actual bytecode instructions
- Lets you debug through the code instruction by instruction
- Has a nice file browser to find your class files
- Shows how different classes are connected to each other
  
## Getting Started

You'll need:
- Java (JDK) installed
- Python 3.x

Just run:
```bash
python main.py
```

The program will handle downloading any other stuff it needs.

## How to Use It

1. Run the program
2. Use the file browser on the left to find your `.class` files
3. Double-click a file to open it
4. You'll see three tabs:
   - Bytecode: The raw Java instructions
   - Decompiled Source: The readable Java code
   - Debug View: Where you can step through the code

### Debugging

- Click on line numbers to set breakpoints
- Use "Step" to run one instruction at a time
- Use "Run" to go until the next breakpoint
- Click "Reset" to start over

## Example Java Files

I included some example Java files to test with. Here's a simple one:

```java
public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
    
    public static void main(String[] args) {
        Calculator calc = new Calculator();
        System.out.println(calc.add(5, 3));  // Prints: 8
    }
}
```

This is perfect for seeing how basic Java operations work in bytecode.

## Help and Tips

If something's not working:
- Make sure Java is installed properly
- Check that you're opening a valid `.class` file

## Want to Help?

Feel free to contribute! Just:
1. Fork it
2. Make your changes
3. Send a pull request

## License

MIT License - Use it however you want!

---
Made by Tate Matthews - Feel free to reach out if you have questions!
