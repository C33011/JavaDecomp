@echo off
mkdir bin 2>nul

javac -d bin src/*.java
if %errorlevel% neq 0 (
    echo Compilation failed
    pause
    exit /b %errorlevel%
)

echo Compilation successful
java -cp bin Main
pause
