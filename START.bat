@echo off
cd /d "%~dp0"
echo Installing requirements (first run only)...
pip install -r requirements.txt >nul 2>&1
echo.
echo Agent Broker Coach - 1 week social campaign.
echo Posts to Facebook, Instagram, LinkedIn, YouTube, TikTok on YOUR (Pakistan) clock.
echo  - 4 blocks/day (11 PM, 4 AM, 8 AM, 7 PM): 16 images + 8 videos per day.
echo  - Change --days below: 1 = test day, 7 = the full week.
echo.
python run.py go --days 7
echo.
pause
