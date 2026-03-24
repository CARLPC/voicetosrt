@echo off
setlocal EnableExtensions

set "ENV_DIR=voice"
echo [INFO] Start run.cmd, env=%ENV_DIR%

where conda >nul 2>nul
if errorlevel 1 (
  echo [ERROR] conda not found in PATH.
  pause
  exit /b 1
)
echo [INFO] conda OK.

:: 不要用 conda run 做探测：在 Windows 上可能长时间无输出/像卡住
echo [INFO] Checking if conda env "%ENV_DIR%" exists...
conda env list 2>nul | findstr /r /c:"^%ENV_DIR% " >nul
if errorlevel 1 (
  echo [INFO] Conda env "%ENV_DIR%" 不存在，正在创建...
  conda create -n "%ENV_DIR%" python=3.10 -y
  conda install -n "%ENV_DIR%" -c conda-forge libuv -y
) else (
  echo [INFO] Conda env "%ENV_DIR%" 已存在，跳过创建。
)

echo [INFO] Activating "%ENV_DIR%" ...
call conda activate "%ENV_DIR%"
if errorlevel 1 (
  echo [ERROR] conda activate failed.
  pause
  exit /b 1
)

echo [INFO] Installing requirements.txt
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install -r requirements.txt failed.
  pause
  exit /b 1
)


echo [INFO] Running app.py
python app.py

endlocal
