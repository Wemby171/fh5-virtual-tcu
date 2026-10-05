@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
echo ============================================================
echo  Virtual TCU - FH5 packet capture
echo  Close Virtual TCU first, then be IN A RACE and driving.
echo ============================================================
echo.
python "%~dp0_capture_fh5_packet.py" %1
echo.
echo Script finished. Files written to this folder:
echo   _capture_fh5_packet.bin
echo   _capture_fh5_packet.txt
pause
