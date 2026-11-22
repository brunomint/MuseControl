# PyInstaller: transforma o MuseControl num programa (pasta dist/MuseControl).
# Usado pelo GitHub Actions para o instalador do Windows:
#   pyinstaller empacotar/musecontrol.spec
import os

raiz = os.path.dirname(SPECPATH)  # SPECPATH = pasta deste arquivo

a = Analysis(
    [os.path.join(raiz, "main.py")],
    pathex=[raiz],
    datas=[
        (os.path.join(raiz, "templates"), "templates"),
        (os.path.join(raiz, "static"), "static"),
    ],
    # importados só dentro de funções (o PyInstaller pode não ver sozinho)
    hiddenimports=["pyautogui", "rtmidi"],
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MuseControl",
    icon=os.path.join(SPECPATH, "musecontrol.ico"),
    console=True,  # a janelinha preta mostra o endereço; fechar = desligar
)
coll = COLLECT(exe, a.binaries, a.datas, name="MuseControl")
