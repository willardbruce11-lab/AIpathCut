; AIpathCut NSIS 安装脚本
;
; 使用方法:
;   1. 先运行 build/build.py 打包程序
;   2. 安装 NSIS: https://nsis.sourceforge.io/
;   3. 右键此文件选择 "Compile NSIS Script"
;   4. 或命令行运行: makensis build_nsis.nsi

!define PRODUCT_NAME "AIpathCut"
!define PRODUCT_VERSION "1.0.0"
!define PRODUCT_PUBLISHER "AIpathCut Team"
!define PRODUCT_WEB_SITE "https://github.com/willardbruce11-lab/AIpathCut"

; 安装程序属性
Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "AIpathCut_Setup_${PRODUCT_VERSION}.exe"
InstallDir "$PROGRAMFILES\AIpathCut"
InstallDirRegKey HKLM "Software\AIpathCut" "InstallLocation"
RequestExecutionLevel admin

; 使用现代化界面
!include "MUI2.nsh"

; 界面设置
!define MUI_ABORTWARNING
!define MUI_ICON "resources\icon.ico"
!define MUI_UNICON "resources\icon.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "resources\header.bmp"  ; 可选：150x57 像素

; 欢迎页面
!insertmacro MUI_PAGE_WELCOME
; 许可协议页面（可选）
; !insertmacro MUI_PAGE_LICENSE "LICENSE"
; 安装目录页面
!insertmacro MUI_PAGE_DIRECTORY
; 安装进度页面
!insertmacro MUI_PAGE_INSTFILES
; 完成页面
!insertmacro MUI_PAGE_FINISH

; 语言设置
!insertmacro MUI_LANGUAGE "SimpChinese"

; 安装区段
Section "主程序" SecMain
  SectionIn RO

  SetOutPath "$INSTDIR"

  ; 显示安装详情
  DetailPrint "正在复制程序文件..."

  ; 复制打包后的所有文件
  File /r "dist\AIpathCut\*"

  ; 创建开始菜单快捷方式
  DetailPrint "正在创建开始菜单快捷方式..."
  CreateDirectory "$SMPROGRAMS\AIpathCut"
  CreateShortCut "$SMPROGRAMS\AIpathCut\AIpathCut.lnk" "$INSTDIR\AIpathCut.exe"
  CreateShortCut "$SMPROGRAMS\AIpathCut\卸载 AIpathCut.lnk" "$INSTDIR\uninstall.exe"

  ; 创建桌面快捷方式
  DetailPrint "正在创建桌面快捷方式..."
  CreateShortCut "$DESKTOP\AIpathCut.lnk" "$INSTDIR\AIpathCut.exe"

  ; 写入注册表
  DetailPrint "正在写入注册表..."
  WriteRegStr HKLM "Software\AIpathCut" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "Software\AIpathCut" "Version" "${PRODUCT_VERSION}"

  ; 注册卸载信息
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AIpathCut" \
                   "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AIpathCut" \
                   "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AIpathCut" \
                   "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AIpathCut" \
                   "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AIpathCut" \
                   "UninstallString" "$INSTDIR\uninstall.exe"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AIpathCut" \
                   "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AIpathCut" \
                   "NoRepair" 1

  ; 创建卸载程序
  WriteUninstaller "$INSTDIR\uninstall.exe"

SectionEnd

; 卸载区段
Section "Uninstall"
  ; 删除文件
  DetailPrint "正在卸载..."
  RMDir /r "$INSTDIR"

  ; 删除快捷方式
  Delete "$DESKTOP\AIpathCut.lnk"
  RMDir /r "$SMPROGRAMS\AIpathCut"

  ; 删除注册表项
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\AIpathCut"
  DeleteRegKey HKLM "Software\AIpathCut"

SectionEnd
