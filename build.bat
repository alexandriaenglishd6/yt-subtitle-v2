@echo off
REM YouTube 字幕工具打包脚本
REM 使用 PyInstaller 打包为便携版

echo ========================================
echo  YouTube 字幕工具 - 便携版打包脚本
echo ========================================
echo.

REM 检查 yt-dlp.exe 是否存在
if not exist "yt-dlp.exe" (
    echo [WARNING] 未找到 yt-dlp.exe，打包后的程序可能无法正常工作
    echo [INFO] 请从以下地址下载：
    echo        https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe
    echo.
)

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

REM 复制 yt-dlp.exe 到打包目录
echo.
echo [INFO] 复制依赖文件...
if exist "yt-dlp.exe" (
    copy /Y "yt-dlp.exe" "dist\YT-Subtitle-Tool\"
    echo [OK] yt-dlp.exe 已复制到打包目录
) else (
    echo [WARNING] 未找到 yt-dlp.exe，跳过复制
)

REM 复制 ffmpeg.exe（如果存在）
if exist "ffmpeg.exe" (
    copy /Y "ffmpeg.exe" "dist\YT-Subtitle-Tool\"
    echo [OK] ffmpeg.exe 已复制到打包目录
)

echo.
echo ========================================
echo  打包完成！
echo ========================================
echo.
echo 输出目录: dist\YT-Subtitle-Tool\
echo.
echo 已自动包含的文件:
if exist "dist\YT-Subtitle-Tool\yt-dlp.exe" echo   - yt-dlp.exe [OK]
if exist "dist\YT-Subtitle-Tool\ffmpeg.exe" echo   - ffmpeg.exe [OK]
echo.
pause

