@echo off
echo Running TCF PPC Pipeline...
cd /d "%~dp0"
python run_pipeline.py
exit /b %errorlevel%
