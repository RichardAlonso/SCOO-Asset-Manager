# build.py
import PyInstaller.__main__
import os
import sys

# INCREASE RECURSION LIMIT
sys.setrecursionlimit(5000)

if __name__ == '__main__':
    PyInstaller.__main__.run([
        'run_app.py',                       
        '--name=SCOO_Asset_Manager',        
        '--onefile',                        
        '--clean',                          
        
        # Keep windowed REMOVED for now so you can see errors if it crashes.
        # Once it works, you can add '--windowed' back.
        # '--windowed',                       
        
        # Add your source files
        '--add-data=app.py;.',
        '--add-data=views.py;.',
        '--add-data=database.py;.',
        '--add-data=config.py;.',
        
        # Collect heavy libraries
        '--collect-all=streamlit',
        '--collect-all=altair',
        '--collect-all=pandas',
        '--collect-all=plotly',
        '--collect-all=pyzbar',
        '--collect-all=cv2',
        '--collect-all=qrcode', 
        '--collect-all=PIL',
        '--collect-all=bcrypt',
        '--collect-all=fpdf', 
        
        # CRITICAL FIX: Streamlit Metadata
        '--copy-metadata=streamlit',
        '--copy-metadata=tqdm',
        #'--copy-metadata=regex',
        '--copy-metadata=requests',
        '--copy-metadata=packaging',
        
        # EXCLUDE things we don't need
        '--exclude-module=pytest',
        '--exclude-module=langchain',
    ])