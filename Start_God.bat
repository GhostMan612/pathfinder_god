@echo off
echo Waking up the Pathfinder God...

:: Step 1: Open a hidden window, set the port, and boot Ollama
start "Ollama Brain" /MIN cmd /c "set OLLAMA_HOST=127.0.0.1:11450 && ollama serve"

:: Step 2: Navigate exactly to your hub folder
cd /d C:\pathfinder_god\hub

:: Step 3: Boot the Uvicorn server in the main window so you can see the logs
C:\venv-hub\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000