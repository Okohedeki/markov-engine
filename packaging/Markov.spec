"""Build a self-contained Windows executable from a clean Python environment."""
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).parent
data = [(str(root / 'markov_engine' / folder), 'markov_engine/' + folder)
        for folder in ('templates', 'static')]
data += [(str(root / 'LICENSE'), 'licenses')]
for package in ('trafilatura', 'justext', 'faster_whisper', 'certifi'):
    data += collect_data_files(package)
for distribution in ('markov-engine', 'clerk-backend-api', 'yt-dlp', 'voyageai'):
    data += copy_metadata(distribution)

analysis = Analysis([str(root / 'markov_engine' / 'windows.py')],
    pathex=[str(root)], datas=data, binaries=[],
    hiddenimports=['uvicorn.logging', 'uvicorn.lifespan.on',
                   'uvicorn.protocols.http.h11_impl', 'qrcode.image.svg'],
    hookspath=[], runtime_hooks=[],
    excludes=['llama_cpp', 'torch', 'tensorflow', 'IPython', 'pytest'],
    noarchive=False)
archive = PYZ(analysis.pure)
exe = EXE(archive, analysis.scripts, analysis.binaries, analysis.datas, [],
    name='Markov', console=True, debug=False, strip=False, upx=False,
    version=str(root / 'packaging' / 'windows-version.txt')
        if (root / 'packaging' / 'windows-version.txt').exists() else None)
