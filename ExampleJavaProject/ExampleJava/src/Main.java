public class Main {
    public static void main(String[] args) {
        // Create library instance
        Library library = new Library();

        // Add some books
        Book book1 = new Book("The Great Gatsby", "F. Scott Fitzgerald", "123456");
        Book book2 = new Book("1984", "George Orwell", "789012");
        Book book3 = new Book("To Kill a Mockingbird", "Harper Lee", "345678");

        library.addBook(book1);
        library.addBook(book2);
        library.addBook(book3);

        // Register a user
        User user = new User("John Doe", 1);
        library.registerUser(user);

        // Display all available books
        System.out.println("Available books:");
        library.displayAvailableBooks();

        // Borrow a book
        library.borrowBook(user, "123456");
        
        System.out.println("\nAvailable books after borrowing:");
        library.displayAvailableBooks();

        // Return the book
        library.returnBook(user, "123456");

        System.out.println("\nAvailable books after returning:");
        library.displayAvailableBooks();
    }
}
