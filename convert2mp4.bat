@chcp 65001 > nul
@echo off
setlocal enabledelayedexpansion

for %%f in (%*) do (
    powershell -ExecutionPolicy Bypass -File "%~dp0convert2mp4.ps1" -inputFile "%%f"
    echo.
)

pause 