import sqlite3
import hashlib
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, or_
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session, relationship
import config

# --- 1. SETUP ORM BASE ---
Base = declarative_base()

# --- 2. DEFINE MODELS (TABLES) ---
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default='User')
    scope = Column(String, default='Read Only')

class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(Integer, ForeignKey('assets.id'), nullable=False)
    user_name = Column(String, nullable=False) # The system user performing the action
    assignee = Column(String) # Who the asset is assigned to (e.g., employee name)
    action = Column(String, nullable=False) # 'CHECKOUT', 'CHECKIN', 'CREATE', 'UPDATE'
    timestamp = Column(DateTime, default=datetime.now)

    # Relationship to Asset
    asset = relationship("Asset", back_populates="transactions")

class Asset(Base):
    __tablename__ = 'assets'

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_type = Column(String)
    make = Column(String)
    model = Column(String)
    serial_number = Column(String, unique=True, nullable=False)
    stock_number = Column(String)
    itec_account = Column(String)
    aqs_price = Column(Float)
    building = Column(String, nullable=False)
    room = Column(String, nullable=False)
    classification = Column(String)
    rack = Column(String)
    row = Column(String)
    table_num = Column(String)
    assigned_to = Column(String)
    tags = Column(String)
    date_added = Column(String)
    last_modified = Column(String)
    last_scanned = Column(String)

    # Relationship to Transactions
    transactions = relationship("Transaction", order_by=Transaction.id, back_populates="asset")

    # Helper to maintain compatibility with your current views.py (which expects tuples)
    def to_tuple(self):
        return (
            self.id, self.device_type, self.make, self.model, self.serial_number,
            self.stock_number, self.itec_account, self.aqs_price, self.building,
            self.room, self.classification, self.rack, self.row, self.table_num,
            self.assigned_to, self.tags, self.date_added, self.last_modified,
            self.last_scanned
        )

