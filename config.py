# config.py
APP_VERSION = "2.312 by Config Mang"

# Database
DB_NAME = "asset_manager.db"

# Scopes / Permissions
SCOPE_ADMIN = "Admin"             # Full Access
SCOPE_READ_WRITE = "Read/Write"   # Can add/edit/scan, cannot manage users
SCOPE_READ_ONLY = "Read Only"     # Can only view dashboard and search

# Column headers (Updated with new fields)
ASSET_COLUMNS = [
    "ID", "Type", "Make", "Model", "Serial", "Stock #", 
    "ITEC", "Price", "Building", "Room", "Class", 
    "Rack", "Row", "Table", "Assigned To", "Tags", 
    "Date Added", "Last Modified", "Last Scanned"
]