/**
 * Example program for testing the decompiler
 */
public class ExampleProgram {
    private int number;
    private String text;
    
    public ExampleProgram(int number, String text) {
        this.number = number;
        this.text = text;
    }
    
    public int calculate(int x) {
        int result = 0;
        for (int i = 0; i < x; i++) {
            result += i * number;
            if (result > 1000) {
                break;
            }
        }
        return result;
    }
    
    public String getMessage() {
        return text + " - Value: " + number;
    }
    
    public static void main(String[] args) {
        ExampleProgram example = new ExampleProgram(42, "Hello World");
        System.out.println(example.getMessage());
        System.out.println("Calculation result: " + example.calculate(10));
    }
}
