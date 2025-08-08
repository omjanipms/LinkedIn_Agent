@echo off
echo Setting up Python environment...
python -m pip install -r requirements.txt
echo.
echo Running LinkedIn Agent...
python linkedin_agent.py
pause 