# --- 3. DATABASE CONTROLLER ---
class Database:
    def __init__(self):
        # Connect to DB (check_same_thread=False is needed for Streamlit)
        self.engine = create_engine(
            f'sqlite:///{config.DB_NAME}', 
            connect_args={'check_same_thread': False}
        )
        Base.metadata.create_all(self.engine)
        
        # Create a thread-safe session factory
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        
        # Initialize Admin
        self.create_default_admin()

    def get_session(self):
        """Returns a new session instance"""
        return self.Session()

    def create_default_admin(self):
        session = self.get_session()
        if session.query(User).count() == 0:
            password = "admin123"
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            admin = User(
                username="admin", 
                password_hash=hashed_password, 
                role="Admin", 
                scope=config.SCOPE_ADMIN
            )
            session.add(admin)
            session.commit()
        session.close()

    # --- USER MANAGEMENT ---
    def verify_user(self, username, password):
        session = self.get_session()
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        user = session.query(User).filter_by(username=username, password_hash=hashed_password).first()
        
        # Return tuple format for existing app compatibility: (id, username, password, role, scope)
        result = (user.id, user.username, user.password_hash, user.role, user.scope) if user else None
        session.close()
        return result

    def add_user(self, username, password, role="User", scope="Read Only"):
        session = self.get_session()
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        # Check if exists
        if session.query(User).filter_by(username=username).first():
            session.close()
            return False
            
        new_user = User(username=username, password_hash=hashed_password, role=role, scope=scope)
        session.add(new_user)
        session.commit()
        session.close()
        return True

    def get_all_users(self):
        session = self.get_session()
        users = session.query(User).all()
        # Convert to list of tuples for views.py compatibility
        result = [(u.id, u.username, u.role, u.scope) for u in users]
        session.close()
        return result

    def update_user_password(self, user_id, new_password):
        session = self.get_session()
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.password_hash = hashlib.sha256(new_password.encode()).hexdigest()
            session.commit()
        session.close()

    def delete_user(self, user_id):
        session = self.get_session()
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            session.delete(user)
            session.commit()
        session.close()

    # --- ASSET MANAGEMENT ---
    def add_asset(self, data):
        # Data is a tuple from the View. We need to map it to the Object.
        # Order: Type, Make, Model, Serial, Stock, ITEC, Price, Build, Room, Class, Rack, Row, Table, Assign, Tags, Added, Mod, Scanned
        session = self.get_session()
        try:
            asset = Asset(
                device_type=data[0], make=data[1], model=data[2], serial_number=data[3],
                stock_number=data[4], itec_account=data[5], aqs_price=data[6],
                building=data[7], room=data[8], classification=data[9],
                rack=data[10], row=data[11], table_num=data[12], assigned_to=data[13],
                tags=data[14], date_added=data[15], last_modified=data[16], last_scanned=data[17]
            )
            session.add(asset)
            session.commit()
            return asset.id
        except Exception:
            session.rollback()
            return None
        finally:
            session.close()

    def get_all_assets(self, tag_filter=None, search_query=None):
        session = self.get_session()
        query = session.query(Asset)

        if tag_filter and tag_filter != "All":
            query = query.filter(Asset.tags.like(f"%{tag_filter}%"))

        if search_query:
            terms = search_query.split()
            for term in terms:
                # SQLAlchemy OR filter
                term_filter = f"%{term}%"
                query = query.filter(or_(
                    Asset.make.ilike(term_filter),
                    Asset.model.ilike(term_filter),
                    Asset.serial_number.ilike(term_filter),
                    Asset.device_type.ilike(term_filter),
                    Asset.assigned_to.ilike(term_filter),
                    Asset.building.ilike(term_filter)
                ))

        query = query.order_by(Asset.id.desc())
        assets = query.all()
        
        # Convert to Tuples for Views
        results = [a.to_tuple() for a in assets]
        session.close()
        return results

    def get_asset_by_serial(self, serial):
        session = self.get_session()
        asset = session.query(Asset).filter_by(serial_number=serial).first()
        result = asset.to_tuple() if asset else None
        session.close()
        return result

    def update_scan_time(self, serial):
        session = self.get_session()
        asset = session.query(Asset).filter_by(serial_number=serial).first()
        if asset:
            asset.last_scanned = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            session.commit()
        session.close()

    def update_asset(self, asset_id, data):
        session = self.get_session()
        asset = session.query(Asset).filter_by(id=asset_id).first()
        if asset:
            try:
                asset.device_type = data[0]
                asset.make = data[1]
                asset.model = data[2]
                asset.serial_number = data[3]
                asset.stock_number = data[4]
                asset.itec_account = data[5]
                asset.aqs_price = data[6]
                asset.building = data[7]
                asset.room = data[8]
                asset.classification = data[9]
                asset.rack = data[10]
                asset.row = data[11]
                asset.table_num = data[12]
                asset.assigned_to = data[13]
                asset.tags = data[14]
                asset.last_modified = data[15]
                
                session.commit()
                return True
            except Exception:
                session.rollback()
                return False
            finally:
                session.close()
        return False

    def delete_asset(self, asset_id):
        session = self.get_session()
        asset = session.query(Asset).filter_by(id=asset_id).first()
        if asset:
            session.delete(asset)
            session.commit()
        session.close()

    # --- TRANSACTION MANAGEMENT ---
    def add_transaction(self, asset_id, user_name, action, assignee=None):
        session = self.get_session()
        try:
            # 1. Log the transaction
            trans = Transaction(
                asset_id=asset_id,
                user_name=user_name,
                action=action,
                assignee=assignee,
                timestamp=datetime.now()
            )
            session.add(trans)

            # 2. Update the Asset status automatically
            asset = session.query(Asset).filter_by(id=asset_id).first()
            if asset:
                if action == "CHECKOUT":
                    asset.assigned_to = assignee
                elif action == "CHECKIN":
                    asset.assigned_to = "Available" # or None/Empty string
                
                # Update modification time
                asset.last_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            session.commit()
            return True
        except Exception as e:
            print(f"Transaction Error: {e}")
            session.rollback()
            return False
        finally:
            session.close()

    def get_asset_history(self, asset_id):
        """Returns list of transactions for a specific asset"""
        session = self.get_session()
        transactions = session.query(Transaction).filter_by(asset_id=asset_id).order_by(Transaction.timestamp.desc()).all()
        
        # Convert to list of dicts for View
        history = []
        for t in transactions:
            history.append({
                "Date": t.timestamp.strftime("%Y-%m-%d %H:%M"),
                "Action": t.action,
                "User": t.user_name,
                "Assignee": t.assignee if t.assignee else "-"
            })
        session.close()
        return history

    # --- STATISTICS & UTILS ---
    def get_unique_tags(self):
        session = self.get_session()
        # Retrieve just the tags column
        results = session.query(Asset.tags).filter(Asset.tags != None).all()
        unique_tags = set()
        for row in results:
            if row[0]:
                tags = [t.strip() for t in row[0].split(',')]
                unique_tags.update(tags)
        session.close()
        return sorted(list(unique_tags))

    def get_existing_types(self):
        session = self.get_session()
        results = session.query(Asset.device_type).distinct().all()
        session.close()
        return [r[0] for r in results if r[0]]

    def get_stats(self):
        session = self.get_session()
        total = session.query(Asset).count()
        
        # Calculate sum of price
        value_result = session.query(Asset.aqs_price).all()
        value = sum(r[0] for r in value_result if r[0])
        
        types = session.query(Asset.device_type).distinct().count()
        session.close()
        return total, value, types