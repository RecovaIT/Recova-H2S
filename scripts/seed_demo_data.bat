@echo off
cd /d "%~dp0\..\backend"
echo Seeding demo clinical cohorts and portal accounts...
call ".venv\Scripts\activate.bat"
python seed_demo.py
python scripts\seed_portal_demo.py
echo Database seeding completed successfully.
