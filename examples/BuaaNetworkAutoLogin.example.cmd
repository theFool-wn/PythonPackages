@echo off
cd /d "%~dp0"
call conda activate my_env
if errorlevel 1 exit /b 1
BuaaNetworkAutoLogin watch --config "%~dp0BuaaNetworkAutoLogin.json"