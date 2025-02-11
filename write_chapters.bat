@echo off
chcp 65001 >nul

python "%~dp0write_chapters.py" %*
pause 
