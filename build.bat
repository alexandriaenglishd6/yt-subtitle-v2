@echo off
REM YouTube 字幕工具打包脚本
REM 使用 PyInstaller 打包为便携版

echo ========================================
echo  YouTube 字幕工具 - 便携版打包脚本
echo ========================================
echo.

REM 检查 PyInstaller 是否安装
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [INFO] 正在安装 PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] PyInstaller 安装失败
        pause
        exit /b 1
    )
)

REM 清理旧的构建文件
echo [INFO] 清理旧的构建文件...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

REM 开始打包
echo [INFO] 开始打包...
echo.
pyinstaller build.spec --clean

if errorlevel 1 (
    echo.
    echo [ERROR] 打包失败！
    pause
    exit /b 1
)

echo.
echo ========================================
echo  打包完成！
echo ========================================
echo.
echo 输出目录: dist\YT-Subtitle-Tool\
echo.
echo 请将以下文件复制到输出目录:
echo   - yt-dlp.exe (如果需要)
echo   - ffmpeg.exe (如果需要)
echo   - cookies.txt (如果需要)
echo.
pause
