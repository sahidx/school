@echo off
:: ============================================================
:: install_scheduler.bat
:: Registers zkbio_sync.py to run automatically every night at 11 PM
:: Run this once as Administrator on Windows
:: ============================================================

SET SCRIPT_DIR=%~dp0
SET TASK_NAME=ZKBioSchoolSync

:: Remove old task if exists
schtasks /Delete /TN "%TASK_NAME%" /F 2>nul

:: Create task: runs every day at 11:00 PM
schtasks /Create ^
  /TN "%TASK_NAME%" ^
  /TR "python \"%SCRIPT_DIR%zkbio_sync.py\"" ^
  /SC DAILY ^
  /ST 23:00 ^
  /RU SYSTEM ^
  /F

IF %ERRORLEVEL% EQU 0 (
  echo ===========================================
  echo  Scheduled task "%TASK_NAME%" created OK
  echo  Runs every day at 11:00 PM automatically
  echo ===========================================
) ELSE (
  echo FAILED. Make sure you are running as Administrator.
)
pause
