# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['run.py'],
    pathex=['C:\\Users\\black\\OneDrive\\Desktop\\WarrantyAPP'],
    binaries=[],
    datas=[
        # Включаем app.py (обязательно, run.py его запускает)
        ('app.py', '.'),
        # Включаем database.py (app.py его импортирует)
        ('database.py', '.'),

        # Включаем папку шаблонов
        ('templates', 'templates'),

        # Включаем папку для загруженных фото (она нужна для start_server)
        ('uploads', 'uploads'),

        # Включаем файл базы данных (PyInstaller должен его видеть)
        ('guarantee_repairs.db', '.'),

        # Включаем папку статики (иконки, manifest)
        ('static', 'static'),

        # Если вы использовали иконку .ico для run.py (Шаг 2.1)
        ('static/favicon.ico', '.'), 
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='run',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
