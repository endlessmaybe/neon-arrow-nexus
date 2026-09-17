@echo off
chcp 65001 >nul
pushd "%~dp0dist"
start "霓虹箭域" "NeonArrowNexus-Python.exe"
popd
