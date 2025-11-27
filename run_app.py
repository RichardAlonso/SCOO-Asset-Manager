# run_app.py
import streamlit.web.cli as stcli
import os, sys

def resolve_path(path):
    if getattr(sys, "frozen", False):
        basedir = sys._MEIPASS
    else:
        basedir = os.path.dirname(__file__)
    return os.path.join(basedir, path)

if __name__ == "__main__":
    # 1. Set environment variables to prevent browser issues
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
    
    # 2. Identify the path to the main app file
    app_path = resolve_path("app.py")
    
    # 3. Construct the arguments for the streamlit CLI
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
    ]
    
    # 4. Start the app
    sys.exit(stcli.main())