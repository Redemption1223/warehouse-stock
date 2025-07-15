import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime
import io
import uuid
import hashlib

# User Management
def init_user_database():
    """Initialize user management system"""
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        full_name TEXT,
        created_date TEXT,
        last_login TEXT
    )''')
    
    # Create default users if not exist
    users_exist = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if users_exist == 0:
        # Default users with new admin role
        manager_hash = hashlib.sha256("manager123".encode()).hexdigest()
        boss_hash = hashlib.sha256("boss123".encode()).hexdigest()
        viewer_hash = hashlib.sha256("viewer123".encode()).hexdigest()
        admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
        
        default_users = [
            ("warehouse_manager", manager_hash, "warehouse_manager", "Warehouse Manager", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("boss", boss_hash, "boss", "Boss/Owner", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("viewer", viewer_hash, "viewer", "Branch Viewer", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("admin", admin_hash, "admin", "Stock Admin", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        ]
        
        c.executemany("INSERT INTO users (username, password_hash, role, full_name, created_date) VALUES (?, ?, ?, ?, ?)", 
                     default_users)
    
    conn.commit()
    conn.close()

def authenticate_user(username, password):
    """Authenticate user and return role"""
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    result = c.execute("SELECT role, full_name FROM users WHERE username = ? AND password_hash = ?", 
                      (username, password_hash)).fetchone()
    
    if result:
        # Update last login
        c.execute("UPDATE users SET last_login = ? WHERE username = ?", 
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username))
        conn.commit()
    
    conn.close()
    return result

def check_permission(required_role):
    """Check if current user has required permission"""
    if 'user_role' not in st.session_state:
        return False
    
    user_role = st.session_state.user_role
    
    # Permission hierarchy
    roles_hierarchy = {
        'warehouse_manager': 4,  # Full access
        'boss': 3,              # Read all, limited write
        'admin': 2,             # Final stock updates only
        'viewer': 1             # Final products by branch only
    }
    
    required_level = roles_hierarchy.get(required_role, 0)
    user_level = roles_hierarchy.get(user_role, 0)
    
    return user_level >= required_level

# Database setup with branches
def init_database():
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    
    # Branches table
    c.execute('''CREATE TABLE IF NOT EXISTS branches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        branch_code TEXT UNIQUE NOT NULL,
        branch_name TEXT NOT NULL,
        location TEXT,
        manager_name TEXT,
        contact_info TEXT,
        created_date TEXT,
        is_active INTEGER DEFAULT 1
    )''')
    
    # Items table with branch support
    c.execute('''CREATE TABLE IF NOT EXISTS items (
        id TEXT NOT NULL,
        branch_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        unit TEXT NOT NULL,
        current_stock REAL DEFAULT 0,
        min_stock REAL DEFAULT 0,
        cost_per_unit REAL DEFAULT 0,
        location TEXT DEFAULT 'Main',
        warehouse_area TEXT DEFAULT 'General',
        created_date TEXT,
        created_by TEXT,
        PRIMARY KEY (id, branch_id),
        FOREIGN KEY (branch_id) REFERENCES branches (id)
    )''')
    
    # Bill of Materials table
    c.execute('''CREATE TABLE IF NOT EXISTS bom (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        final_product_id TEXT NOT NULL,
        ingredient_id TEXT NOT NULL,
        quantity_required REAL NOT NULL,
        branch_id INTEGER NOT NULL,
        FOREIGN KEY (final_product_id) REFERENCES items (id),
        FOREIGN KEY (ingredient_id) REFERENCES items (id),
        FOREIGN KEY (branch_id) REFERENCES branches (id)
    )''')
    
    # Stock movements table with branch transfers
    c.execute('''CREATE TABLE IF NOT EXISTS stock_movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id TEXT NOT NULL,
        branch_id INTEGER NOT NULL,
        movement_type TEXT NOT NULL,
        quantity REAL NOT NULL,
        reference TEXT,
        batch_nr TEXT,
        date_time TEXT,
        user_id TEXT,
        from_branch_id INTEGER,
        to_branch_id INTEGER,
        FOREIGN KEY (item_id) REFERENCES items (id),
        FOREIGN KEY (branch_id) REFERENCES branches (id),
        FOREIGN KEY (from_branch_id) REFERENCES branches (id),
        FOREIGN KEY (to_branch_id) REFERENCES branches (id)
    )''')
    
    # Warehouse areas table
    c.execute('''CREATE TABLE IF NOT EXISTS warehouse_areas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        area_name TEXT UNIQUE NOT NULL,
        description TEXT,
        capacity REAL,
        created_date TEXT
    )''')
    
    # Create default branches
    default_branches = [
        ("MAIN", "Main Warehouse", "Johannesburg", "Main Manager", "011-xxx-xxxx"),
        ("CPT", "Cape Town Branch", "Cape Town", "Cape Town Manager", "021-xxx-xxxx"),
        ("DBN", "Durban Branch", "Durban", "Durban Manager", "031-xxx-xxxx")
    ]
    
    for branch_code, branch_name, location, manager, contact in default_branches:
        c.execute("""INSERT OR IGNORE INTO branches 
                     (branch_code, branch_name, location, manager_name, contact_info, created_date) 
                     VALUES (?, ?, ?, ?, ?, ?)""",
                 (branch_code, branch_name, location, manager, contact, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    # Create default warehouse areas
    default_areas = [
        ("Raw Materials Storage", "Storage area for chemical compounds and powders"),
        ("Components Storage", "Buckets, stickers, nozzles, and extinguisher bodies"),
        ("Final Products", "Completed fire extinguishers ready for dispatch"),
        ("Quality Control", "Items pending quality inspection"),
        ("Dispatch Area", "Items ready for shipping")
    ]
    
    for area_name, description in default_areas:
        c.execute("INSERT OR IGNORE INTO warehouse_areas (area_name, description, created_date) VALUES (?, ?, ?)",
                 (area_name, description, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    conn.commit()
    conn.close()

def get_all_branches(active_only=True):
    """Get all branches"""
    conn = sqlite3.connect('inventory.db')
    query = "SELECT * FROM branches"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY branch_name"
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def add_branch(branch_code, branch_name, location="", manager_name="", contact_info=""):
    """Add new branch"""
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    c.execute("""INSERT INTO branches (branch_code, branch_name, location, manager_name, contact_info, created_date)
                 VALUES (?, ?, ?, ?, ?, ?)""",
              (branch_code, branch_name, location, manager_name, contact_info, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def load_sample_data():
    """Load sample data into main branch only"""
    
    # Check if data already exists
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM items")
    if c.fetchone()[0] > 0:
        conn.close()
        return  # Data already loaded
    
    # Get main branch ID
    main_branch = c.execute("SELECT id FROM branches WHERE branch_code = 'MAIN'").fetchone()
    if not main_branch:
        conn.close()
        return
    
    main_branch_id = main_branch[0]
    conn.close()
    
    # Raw Materials for main branch
    raw_materials = [
        ("LIG001", "LIGNO", "Raw Material", "kg", 300, 1000, "Raw Materials Storage"),
        ("KOH001", "KOH", "Raw Material", "kg", 40, 100, "Raw Materials Storage"),
        ("ETH001", "ETHYLENE GLYCOL", "Raw Material", "kg", 64, 20, "Raw Materials Storage"),
        ("ACE001", "ACETIC ACID", "Raw Material", "kg", 0, 300, "Raw Materials Storage"),
        ("FOR001", "FORMIC ACID", "Raw Material", "kg", 678.5, 250, "Raw Materials Storage"),
        ("BEN001", "BENTONITE CLAY", "Raw Material", "kg", 40, 100, "Raw Materials Storage"),
        ("XGU001", "X GUM", "Raw Material", "kg", 17.8, 25, "Raw Materials Storage"),
        ("PRO001", "PROPYLENE GLYCOL", "Raw Material", "kg", 30.7, 2, "Raw Materials Storage"),
        ("COR001", "CORNSTARCH", "Raw Material", "kg", 10.1, 25, "Raw Materials Storage"),
    ]
    
    # Pre-Final Components
    prefinal_components = [
        ("LIB001", "LITHIUM BLACK POWDER", "Pre-Final", "kg", 2000, 5, "Components Storage"),
        ("2LB001", "2L BOXES", "Pre-Final", "pieces", 325, 50, "Components Storage"),
        ("6LB001", "6L BOXES", "Pre-Final", "pieces", 146, 50, "Components Storage"),
        ("9LB001", "9L BOXES", "Pre-Final", "pieces", 2, 50, "Components Storage"),
        ("20B001", "20KG BUCKETS", "Pre-Final", "pieces", 65, 10, "Components Storage"),
        ("2LE001", "2L EMPTY EXTINGUISHERS", "Pre-Final", "pieces", 9, 10, "Components Storage"),
        ("6LE001", "6L EMPTY EXTINGUISHERS", "Pre-Final", "pieces", 26, 1, "Components Storage"),
        ("2LS001", "2L STICKERS", "Pre-Final", "pieces", 144, 50, "Components Storage"),
        ("6LS001", "6L STICKERS", "Pre-Final", "pieces", 516, 50, "Components Storage"),
        ("9LS001", "9L STICKERS", "Pre-Final", "pieces", 522, 50, "Components Storage"),
    ]
    
    # Final Products
    final_products = [
        ("LB9L001", "LITHIUM BLACK 9L", "Final Product", "pieces", 3, 100, "Final Products"),
        ("LB6L001", "LITHIUM BLACK 6L", "Final Product", "pieces", 23, 100, "Final Products"),
        ("LB2L001", "LITHIUM BLACK 2L", "Final Product", "pieces", 0, 50, "Final Products"),
        ("SH20001", "SHIELD 20KG", "Final Product", "pieces", 9, 10, "Final Products"),
        ("CT9L001", "CAPE TOWN 9L", "Final Product", "pieces", 7, 10, "Final Products"),
        ("PT9L001", "PINE TOWN 9L", "Final Product", "pieces", 14, 10, "Final Products"),
    ]
    
    # Insert all data to main branch
    all_items = raw_materials + prefinal_components + final_products
    
    for item_data in all_items:
        item_id, name, category, unit, current_stock, min_stock, warehouse_area = item_data
        add_item(item_id, name, category, unit, current_stock, min_stock, 0, "Main", warehouse_area, main_branch_id, "system")

def add_item(item_id, name, category, unit, current_stock=0, min_stock=0, cost_per_unit=0, location="Main", warehouse_area="General", branch_id=1, created_by="system"):
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO items 
                 (id, branch_id, name, category, unit, current_stock, min_stock, cost_per_unit, location, warehouse_area, created_date, created_by)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (item_id, branch_id, name, category, unit, current_stock, min_stock, cost_per_unit, location, warehouse_area,
               datetime.now().strftime("%Y-%m-%d %H:%M:%S"), created_by))
    conn.commit()
    conn.close()

def get_all_items(user_role=None, branch_id=None):
    conn = sqlite3.connect('inventory.db')
    
    # Build query based on user role and branch
    if user_role == "viewer":
        query = """SELECT i.*, b.branch_name, b.branch_code 
                   FROM items i 
                   JOIN branches b ON i.branch_id = b.id 
                   WHERE i.category = 'Final Product'"""
    elif user_role == "admin":
        query = """SELECT i.*, b.branch_name, b.branch_code 
                   FROM items i 
                   JOIN branches b ON i.branch_id = b.id 
                   WHERE i.category = 'Final Product'"""
    else:
        query = """SELECT i.*, b.branch_name, b.branch_code 
                   FROM items i 
                   JOIN branches b ON i.branch_id = b.id"""
    
    if branch_id:
        query += f" AND i.branch_id = {branch_id}"
    
    query += " ORDER BY b.branch_name, i.category, i.name"
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def transfer_stock_between_branches(item_id, from_branch_id, to_branch_id, quantity, reference="", batch_nr="", invoice_nr="", po_nr="", user_id="system"):
    """Transfer stock between branches - available to warehouse managers and admins"""
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    
    try:
        # Check if item exists in from_branch
        from_item = c.execute("SELECT current_stock FROM items WHERE id = ? AND branch_id = ?", 
                            (item_id, from_branch_id)).fetchone()
        
        if not from_item or from_item[0] < quantity:
            conn.close()
            return False, "Insufficient stock in source branch"
        
        # Check if item exists in to_branch, if not create it
        to_item = c.execute("SELECT current_stock FROM items WHERE id = ? AND branch_id = ?", 
                          (item_id, to_branch_id)).fetchone()
        
        if not to_item:
            # Get item details from source branch
            item_details = c.execute("""SELECT name, category, unit, min_stock, cost_per_unit, location, warehouse_area 
                                       FROM items WHERE id = ? AND branch_id = ?""", 
                                   (item_id, from_branch_id)).fetchone()
            
            if item_details:
                # Create item in destination branch with 0 stock
                c.execute("""INSERT INTO items (id, branch_id, name, category, unit, current_stock, min_stock, 
                           cost_per_unit, location, warehouse_area, created_date, created_by)
                           VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)""",
                         (item_id, to_branch_id, item_details[0], item_details[1], item_details[2], 
                          item_details[3], item_details[4], item_details[5], item_details[6],
                          datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        
        # Update stock in both branches
        c.execute("UPDATE items SET current_stock = current_stock - ? WHERE id = ? AND branch_id = ?", 
                 (quantity, item_id, from_branch_id))
        c.execute("UPDATE items SET current_stock = current_stock + ? WHERE id = ? AND branch_id = ?", 
                 (quantity, item_id, to_branch_id))
        
        # Record movements with enhanced tracking - check if new columns exist first
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Check if the new columns exist
        try:
            c.execute("SELECT invoice_nr FROM stock_movements LIMIT 1")
            has_new_columns = True
        except sqlite3.OperationalError:
            has_new_columns = False
        
        if has_new_columns:
            # Out movement from source branch
            c.execute("""INSERT INTO stock_movements (item_id, branch_id, movement_type, quantity, reference, batch_nr, 
                         invoice_nr, po_nr, date_time, user_id, from_branch_id, to_branch_id)
                         VALUES (?, ?, 'TRANSFER_OUT', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (item_id, from_branch_id, quantity, reference, batch_nr, invoice_nr, po_nr, timestamp, user_id, from_branch_id, to_branch_id))
            
            # In movement to destination branch
            c.execute("""INSERT INTO stock_movements (item_id, branch_id, movement_type, quantity, reference, batch_nr, 
                         invoice_nr, po_nr, date_time, user_id, from_branch_id, to_branch_id)
                         VALUES (?, ?, 'TRANSFER_IN', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (item_id, to_branch_id, quantity, reference, batch_nr, invoice_nr, po_nr, timestamp, user_id, from_branch_id, to_branch_id))
        else:
            # Fall back to old format
            c.execute("""INSERT INTO stock_movements (item_id, branch_id, movement_type, quantity, reference, batch_nr, 
                         date_time, user_id, from_branch_id, to_branch_id)
                         VALUES (?, ?, 'TRANSFER_OUT', ?, ?, ?, ?, ?, ?, ?)""",
                     (item_id, from_branch_id, quantity, reference, batch_nr, timestamp, user_id, from_branch_id, to_branch_id))
            
            c.execute("""INSERT INTO stock_movements (item_id, branch_id, movement_type, quantity, reference, batch_nr, 
                         date_time, user_id, from_branch_id, to_branch_id)
                         VALUES (?, ?, 'TRANSFER_IN', ?, ?, ?, ?, ?, ?, ?)""",
                     (item_id, to_branch_id, quantity, reference, batch_nr, timestamp, user_id, from_branch_id, to_branch_id))
        
        conn.commit()
        conn.close()
        return True, f"Successfully transferred {quantity} units"
        
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Transfer failed: {str(e)}"

def update_stock(item_id, branch_id, quantity, movement_type, reference="", batch_nr="", invoice_nr="", po_nr="", user_id="system"):
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    
    # Update current stock
    if movement_type in ['IN', 'ADJUSTMENT_IN', 'PRODUCTION', 'TRANSFER_IN', 'ADMIN_IN']:
        c.execute("UPDATE items SET current_stock = current_stock + ? WHERE id = ? AND branch_id = ?", 
                 (quantity, item_id, branch_id))
    else:
        c.execute("UPDATE items SET current_stock = current_stock - ? WHERE id = ? AND branch_id = ?", 
                 (quantity, item_id, branch_id))
    
    # Record movement with enhanced tracking - check if new columns exist first
    try:
        c.execute("SELECT invoice_nr FROM stock_movements LIMIT 1")
        has_new_columns = True
    except sqlite3.OperationalError:
        has_new_columns = False
    
    if has_new_columns:
        c.execute('''INSERT INTO stock_movements (item_id, branch_id, movement_type, quantity, reference, batch_nr, invoice_nr, po_nr, date_time, user_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (item_id, branch_id, movement_type, quantity, reference, batch_nr, invoice_nr, po_nr,
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
    else:
        # Fall back to old format
        c.execute('''INSERT INTO stock_movements (item_id, branch_id, movement_type, quantity, reference, batch_nr, date_time, user_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (item_id, branch_id, movement_type, quantity, reference, batch_nr,
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
    
    conn.commit()
    conn.close()

# Login system
def show_login():
    # Hide Streamlit elements on login page
    hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {visibility: hidden;}
    .stDecoration {visibility: hidden;}
    .viewerBadge_container__1QSob {display: none;}
    
    /* Mobile responsive login */
    .main .block-container {
        padding-top: 2rem;
        max-width: 500px;
        margin: 0 auto;
    }
    
    .login-header {
        text-align: center;
        margin-bottom: 2rem;
        padding: 1.5rem;
        background: linear-gradient(135deg, #FF4B4B 0%, #FF6B6B 100%);
        border-radius: 10px;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .login-form {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border: 1px solid #e0e0e0;
    }
    
    @media (max-width: 768px) {
        .main .block-container {
            padding: 1rem;
        }
        .login-header {
            padding: 1rem;
        }
        .login-header h1 {
            font-size: 1.8rem !important;
        }
        .login-header h2 {
            font-size: 1.4rem !important;
        }
    }
    </style>
    """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)
    
    # Professional login header
    st.markdown("""
    <div class="login-header">
        <div style="font-size: 3rem; margin-bottom: 0.5rem;">🔥</div>
        <h1 style="margin: 0; font-size: 2rem;">FLAMEBLOCK</h1>
        <h2 style="margin: 0; font-size: 1.6rem; opacity: 0.9;">MULTI-BRANCH INVENTORY</h2>
        <p style="margin: 0.5rem 0 0 0; font-size: 1rem; opacity: 0.8;">Professional Stock Control Across All Branches</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="login-form">', unsafe_allow_html=True)
    
    with st.form("login_form"):
        st.markdown("#### 🔐 Secure Access")
        username = st.text_input("👤 Username", placeholder="Enter your username")
        password = st.text_input("🔒 Password", type="password", placeholder="Enter your password")
        submit = st.form_submit_button("🚀 Access System", use_container_width=True, type="primary")
        
        if submit:
            if username and password:
                result = authenticate_user(username, password)
                if result:
                    role, full_name = result
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.user_role = role
                    st.session_state.full_name = full_name
                    st.success(f"✅ Welcome {full_name}!")
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials. Please try again.")
            else:
                st.error("❌ Please enter both username and password")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Show login info
    st.markdown("---")
    st.markdown("**🔑 Default Login Details:**")
    st.markdown("""
    - **Warehouse Manager**: `warehouse_manager` / `manager123`
    - **Boss/Owner**: `boss` / `boss123`  
    - **Branch Viewer**: `viewer` / `viewer123`
    - **Stock Admin**: `admin` / `admin123` *(Can update & transfer final products)*
    """)

# Mobile-friendly navigation
def show_mobile_navigation(user_role):
    """Mobile-friendly navigation system based on user role"""
    
    # Define menu items based on user role
    if user_role == "viewer":
        menu_items = [
            ("🏪", "Branches", "branch_viewer"),
            ("📦", "Products", "final_products_view")
        ]
    elif user_role == "admin":
        menu_items = [
            ("📊", "Dashboard", "admin_dashboard"),
            ("🔄", "Update Stock", "admin_stock_update"),
            ("🔀", "Transfers", "admin_stock_transfers"),
            ("📈", "Movements", "admin_stock_movements"),
            ("🏪", "All Branches", "admin_branch_view")
        ]
    elif user_role == "boss":
        menu_items = [
            ("📊", "Dashboard", "management_dashboard"),
            ("🏪", "Branches", "branch_overview"),
            ("📦", "Stock View", "complete_stock_view"),
            ("📈", "Transfers", "branch_transfers"),
            ("🔄", "Movements", "boss_stock_movements"),
            ("📋", "Reports", "management_reports")
        ]
    else:  # warehouse_manager
        menu_items = [
            ("📊", "Dashboard", "dashboard"),
            ("🏪", "Branches", "branch_management"),
            ("📦", "Stock", "stock_management"),
            ("🔄", "Transfers", "stock_transfers"),
            ("📈", "Movements", "manager_stock_movements"),
            ("🏭", "Production", "production_center"),
            ("⚙️", "Items", "item_management"),
            ("📋", "Reports", "reports"),
            ("👥", "Users", "user_management")
        ]
    
    # Initialize session state for current page
    if 'current_page' not in st.session_state:
        st.session_state.current_page = menu_items[0][2]
    
    # Mobile navigation style
    nav_style = """
    <style>
    .mobile-nav {
        background: linear-gradient(90deg, #FF4B4B 0%, #FF6B6B 100%);
        padding: 0.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .nav-button {
        display: inline-block;
        margin: 0.2rem;
        padding: 0.5rem 0.8rem;
        background: rgba(255,255,255,0.2);
        border: none;
        border-radius: 6px;
        color: white;
        text-decoration: none;
        font-size: 0.9rem;
        cursor: pointer;
        transition: background 0.3s;
    }
    
    .nav-button:hover {
        background: rgba(255,255,255,0.3);
    }
    
    .nav-button.active {
        background: rgba(255,255,255,0.9);
        color: #FF4B4B;
        font-weight: bold;
    }
    
    @media (max-width: 768px) {
        .nav-button {
            font-size: 0.8rem;
            padding: 0.4rem 0.6rem;
            margin: 0.1rem;
        }
    }
    </style>
    """
    
    st.markdown(nav_style, unsafe_allow_html=True)
    
    # Create navigation buttons
    st.markdown('<div class="mobile-nav">', unsafe_allow_html=True)
    
    cols = st.columns(len(menu_items))
    
    for i, (icon, label, page_key) in enumerate(menu_items):
        with cols[i]:
            # Shorter label for mobile
            mobile_label = label[:8] + "..." if len(label) > 8 else label
            button_text = f"{icon}\n{mobile_label}"
            
            if st.button(button_text, key=f"nav_{page_key}", use_container_width=True):
                st.session_state.current_page = page_key
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    return st.session_state.current_page

# Main application
def main():
    st.set_page_config(
        page_title="🔥 FLAMEBLOCK MULTI-BRANCH INVENTORY",
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items={
            'Get Help': None,
            'Report a bug': None,
            'About': None
        }
    )
    
    # Hide Streamlit style elements
    hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {visibility: hidden;}
    .stDecoration {visibility: hidden;}
    .stActionButton {visibility: hidden;}
    .stToolbar {visibility: hidden;}
    .viewerBadge_container__1QSob {display: none;}
    
    .stApp > header {
        background-color: transparent;
    }
    
    .main .block-container {
        padding-top: 1rem;
        max-width: 100%;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    /* Hide dataframe toolbars */
    .stDataFrame [data-testid="stElementToolbar"] {
        display: none;
    }
    
    /* Mobile responsive adjustments */
    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }
        
        .stSelectbox label, .stTextInput label, .stNumberInput label {
            font-size: 0.9rem;
        }
        
        .element-container {
            margin-bottom: 0.5rem;
        }
    }
    
    /* Professional styling */
    .stSelectbox label, .stTextInput label, .stNumberInput label {
        font-weight: 600;
        color: #262730;
    }
    </style>
    """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)
    
    # Initialize databases
    init_database()
    init_user_database()
    
    # Check authentication
    if not st.session_state.get('authenticated', False):
        show_login()
        return
    
    # Check if database is empty and load sample data
    items_df = get_all_items()
    if items_df.empty:
        with st.spinner("Setting up your multi-branch inventory system..."):
            load_sample_data()
            st.success("✅ Loaded your existing inventory data into Main Branch!")
            st.rerun()
    
    # Header with user info and logout
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("""
        <div style="display: flex; align-items: center; margin-bottom: 1rem;">
            <div style="font-size: 2rem; margin-right: 0.5rem;">🔥</div>
            <div>
                <h1 style="margin: 0; color: #262730; font-size: 1.8rem;">FLAMEBLOCK MULTI-BRANCH</h1>
                <p style="margin: 0; color: #666; font-size: 0.8rem;">Multi-Branch Inventory Management</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        user_role = st.session_state.user_role
        role_display = {
            'warehouse_manager': '👨‍💼 Warehouse Manager',
            'boss': '👔 Boss/Owner', 
            'viewer': '👁️ Branch Viewer',
            'admin': '🔧 Stock Admin'
        }
        st.markdown(f"**{role_display.get(user_role, user_role)} - {st.session_state.full_name}**")
    
    with col2:
        if st.button("🚪 Logout", type="secondary", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    # Mobile-friendly navigation
    current_page = show_mobile_navigation(user_role)
    
    # Route to appropriate page based on user role
    if current_page == "branch_viewer":
        show_branch_viewer()
    elif current_page == "final_products_view":
        show_final_products_view()
    elif current_page == "admin_dashboard":
        show_admin_dashboard()
    elif current_page == "admin_stock_update":
        show_admin_stock_update()
    elif current_page == "admin_stock_transfers":
        show_admin_stock_transfers()
    elif current_page == "admin_stock_movements":
        show_admin_stock_movements()
    elif current_page == "admin_branch_view":
        show_admin_branch_view()
    elif current_page == "management_dashboard":
        show_management_dashboard()
    elif current_page == "branch_overview":
        show_branch_overview()
    elif current_page == "complete_stock_view":
        show_complete_stock_view()
    elif current_page == "branch_transfers":
        show_branch_transfers()
    elif current_page == "boss_stock_movements":
        show_boss_stock_movements()
    elif current_page == "management_reports":
        show_management_reports()
    elif current_page == "dashboard":
        show_dashboard()
    elif current_page == "branch_management":
        show_branch_management()
    elif current_page == "stock_management":
        show_stock_management()
    elif current_page == "stock_transfers":
        show_stock_transfers()
    elif current_page == "manager_stock_movements":
        show_manager_stock_movements()
    elif current_page == "production_center":
        show_production_center()
    elif current_page == "item_management":
        show_item_management()
    elif current_page == "reports":
        show_reports()
    elif current_page == "user_management":
        show_user_management()

# NEW VIEWER PAGES
def show_branch_viewer():
    """Branch selection for viewers - final products only, no quantities"""
    st.header("🏪 Branch Selection")
    
    branches_df = get_all_branches()
    
    if not branches_df.empty:
        # Branch selection
        selected_branch_id = st.selectbox(
            "🏪 Select Branch to View",
            options=branches_df['id'].tolist(),
            format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]} - {branches_df[branches_df['id']==x]['location'].iloc[0]}"
        )
        
        if selected_branch_id:
            branch_info = branches_df[branches_df['id'] == selected_branch_id].iloc[0]
            
            # Branch info card
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #FF4B4B 0%, #FF6B6B 100%); 
                        padding: 1rem; border-radius: 10px; color: white; margin-bottom: 1rem;">
                <h3 style="margin: 0;">🏪 {branch_info['branch_name']}</h3>
                <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">📍 {branch_info['location']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Get final products for this branch
            items_df = get_all_items("viewer", selected_branch_id)
            
            if not items_df.empty:
                st.subheader("🔥 Available Products")
                
                # Show products without quantities - just availability
                for _, item in items_df.iterrows():
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        # Show availability status without quantities
                        if item['current_stock'] > 0:
                            status = "✅ Available"
                            status_color = "green"
                        else:
                            status = "❌ Out of Stock"
                            status_color = "red"
                        
                        st.markdown(f"**{item['name']}**")
                    
                    with col2:
                        st.markdown(f"<span style='color: {status_color}'>{status}</span>", unsafe_allow_html=True)
                
                # Summary counts
                st.markdown("---")
                col1, col2 = st.columns(2)
                
                with col1:
                    available = len(items_df[items_df['current_stock'] > 0])
                    st.metric("✅ Available Products", available)
                
                with col2:
                    out_of_stock = len(items_df[items_df['current_stock'] <= 0])
                    st.metric("❌ Out of Stock", out_of_stock)
            
            else:
                st.info(f"No final products found in {branch_info['branch_name']}")
    else:
        st.error("No branches configured in the system.")

def show_final_products_view():
    """Alternative view showing all branches with final products"""
    st.header("📦 All Products Across Branches")
    
    branches_df = get_all_branches()
    items_df = get_all_items("viewer")
    
    if not branches_df.empty and not items_df.empty:
        # Group by branch
        for _, branch in branches_df.iterrows():
            branch_items = items_df[items_df['branch_id'] == branch['id']]
            
            if not branch_items.empty:
                with st.expander(f"🏪 {branch['branch_name']} - {branch['location']} ({len(branch_items)} products)"):
                    for _, item in branch_items.iterrows():
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.write(f"🔥 **{item['name']}**")
                        
                        with col2:
                            if item['current_stock'] > 0:
                                st.success("✅ Available")
                            else:
                                st.error("❌ Out of Stock")

# NEW ADMIN PAGES
def show_admin_dashboard():
    """Enhanced dashboard for admin users - final products with quantities by branch"""
    st.header("🔧 Stock Admin Dashboard")
    
    if not check_permission('admin'):
        st.error("❌ Access denied.")
        return
    
    branches_df = get_all_branches()
    items_df = get_all_items("admin")
    
    if not items_df.empty:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_products = len(items_df)
            st.metric("Total Final Products", total_products)
        
        with col2:
            total_branches = len(branches_df)
            st.metric("Active Branches", total_branches)
        
        with col3:
            total_stock = items_df['current_stock'].sum()
            st.metric("Total Stock Units", int(total_stock))
        
        with col4:
            out_of_stock = len(items_df[items_df['current_stock'] <= 0])
            st.metric("Out of Stock Items", out_of_stock)
        
        # Stock by Branch Overview
        st.subheader("📊 Stock Overview by Branch")
        
        branch_overview = []
        for _, branch in branches_df.iterrows():
            branch_items = items_df[items_df['branch_id'] == branch['id']]
            if not branch_items.empty:
                total_stock = branch_items['current_stock'].sum()
                in_stock_count = len(branch_items[branch_items['current_stock'] > 0])
                out_of_stock_count = len(branch_items[branch_items['current_stock'] <= 0])
                low_stock_count = len(branch_items[(branch_items['current_stock'] <= branch_items['min_stock']) & (branch_items['current_stock'] > 0)])
                
                # Status indicator
                if out_of_stock_count > 0:
                    status = f"🚨 {out_of_stock_count} Critical"
                elif low_stock_count > 0:
                    status = f"⚠️ {low_stock_count} Low"
                else:
                    status = "✅ Good"
                
                branch_overview.append({
                    'Branch': branch['branch_name'],
                    'Location': branch['location'],
                    'Total Units': int(total_stock),
                    'Products': len(branch_items),
                    'In Stock': in_stock_count,
                    'Out of Stock': out_of_stock_count,
                    'Status': status
                })
        
        if branch_overview:
            overview_df = pd.DataFrame(branch_overview)
            st.dataframe(overview_df, use_container_width=True)
        
        # Critical items across all branches
        critical_items = items_df[items_df['current_stock'] <= 0]
        if not critical_items.empty:
            st.subheader("🚨 Critical Items (Out of Stock)")
            critical_display = critical_items[['branch_name', 'name', 'current_stock', 'min_stock', 'unit']].copy()
            critical_display.columns = ['Branch', 'Product', 'Current', 'Min Required', 'Unit']
            st.dataframe(critical_display, use_container_width=True)
        
        # Low stock items
        low_stock_items = items_df[(items_df['current_stock'] <= items_df['min_stock']) & (items_df['current_stock'] > 0)]
        if not low_stock_items.empty:
            st.subheader("⚠️ Low Stock Items")
            low_stock_display = low_stock_items[['branch_name', 'name', 'current_stock', 'min_stock', 'unit']].copy()
            low_stock_display.columns = ['Branch', 'Product', 'Current', 'Min Required', 'Unit']
            st.dataframe(low_stock_display, use_container_width=True)
        
        if critical_items.empty and low_stock_items.empty:
            st.success("✅ All final products have adequate stock levels across all branches!")
    else:
        st.info("📦 No final products found in the system.")
        st.markdown("""
        **To get started:**
        - Ask warehouse manager to add final products
        - Transfer items from other branches
        - Check if products exist in the main warehouse
        """)

def show_admin_stock_update():
    """Admin interface for updating final product stock only"""
    st.header("🔄 Update Final Product Stock")
    
    if not check_permission('admin'):
        st.error("❌ Access denied.")
        return
    
    branches_df = get_all_branches()
    
    # Branch selection
    col1, col2 = st.columns(2)
    
    with col1:
        selected_branch_id = st.selectbox(
            "🏪 Select Branch",
            options=branches_df['id'].tolist(),
            format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]}"
        )
    
    if selected_branch_id:
        branch_info = branches_df[branches_df['id'] == selected_branch_id].iloc[0]
        
        with col2:
            st.info(f"📍 {branch_info['branch_name']} - {branch_info['location']}")
        
        # Get final products for this branch
        items_df = get_all_items("admin", selected_branch_id)
        
        if not items_df.empty:
            # Show current stock levels
            st.subheader("📦 Current Stock Levels")
            
            display_df = items_df[['name', 'current_stock', 'unit']].copy()
            display_df.columns = ['Product', 'Current Stock', 'Unit']
            st.dataframe(display_df, use_container_width=True)
            
            # Stock update form
            st.subheader("🔄 Update Stock")
            
            with st.form("admin_stock_update"):
                col1, col2 = st.columns(2)
                
                with col1:
                    selected_item = st.selectbox(
                        "Product",
                        options=items_df['id'].tolist(),
                        format_func=lambda x: f"{items_df[items_df['id']==x]['name'].iloc[0]}"
                    )
                    
                    update_type = st.selectbox("Update Type", ["SET", "ADD", "SUBTRACT"])
                    quantity = st.number_input("Quantity", min_value=0.0, value=0.0)
                
                with col2:
                    reference = st.text_input("Reference/Reason", placeholder="Stock count, delivery, etc.")
                    batch_nr = st.text_input("Batch Number", placeholder="Optional batch reference")
                    
                    col2a, col2b = st.columns(2)
                    with col2a:
                        invoice_nr = st.text_input("Invoice #", placeholder="Optional")
                    with col2b:
                        po_nr = st.text_input("PO #", placeholder="Optional")
                
                submitted = st.form_submit_button("🔄 Update Stock", type="primary", use_container_width=True)
                
                if submitted:
                    if selected_item and quantity >= 0:
                        current_item = items_df[items_df['id'] == selected_item].iloc[0]
                        
                        if update_type == "SET":
                            # Set absolute value
                            conn = sqlite3.connect('inventory.db')
                            c = conn.cursor()
                            c.execute("UPDATE items SET current_stock = ? WHERE id = ? AND branch_id = ?", 
                                     (quantity, selected_item, selected_branch_id))
                            
                            # Record movement with enhanced tracking
                            movement_type = "ADMIN_SET"
                            c.execute('''INSERT INTO stock_movements (item_id, branch_id, movement_type, quantity, reference, batch_nr, invoice_nr, po_nr, date_time, user_id)
                                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                      (selected_item, selected_branch_id, movement_type, quantity, 
                                       f"SET to {quantity} - {reference}", batch_nr, invoice_nr, po_nr,
                                       datetime.now().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.username))
                            
                            conn.commit()
                            conn.close()
                            
                            st.success(f"✅ Set {current_item['name']} stock to {quantity} {current_item['unit']}")
                            st.rerun()
                        
                        elif update_type == "ADD":
                            if quantity > 0:
                                update_stock(selected_item, selected_branch_id, quantity, 'ADMIN_IN', 
                                            f"Admin added {quantity} - {reference}", batch_nr, invoice_nr, po_nr, st.session_state.username)
                                new_stock = current_item['current_stock'] + quantity
                                st.success(f"✅ Added {quantity} {current_item['unit']} to {current_item['name']} (New total: {new_stock})")
                                st.rerun()
                            else:
                                st.error("❌ Quantity must be greater than 0 for ADD operation")
                        
                        elif update_type == "SUBTRACT":
                            if quantity > 0:
                                if current_item['current_stock'] >= quantity:
                                    update_stock(selected_item, selected_branch_id, quantity, 'ADMIN_OUT', 
                                                f"Admin subtracted {quantity} - {reference}", batch_nr, invoice_nr, po_nr, st.session_state.username)
                                    new_stock = current_item['current_stock'] - quantity
                                    st.success(f"✅ Subtracted {quantity} {current_item['unit']} from {current_item['name']} (New total: {new_stock})")
                                    st.rerun()
                                else:
                                    st.error(f"❌ Cannot subtract {quantity}. Only {current_item['current_stock']} available.")
                            else:
                                st.error("❌ Quantity must be greater than 0 for SUBTRACT operation")
                    else:
                        st.error("❌ Please enter a valid quantity (0 or greater)")
        else:
            st.warning(f"⚠️ No final products found in **{branch_info['branch_name']}**")
            st.info("💡 To add final products to this branch:")
            st.markdown("""
            1. **Transfer from another branch** (if you have final products elsewhere)
            2. **Add new items** using the Item Management section
            3. **Produce items** using the Production Center
            """)

def show_admin_stock_transfers():
    """Admin interface for transferring final product stock between branches"""
    st.header("🔀 Transfer Final Products Between Branches")
    
    if not check_permission('admin'):
        st.error("❌ Access denied.")
        return
    
    branches_df = get_all_branches()
    
    if len(branches_df) < 2:
        st.warning("⚠️ Need at least 2 branches to perform transfers.")
        return
    
    st.info("🔧 **Admin Transfer**: You can transfer final products between branches")
    
    # Branch selection
    col1, col2 = st.columns(2)
    
    with col1:
        from_branch_id = st.selectbox(
            "📤 From Branch",
            options=branches_df['id'].tolist(),
            format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]}"
        )
    
    with col2:
        to_branch_options = [bid for bid in branches_df['id'].tolist() if bid != from_branch_id]
        to_branch_id = st.selectbox(
            "📥 To Branch",
            options=to_branch_options,
            format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]}"
        ) if to_branch_options else None
    
    if from_branch_id and to_branch_id:
        # Get final products from source branch
        from_items_df = get_all_items("admin", from_branch_id)
        available_items = from_items_df[from_items_df['current_stock'] > 0]
        
        if not available_items.empty:
            from_branch_name = branches_df[branches_df['id'] == from_branch_id]['branch_name'].iloc[0]
            to_branch_name = branches_df[branches_df['id'] == to_branch_id]['branch_name'].iloc[0]
            
            st.success(f"📦 Available final products in **{from_branch_name}**: {len(available_items)} items")
            
            # Transfer form
            with st.form("admin_transfer_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    selected_item = st.selectbox(
                        "📦 Final Product to Transfer",
                        options=available_items['id'].tolist(),
                        format_func=lambda x: f"{available_items[available_items['id']==x]['name'].iloc[0]} ({available_items[available_items['id']==x]['current_stock'].iloc[0]} {available_items[available_items['id']==x]['unit'].iloc[0]})"
                    )
                    
                    if selected_item:
                        max_qty = available_items[available_items['id'] == selected_item]['current_stock'].iloc[0]
                        transfer_qty = st.number_input("Quantity to Transfer", min_value=0.0, max_value=max_qty, value=1.0)
                
                with col2:
                    reference = st.text_input("Transfer Reference", placeholder="Admin transfer - reason for moving stock")
                    batch_nr = st.text_input("Batch Number", placeholder="Optional batch reference")
                    
                    col2a, col2b = st.columns(2)
                    with col2a:
                        invoice_nr = st.text_input("Invoice #", placeholder="Optional")
                    with col2b:
                        po_nr = st.text_input("PO #", placeholder="Optional")
                
                submitted = st.form_submit_button("🔀 Transfer Final Product", type="primary", use_container_width=True)
                
                if submitted:
                    if selected_item and transfer_qty > 0:
                        success, message = transfer_stock_between_branches(
                            selected_item, from_branch_id, to_branch_id, transfer_qty, 
                            f"ADMIN TRANSFER: {reference}", batch_nr, invoice_nr, po_nr, st.session_state.username
                        )
                        
                        if success:
                            item_name = available_items[available_items['id'] == selected_item]['name'].iloc[0]
                            st.success(f"✅ Successfully transferred {transfer_qty} units of {item_name} from {from_branch_name} to {to_branch_name}")
                            if batch_nr or invoice_nr or po_nr:
                                tracking_info = []
                                if batch_nr: tracking_info.append(f"Batch: {batch_nr}")
                                if invoice_nr: tracking_info.append(f"Invoice: {invoice_nr}")
                                if po_nr: tracking_info.append(f"PO: {po_nr}")
                                st.info(f"📋 Tracking: {' | '.join(tracking_info)}")
                            st.rerun()
                        else:
                            st.error(f"❌ Transfer failed: {message}")
                    else:
                        st.error("❌ Please select an item and enter a quantity greater than 0")
        
        else:
            from_branch_name = branches_df[branches_df['id'] == from_branch_id]['branch_name'].iloc[0]
            st.warning(f"⚠️ No final products with stock available in **{from_branch_name}**")
            
            # Show what final products exist but have no stock
            all_final_products = get_all_items("admin", from_branch_id)
            if not all_final_products.empty:
                zero_stock_items = all_final_products[all_final_products['current_stock'] <= 0]
                if not zero_stock_items.empty:
                    st.info(f"💡 Final products in this branch with zero stock:")
                    for _, item in zero_stock_items.iterrows():
                        st.write(f"- {item['name']}: {item['current_stock']} {item['unit']}")
            else:
                st.info(f"💡 No final products found in **{from_branch_name}**")

def show_admin_stock_movements():
    """Admin interface for viewing final product stock movements with enhanced tracking"""
    st.header("📈 Final Product Stock Movements")
    
    if not check_permission('admin'):
        st.error("❌ Access denied.")
        return
    
    branches_df = get_all_branches()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        branch_filter = st.selectbox(
            "🏪 Filter by Branch",
            options=["All Branches"] + branches_df['branch_name'].tolist()
        )
    
    with col2:
        user_filter = st.selectbox(
            "👤 Filter by User",
            options=["All Users", "My Movements", "Manager Movements", "Admin Movements"]
        )
    
    with col3:
        movement_filter = st.selectbox(
            "🔄 Movement Type",
            options=["All Types", "Admin Actions", "Transfers", "Production", "Stock In/Out"]
        )
    
    # Get movements for final products only
    conn = sqlite3.connect('inventory.db')
    
    # Build base query
    base_query = '''
        SELECT sm.*, i.name as item_name, i.unit, b.branch_name,
               b1.branch_name as from_branch_name,
               b2.branch_name as to_branch_name
        FROM stock_movements sm
        JOIN items i ON sm.item_id = i.id AND sm.branch_id = i.branch_id
        JOIN branches b ON sm.branch_id = b.id
        LEFT JOIN branches b1 ON sm.from_branch_id = b1.id
        LEFT JOIN branches b2 ON sm.to_branch_id = b2.id
        WHERE i.category = 'Final Product'
    '''
    
    # Add filters
    params = []
    
    if branch_filter != "All Branches":
        branch_id = branches_df[branches_df['branch_name'] == branch_filter]['id'].iloc[0]
        base_query += " AND sm.branch_id = ?"
        params.append(branch_id)
    
    if user_filter == "My Movements":
        base_query += " AND sm.user_id = ?"
        params.append(st.session_state.username)
    elif user_filter == "Manager Movements":
        base_query += " AND sm.user_id LIKE '%manager%'"
    elif user_filter == "Admin Movements":
        base_query += " AND sm.user_id = 'admin'"
    
    if movement_filter == "Admin Actions":
        base_query += " AND sm.movement_type LIKE 'ADMIN_%'"
    elif movement_filter == "Transfers":
        base_query += " AND sm.movement_type LIKE 'TRANSFER_%'"
    elif movement_filter == "Production":
        base_query += " AND sm.movement_type = 'PRODUCTION'"
    elif movement_filter == "Stock In/Out":
        base_query += " AND sm.movement_type IN ('IN', 'OUT')"
    
    base_query += " ORDER BY sm.date_time DESC LIMIT 100"
    
    movements_df = pd.read_sql_query(base_query, conn, params=params)
    conn.close()
    
    if not movements_df.empty:
        st.info(f"📊 Showing {len(movements_df)} movements (filtered)")
        
        # Process and display movements with enhanced information
        display_data = []
        
        for _, row in movements_df.iterrows():
            # Format movement type and details
            movement_info = row['movement_type']
            direction = ""
            
            if row['movement_type'] in ['TRANSFER_OUT', 'TRANSFER_IN']:
                if row['movement_type'] == 'TRANSFER_OUT':
                    direction = f"→ {row['to_branch_name']}" if row['to_branch_name'] else ""
                else:
                    direction = f"← {row['from_branch_name']}" if row['from_branch_name'] else ""
                movement_info = f"Transfer {direction}"
            elif row['movement_type'] in ['ADMIN_IN', 'ADMIN_OUT', 'ADMIN_SET']:
                movement_info = f"Admin {row['movement_type'].split('_')[1]}"
            elif row['movement_type'] == 'IN':
                movement_info = "Stock In"
            elif row['movement_type'] == 'OUT':
                movement_info = "Stock Out"
            elif row['movement_type'] == 'PRODUCTION':
                movement_info = "Production"
            
            # Build tracking info
            tracking_parts = []
            if row.get('batch_nr'):
                tracking_parts.append(f"Batch: {row['batch_nr']}")
            if row.get('invoice_nr'):
                tracking_parts.append(f"Inv: {row['invoice_nr']}")
            if row.get('po_nr'):
                tracking_parts.append(f"PO: {row['po_nr']}")
            
            tracking_info = " | ".join(tracking_parts) if tracking_parts else "-"
            
            # User color coding
            user_display = row['user_id']
            if 'admin' in row['user_id'].lower():
                user_display = f"🔧 {row['user_id']}"
            elif 'manager' in row['user_id'].lower():
                user_display = f"👨‍💼 {row['user_id']}"
            
            display_data.append({
                'Date': row['date_time'][:16],
                'Branch': row['branch_name'],
                'Product': row['item_name'],
                'Movement': movement_info,
                'Quantity': f"{row['quantity']} {row['unit']}",
                'Reference': row['reference'][:30] + "..." if row['reference'] and len(row['reference']) > 30 else (row['reference'] or '-'),
                'Tracking': tracking_info,
                'User': user_display
            })
        
        if display_data:
            movements_display_df = pd.DataFrame(display_data)
            st.dataframe(movements_display_df, use_container_width=True, height=400)
            
            # Summary statistics
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_movements = len(movements_df)
                st.metric("Total Movements", total_movements)
            
            with col2:
                admin_actions = len(movements_df[movements_df['movement_type'].str.contains('ADMIN')])
                st.metric("Admin Actions", admin_actions)
            
            with col3:
                transfers = len(movements_df[movements_df['movement_type'].str.contains('TRANSFER')])
                st.metric("Transfers", transfers)
            
            with col4:
                unique_products = movements_df['item_name'].nunique()
                st.metric("Products Affected", unique_products)
            
            # Show recent admin vs manager activity
            if not movements_df.empty:
                st.subheader("👥 Recent Activity by User Type")
                admin_count = len(movements_df[movements_df['user_id'].str.contains('admin', case=False)])
                manager_count = len(movements_df[movements_df['user_id'].str.contains('manager', case=False)])
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("🔧 Admin Actions", admin_count)
                with col2:
                    st.metric("👨‍💼 Manager Actions", manager_count)
        else:
            st.info("No movements found with the selected filters.")
    else:
        st.info("📊 No final product movements found.")
        st.markdown("""
        **Movements will appear here when:**
        - ✅ Stock is updated by admins
        - ✅ Products are transferred between branches  
        - ✅ Final products are produced
        - ✅ Stock adjustments are made
        
        **Enhanced Tracking includes:**
        - 📋 Batch numbers
        - 🧾 Invoice numbers  
        - 📝 PO numbers
        - 👤 User identification
        """)
    """Admin view of all branches and their final products"""
    st.header("🏪 All Branches - Final Products")
    
    if not check_permission('admin'):
        st.error("❌ Access denied.")
        return
    
    branches_df = get_all_branches()
    items_df = get_all_items("admin")
    
    if not branches_df.empty:
        for _, branch in branches_df.iterrows():
            branch_items = items_df[items_df['branch_id'] == branch['id']]
            
            with st.expander(f"🏪 {branch['branch_name']} - {branch['location']} ({len(branch_items)} products)"):
                if not branch_items.empty:
                    display_df = branch_items[['name', 'current_stock', 'unit']].copy()
                    display_df.columns = ['Product', 'Stock', 'Unit']
                    st.dataframe(display_df, use_container_width=True)
                    
                    # Quick stats
                    col1, col2 = st.columns(2)
                    with col1:
                        in_stock = len(branch_items[branch_items['current_stock'] > 0])
                        st.metric("In Stock", in_stock)
                    with col2:
                        out_of_stock = len(branch_items[branch_items['current_stock'] <= 0])
                        st.metric("Out of Stock", out_of_stock)
def show_admin_branch_view():
    """Admin view of all branches and their final products with quantities"""
    st.header("🏪 All Branches - Final Products Stock")
    
    if not check_permission('admin'):
        st.error("❌ Access denied.")
        return
    
    branches_df = get_all_branches()
    items_df = get_all_items("admin")
    
    if not branches_df.empty:
        # Summary overview first
        st.subheader("📊 Quick Overview")
        
        summary_data = []
        for _, branch in branches_df.iterrows():
            branch_items = items_df[items_df['branch_id'] == branch['id']]
            if not branch_items.empty:
                total_stock = branch_items['current_stock'].sum()
                in_stock_items = len(branch_items[branch_items['current_stock'] > 0])
                out_of_stock = len(branch_items[branch_items['current_stock'] <= 0])
                
                summary_data.append({
                    'Branch': branch['branch_name'],
                    'Location': branch['location'],
                    'Products': len(branch_items),
                    'In Stock': in_stock_items,
                    'Out of Stock': out_of_stock,
                    'Total Units': total_stock
                })
        
        if summary_data:
            summary_df = pd.DataFrame(summary_data)
            st.dataframe(summary_df, use_container_width=True)
        
        # Detailed branch breakdown
        st.subheader("📦 Detailed Stock by Branch")
        
        for _, branch in branches_df.iterrows():
            branch_items = items_df[items_df['branch_id'] == branch['id']]
            
            with st.expander(f"🏪 {branch['branch_name']} - {branch['location']} ({len(branch_items)} products)", expanded=False):
                if not branch_items.empty:
                    # Add status indicators
                    def get_status_icon(row):
                        if row['current_stock'] <= 0:
                            return "❌"
                        elif row['current_stock'] <= row['min_stock']:
                            return "⚠️"
                        else:
                            return "✅"
                    
                    branch_items = branch_items.copy()
                    branch_items['Status'] = branch_items.apply(get_status_icon, axis=1)
                    
                    display_df = branch_items[['Status', 'name', 'current_stock', 'min_stock', 'unit']].copy()
                    display_df.columns = ['Status', 'Product', 'Current Stock', 'Min Stock', 'Unit']
                    
                    st.dataframe(display_df, use_container_width=True)
                    
                    # Branch stats
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        total_items = len(branch_items)
                        st.metric("Total Products", total_items)
                    with col2:
                        in_stock = len(branch_items[branch_items['current_stock'] > 0])
                        st.metric("In Stock", in_stock)
                    with col3:
                        out_of_stock = len(branch_items[branch_items['current_stock'] <= 0])
                        st.metric("Out of Stock", out_of_stock)
                else:
                    st.info("No final products in this branch")
                    st.markdown("💡 **How to add products:**")
                    st.markdown("- Transfer from another branch")
                    st.markdown("- Ask warehouse manager to add items")
    else:
        st.error("No branches found in the system.")

# ENHANCED MANAGEMENT PAGES
def show_management_dashboard():
    """Enhanced dashboard for boss with branch overview"""
    st.header("📊 Management Dashboard")
    
    branches_df = get_all_branches()
    items_df = get_all_items()
    
    if not items_df.empty:
        # High-level metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_branches = len(branches_df)
            st.metric("Active Branches", total_branches)
        
        with col2:
            total_items = len(items_df)
            st.metric("Total Items", total_items)
        
        with col3:
            final_products = len(items_df[items_df['category'] == 'Final Product'])
            st.metric("Final Products", final_products)
        
        with col4:
            critical_items = len(items_df[items_df['current_stock'] <= 0])
            st.metric("Critical Items", critical_items)
        
        # Branch overview
        st.subheader("🏪 Branch Overview")
        
        branch_data = []
        for _, branch in branches_df.iterrows():
            branch_items = items_df[items_df['branch_id'] == branch['id']]
            if not branch_items.empty:
                raw_materials = len(branch_items[branch_items['category'] == 'Raw Material'])
                pre_final = len(branch_items[branch_items['category'] == 'Pre-Final'])
                final_products = len(branch_items[branch_items['category'] == 'Final Product'])
                critical = len(branch_items[branch_items['current_stock'] <= 0])
                
                branch_data.append({
                    'Branch': branch['branch_name'],
                    'Location': branch['location'],
                    'Raw Materials': raw_materials,
                    'Components': pre_final,
                    'Final Products': final_products,
                    'Critical': critical
                })
        
        if branch_data:
            branch_df = pd.DataFrame(branch_data)
            st.dataframe(branch_df, use_container_width=True)
        
        # Critical alerts
        critical_items = items_df[items_df['current_stock'] <= 0]
        if not critical_items.empty:
            st.error(f"🚨 CRITICAL: {len(critical_items)} items are OUT OF STOCK across all branches!")
            
            # Group by branch
            for _, branch in branches_df.iterrows():
                branch_critical = critical_items[critical_items['branch_id'] == branch['id']]
                if not branch_critical.empty:
                    st.write(f"**{branch['branch_name']}:** {len(branch_critical)} items out of stock")

def show_branch_overview():
    """Branch overview for management"""
    st.header("🏪 Branch Overview")
    
    branches_df = get_all_branches()
    
    if not branches_df.empty:
        # Branch cards
        for _, branch in branches_df.iterrows():
            with st.expander(f"🏪 {branch['branch_name']} - {branch['location']}", expanded=True):
                
                # Branch info
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Manager:** {branch['manager_name']}")
                    st.write(f"**Contact:** {branch['contact_info']}")
                
                with col2:
                    st.write(f"**Code:** {branch['branch_code']}")
                    st.write(f"**Created:** {branch['created_date'][:10]}")
                
                # Branch statistics
                items_df = get_all_items(branch_id=branch['id'])
                
                if not items_df.empty:
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Total Items", len(items_df))
                    
                    with col2:
                        raw_count = len(items_df[items_df['category'] == 'Raw Material'])
                        st.metric("Raw Materials", raw_count)
                    
                    with col3:
                        final_count = len(items_df[items_df['category'] == 'Final Product'])
                        st.metric("Final Products", final_count)
                    
                    with col4:
                        critical_count = len(items_df[items_df['current_stock'] <= 0])
                        st.metric("Out of Stock", critical_count)
                else:
                    st.info("No items in this branch")

def show_complete_stock_view():
    """Complete stock view across all branches for boss"""
    st.header("📦 Complete Stock View")
    
    branches_df = get_all_branches()
    
    # Branch filter
    branch_filter = st.selectbox(
        "🏪 Filter by Branch",
        options=["All Branches"] + branches_df['branch_name'].tolist()
    )
    
    # Category filter
    category_filter = st.selectbox(
        "📦 Filter by Category", 
        ["All Categories", "Raw Material", "Pre-Final", "Final Product"]
    )
    
    # Get filtered data
    if branch_filter == "All Branches":
        items_df = get_all_items()
    else:
        branch_id = branches_df[branches_df['branch_name'] == branch_filter]['id'].iloc[0]
        items_df = get_all_items(branch_id=branch_id)
    
    if category_filter != "All Categories":
        items_df = items_df[items_df['category'] == category_filter]
    
    # Display results
    if not items_df.empty:
        # Add status column
        def get_status(row):
            if row['current_stock'] <= 0:
                return "❌ OUT"
            elif row['current_stock'] <= row['min_stock']:
                return "⚠️ LOW"
            else:
                return "✅ OK"
        
        items_df['Status'] = items_df.apply(get_status, axis=1)
        
        display_df = items_df[['branch_name', 'name', 'category', 'current_stock', 'min_stock', 'unit', 'Status']]
        display_df.columns = ['Branch', 'Item', 'Category', 'Stock', 'Min', 'Unit', 'Status']
        
        st.dataframe(display_df, use_container_width=True, height=400)
        
        # Summary stats
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Items", len(items_df))
        
        with col2:
            in_stock = len(items_df[items_df['current_stock'] > 0])
            st.metric("In Stock", in_stock)
        
        with col3:
            low_stock = len(items_df[(items_df['current_stock'] <= items_df['min_stock']) & (items_df['current_stock'] > 0)])
            st.metric("Low Stock", low_stock)
        
        with col4:
            out_of_stock = len(items_df[items_df['current_stock'] <= 0])
            st.metric("Out of Stock", out_of_stock)
    
    else:
        st.info("No items found with the selected filters.")

def show_branch_transfers():
    """Show branch transfer history for management"""
    st.header("📈 Branch Transfer History")
    
    # Get transfer movements
    conn = sqlite3.connect('inventory.db')
    transfers_df = pd.read_sql_query('''
        SELECT sm.*, i.name as item_name, i.unit,
               b1.branch_name as from_branch_name,
               b2.branch_name as to_branch_name
        FROM stock_movements sm
        JOIN items i ON sm.item_id = i.id AND sm.branch_id = i.branch_id
        LEFT JOIN branches b1 ON sm.from_branch_id = b1.id
        LEFT JOIN branches b2 ON sm.to_branch_id = b2.id
        WHERE sm.movement_type IN ('TRANSFER_OUT', 'TRANSFER_IN')
        ORDER BY sm.date_time DESC 
        LIMIT 100
    ''', conn)
    conn.close()
    
    if not transfers_df.empty:
        # Process transfers to show paired movements
        transfer_pairs = []
        processed_ids = set()
        
        for _, row in transfers_df.iterrows():
            if row['id'] in processed_ids:
                continue
            
            if row['movement_type'] == 'TRANSFER_OUT':
                # Find corresponding TRANSFER_IN
                matching_in = transfers_df[
                    (transfers_df['item_id'] == row['item_id']) &
                    (transfers_df['movement_type'] == 'TRANSFER_IN') &
                    (transfers_df['quantity'] == row['quantity']) &
                    (transfers_df['date_time'] == row['date_time'])
                ]
                
                if not matching_in.empty:
                    in_row = matching_in.iloc[0]
                    transfer_pairs.append({
                        'Date': row['date_time'][:16],
                        'Item': row['item_name'],
                        'Quantity': f"{row['quantity']} {row['unit']}",
                        'From': row['from_branch_name'],
                        'To': row['to_branch_name'],
                        'Reference': row['reference'],
                        'User': row['user_id']
                    })
                    processed_ids.add(row['id'])
                    processed_ids.add(in_row['id'])
        
        if transfer_pairs:
            transfers_display_df = pd.DataFrame(transfer_pairs)
            st.dataframe(transfers_display_df, use_container_width=True, height=400)
        else:
            st.info("No branch transfers found.")
    else:
        st.info("No transfer history available.")

def show_management_reports():
    """Enhanced management reports with branch breakdown"""
    st.header("📋 Management Reports")
    
    branches_df = get_all_branches()
    items_df = get_all_items()
    
    if items_df.empty:
        st.info("No data available.")
        return
    
    # Branch performance summary
    st.subheader("🏪 Branch Performance")
    
    branch_summary = []
    for _, branch in branches_df.iterrows():
        branch_items = items_df[items_df['branch_id'] == branch['id']]
        if not branch_items.empty:
            total_items = len(branch_items)
            final_products = len(branch_items[branch_items['category'] == 'Final Product'])
            in_stock = len(branch_items[branch_items['current_stock'] > 0])
            critical = len(branch_items[branch_items['current_stock'] <= 0])
            
            branch_summary.append({
                'Branch': branch['branch_name'],
                'Location': branch['location'],
                'Total Items': total_items,
                'Final Products': final_products,
                'In Stock': in_stock,
                'Critical': critical,
                'Performance': f"{(in_stock/total_items*100):.1f}%" if total_items > 0 else "0%"
            })
    
    if branch_summary:
        summary_df = pd.DataFrame(branch_summary)
        st.dataframe(summary_df, use_container_width=True)
    
    # Category breakdown
    st.subheader("📊 Inventory Breakdown")
    
    category_summary = items_df.groupby(['branch_name', 'category']).agg({
        'current_stock': 'sum',
        'name': 'count'
    }).rename(columns={'name': 'items', 'current_stock': 'total_stock'}).reset_index()
    
    st.dataframe(category_summary, use_container_width=True)

# WAREHOUSE MANAGER PAGES
def show_dashboard():
    """Enhanced dashboard for warehouse manager with branch view"""
    st.header("📊 Warehouse Manager Dashboard")
    
    branches_df = get_all_branches()
    items_df = get_all_items()
    
    if not items_df.empty:
        # High-level metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_branches = len(branches_df)
            st.metric("Active Branches", total_branches)
        
        with col2:
            total_items = len(items_df)
            st.metric("Total Items", total_items)
        
        with col3:
            final_products = len(items_df[items_df['category'] == 'Final Product'])
            st.metric("Final Products", final_products)
        
        with col4:
            critical_items = len(items_df[items_df['current_stock'] <= 0])
            st.metric("Critical Items", critical_items)
        
        # Branch status overview
        st.subheader("🏪 Branch Status")
        
        for _, branch in branches_df.iterrows():
            branch_items = items_df[items_df['branch_id'] == branch['id']]
            
            if not branch_items.empty:
                with st.expander(f"🏪 {branch['branch_name']} ({len(branch_items)} items)"):
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        raw_count = len(branch_items[branch_items['category'] == 'Raw Material'])
                        st.metric("Raw Materials", raw_count)
                    
                    with col2:
                        pre_final_count = len(branch_items[branch_items['category'] == 'Pre-Final'])
                        st.metric("Components", pre_final_count)
                    
                    with col3:
                        final_count = len(branch_items[branch_items['category'] == 'Final Product'])
                        st.metric("Final Products", final_count)
                    
                    with col4:
                        critical_count = len(branch_items[branch_items['current_stock'] <= 0])
                        st.metric("Critical", critical_count)
                    
                    # Show critical items
                    critical_items = branch_items[branch_items['current_stock'] <= 0]
                    if not critical_items.empty:
                        st.error(f"🚨 Critical items in {branch['branch_name']}:")
                        for _, item in critical_items.iterrows():
                            st.write(f"❌ {item['name']}")

def show_branch_management():
    """Branch management interface for warehouse manager"""
    st.header("🏪 Branch Management")
    
    if not check_permission('warehouse_manager'):
        st.error("❌ Access denied.")
        return
    
    tab1, tab2 = st.tabs(["🏪 View Branches", "➕ Add Branch"])
    
    with tab1:
        st.subheader("🏪 All Branches")
        
        branches_df = get_all_branches()
        
        if not branches_df.empty:
            for _, branch in branches_df.iterrows():
                with st.expander(f"🏪 {branch['branch_name']} - {branch['location']}", expanded=True):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Branch Code:** {branch['branch_code']}")
                        st.write(f"**Manager:** {branch['manager_name']}")
                        st.write(f"**Contact:** {branch['contact_info']}")
                    
                    with col2:
                        st.write(f"**Created:** {branch['created_date'][:10]}")
                        
                        # Branch statistics
                        items_df = get_all_items(branch_id=branch['id'])
                        if not items_df.empty:
                            st.write(f"**Items:** {len(items_df)}")
                            critical_count = len(items_df[items_df['current_stock'] <= 0])
                            st.write(f"**Critical:** {critical_count}")
                        else:
                            st.write("**Items:** 0")
        else:
            st.info("No branches found.")
    
    with tab2:
        st.subheader("➕ Add New Branch")
        
        with st.form("add_branch_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                branch_code = st.text_input("Branch Code", placeholder="e.g., DBN, CPT, JHB")
                branch_name = st.text_input("Branch Name", placeholder="e.g., Durban Branch")
                location = st.text_input("Location", placeholder="e.g., Durban, KZN")
            
            with col2:
                manager_name = st.text_input("Manager Name", placeholder="Branch Manager")
                contact_info = st.text_input("Contact Info", placeholder="Phone/Email")
            
            submitted = st.form_submit_button("🏪 Add Branch", type="primary")
            
            if submitted:
                if branch_code and branch_name:
                    try:
                        add_branch(branch_code.upper(), branch_name, location, manager_name, contact_info)
                        st.success(f"✅ Added branch: {branch_name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error adding branch: {str(e)}")
                else:
                    st.error("❌ Please fill in Branch Code and Branch Name")

def show_stock_management():
    """Enhanced stock management with branch selection"""
    st.header("📦 Stock Management")
    
    if not check_permission('warehouse_manager'):
        st.error("❌ Access denied.")
        return
    
    branches_df = get_all_branches()
    
    # Branch selection
    selected_branch_id = st.selectbox(
        "🏪 Select Branch",
        options=branches_df['id'].tolist(),
        format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]} - {branches_df[branches_df['id']==x]['location'].iloc[0]}"
    )
    
    if selected_branch_id:
        branch_info = branches_df[branches_df['id'] == selected_branch_id].iloc[0]
        st.info(f"📍 Managing stock for: **{branch_info['branch_name']}** - {branch_info['location']}")
        
        items_df = get_all_items(branch_id=selected_branch_id)
        
        if items_df.empty:
            st.warning(f"No items found in {branch_info['branch_name']}. Add items or transfer from other branches.")
            return
        
        # Filters
        category_filter = st.selectbox("Category", ["All", "Raw Material", "Pre-Final", "Final Product"])
        
        # Apply filter
        if category_filter != "All":
            items_df = items_df[items_df['category'] == category_filter]
        
        # Display stock table
        if not items_df.empty:
            def get_status(row):
                if row['current_stock'] <= 0:
                    return "❌ OUT"
                elif row['current_stock'] <= row['min_stock']:
                    return "⚠️ LOW"
                else:
                    return "✅ OK"
            
            items_df['Status'] = items_df.apply(get_status, axis=1)
            
            display_df = items_df[['id', 'name', 'current_stock', 'unit', 'Status']]
            display_df.columns = ['ID', 'Name', 'Stock', 'Unit', 'Status']
            
            st.dataframe(display_df, use_container_width=True, height=300)
            
            # Quick stock adjustment
            st.subheader("⚡ Quick Update")
            
            with st.form("quick_stock_update"):
                col1, col2 = st.columns(2)
                
                with col1:
                    selected_item = st.selectbox("Item", 
                                               options=items_df['id'].tolist(),
                                               format_func=lambda x: f"{x} - {items_df[items_df['id']==x]['name'].iloc[0]}")
                    adjustment_qty = st.number_input("Quantity", value=0.0)
                    movement_type = st.selectbox("Type", ["IN", "OUT"])
                
                with col2:
                    reference = st.text_input("Reference", placeholder="Reason")
                    batch_nr = st.text_input("Batch #", placeholder="Optional")
                    
                    col2a, col2b = st.columns(2)
                    with col2a:
                        invoice_nr = st.text_input("Invoice #", placeholder="Optional")
                    with col2b:
                        po_nr = st.text_input("PO #", placeholder="Optional")
                
                submitted = st.form_submit_button("💾 Update Stock", type="primary", use_container_width=True)
                
                if submitted:
                    if selected_item and adjustment_qty != 0:
                        update_stock(selected_item, selected_branch_id, abs(adjustment_qty), movement_type, reference, batch_nr, invoice_nr, po_nr, st.session_state.username)
                        st.success("✅ Stock updated!")
                        st.rerun()
                    else:
                        st.error("❌ Please select an item and enter a non-zero quantity")

def show_stock_transfers():
    """Stock transfer interface between branches"""
    st.header("🔄 Branch Stock Transfers")
    
    if not check_permission('warehouse_manager'):
        st.error("❌ Access denied.")
        return
    
    branches_df = get_all_branches()
    
    if len(branches_df) < 2:
        st.warning("Need at least 2 branches to perform transfers.")
        return
    
    tab1, tab2 = st.tabs(["🔄 Transfer Stock", "📈 Transfer History"])
    
    with tab1:
        st.subheader("🔄 Transfer Stock Between Branches")
        
        # First, let user select branches without form
        col1, col2 = st.columns(2)
        
        with col1:
            from_branch_id = st.selectbox(
                "📤 From Branch",
                options=branches_df['id'].tolist(),
                format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]}"
            )
        
        with col2:
            to_branch_options = [bid for bid in branches_df['id'].tolist() if bid != from_branch_id]
            to_branch_id = st.selectbox(
                "📥 To Branch",
                options=to_branch_options,
                format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]}"
            ) if to_branch_options else None
        
        if from_branch_id and to_branch_id:
            # Get items from source branch
            from_items_df = get_all_items(branch_id=from_branch_id)
            available_items = from_items_df[from_items_df['current_stock'] > 0]
            
            if not available_items.empty:
                # Show available items first
                from_branch_name = branches_df[branches_df['id'] == from_branch_id]['branch_name'].iloc[0]
                st.info(f"📦 Available items in **{from_branch_name}**: {len(available_items)} items")
                
                # Now create the form
                with st.form("stock_transfer_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        selected_item = st.selectbox(
                            "📦 Item to Transfer",
                            options=available_items['id'].tolist(),
                            format_func=lambda x: f"{available_items[available_items['id']==x]['name'].iloc[0]} ({available_items[available_items['id']==x]['current_stock'].iloc[0]} {available_items[available_items['id']==x]['unit'].iloc[0]})"
                        )
                        
                        if selected_item:
                            max_qty = available_items[available_items['id'] == selected_item]['current_stock'].iloc[0]
                            transfer_qty = st.number_input("Quantity to Transfer", min_value=0.0, max_value=max_qty, value=1.0)
                    
                    with col2:
                        reference = st.text_input("Transfer Reference", placeholder="Reason for transfer")
                        batch_nr = st.text_input("Batch Number", placeholder="Optional batch reference")
                        
                        col2a, col2b = st.columns(2)
                        with col2a:
                            invoice_nr = st.text_input("Invoice #", placeholder="Optional")
                        with col2b:
                            po_nr = st.text_input("PO #", placeholder="Optional")
                    
                    # Submit button
                    submitted = st.form_submit_button("🔄 Transfer Stock", type="primary", use_container_width=True)
                    
                    if submitted:
                        if selected_item and transfer_qty > 0:
                            success, message = transfer_stock_between_branches(
                                selected_item, from_branch_id, to_branch_id, transfer_qty, reference, batch_nr, invoice_nr, po_nr, st.session_state.username
                            )
                            
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                        else:
                            st.error("❌ Please select an item and enter a quantity greater than 0")
            else:
                from_branch_name = branches_df[branches_df['id'] == from_branch_id]['branch_name'].iloc[0]
                st.warning(f"⚠️ No items with stock available in **{from_branch_name}**")
                
                # Show what items exist but have no stock
                all_items_in_branch = get_all_items(branch_id=from_branch_id)
                if not all_items_in_branch.empty:
                    zero_stock_items = all_items_in_branch[all_items_in_branch['current_stock'] <= 0]
                    if not zero_stock_items.empty:
                        st.info(f"💡 There are {len(zero_stock_items)} items in this branch with zero stock:")
                        for _, item in zero_stock_items.head(5).iterrows():
                            st.write(f"- {item['name']}: {item['current_stock']} {item['unit']}")
                else:
                    st.info(f"💡 No items found in **{from_branch_name}**. Add items to this branch first.")
        else:
            st.info("👆 Please select both source and destination branches to start transfer.")
    
    with tab2:
        st.subheader("📈 Recent Transfers")
        
        # Get recent transfers
        conn = sqlite3.connect('inventory.db')
        transfers_df = pd.read_sql_query('''
            SELECT sm.*, i.name as item_name, i.unit,
                   b1.branch_name as from_branch_name,
                   b2.branch_name as to_branch_name
            FROM stock_movements sm
            JOIN items i ON sm.item_id = i.id AND sm.branch_id = i.branch_id
            LEFT JOIN branches b1 ON sm.from_branch_id = b1.id
            LEFT JOIN branches b2 ON sm.to_branch_id = b2.id
            WHERE sm.movement_type IN ('TRANSFER_OUT', 'TRANSFER_IN')
            ORDER BY sm.date_time DESC 
            LIMIT 50
        ''', conn)
        conn.close()
        
        if not transfers_df.empty:
            # Show only OUT transfers to avoid duplicates
            out_transfers = transfers_df[transfers_df['movement_type'] == 'TRANSFER_OUT']
            
            if not out_transfers.empty:
                # Build tracking info
                def build_tracking_info(row):
                    tracking_parts = []
                    if row.get('batch_nr'):
                        tracking_parts.append(f"Batch: {row['batch_nr']}")
                    if row.get('invoice_nr'):
                        tracking_parts.append(f"Inv: {row['invoice_nr']}")
                    if row.get('po_nr'):
                        tracking_parts.append(f"PO: {row['po_nr']}")
                    return " | ".join(tracking_parts) if tracking_parts else "-"
                
                out_transfers = out_transfers.copy()
                out_transfers['tracking'] = out_transfers.apply(build_tracking_info, axis=1)
                
                display_transfers = out_transfers[['date_time', 'item_name', 'quantity', 'unit', 
                                                 'from_branch_name', 'to_branch_name', 'tracking', 'reference', 'user_id']]
                display_transfers.columns = ['Date', 'Item', 'Qty', 'Unit', 'From', 'To', 'Tracking', 'Reference', 'User']
                display_transfers['Date'] = pd.to_datetime(display_transfers['Date']).dt.strftime('%m-%d %H:%M')
                
                st.dataframe(display_transfers, use_container_width=True, height=400)
            else:
                st.info("No transfers found.")
        else:
            st.info("No transfer history available.")

def show_production_center():
    """Enhanced production center with branch selection"""
    if not check_permission('warehouse_manager'):
        st.error("❌ Access denied.")
        return
    
    st.header("🏭 Production Center")
    
    branches_df = get_all_branches()
    
    # Branch selection for production
    selected_branch_id = st.selectbox(
        "🏪 Production Branch",
        options=branches_df['id'].tolist(),
        format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]}"
    )
    
    if selected_branch_id:
        branch_info = branches_df[branches_df['id'] == selected_branch_id].iloc[0]
        st.info(f"🏭 Production at: **{branch_info['branch_name']}** - {branch_info['location']}")
        
        items_df = get_all_items(branch_id=selected_branch_id)
        final_products = items_df[items_df['category'] == 'Final Product']
        
        if final_products.empty:
            st.warning("No final products found in this branch.")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_product = st.selectbox("Product",
                                          options=final_products['id'].tolist(),
                                          format_func=lambda x: f"{final_products[final_products['id']==x]['name'].iloc[0]}")
            
            quantity_to_produce = st.number_input("Quantity", min_value=1, value=1)
            
            if st.button("🚀 Start Production", type="primary"):
                if selected_product and quantity_to_produce > 0:
                    # For now, just add to final product stock (BOM functionality would need to be updated for branches)
                    update_stock(selected_product, selected_branch_id, quantity_to_produce, 'PRODUCTION', 
                               f'Produced {quantity_to_produce} units', '', '', '', st.session_state.username)
                    st.success(f"✅ Produced {quantity_to_produce} units!")
                    st.rerun()
        
        with col2:
            if selected_product:
                product_info = final_products[final_products['id'] == selected_product].iloc[0]
                st.subheader("📦 Product Info")
                st.write(f"**Current Stock:** {product_info['current_stock']} {product_info['unit']}")
                st.write(f"**Min Stock:** {product_info['min_stock']} {product_info['unit']}")

def show_item_management():
    """Enhanced item management with branch support"""
    if not check_permission('warehouse_manager'):
        st.error("❌ Access denied.")
        return
    
    st.header("⚙️ Item Management")
    
    branches_df = get_all_branches()
    
    tab1, tab2 = st.tabs(["➕ Add Item", "📋 View & Manage Items"])
    
    with tab1:
        st.subheader("Add New Item")
        
        with st.form("add_item_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                branch_id = st.selectbox(
                    "🏪 Branch",
                    options=branches_df['id'].tolist(),
                    format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]}"
                )
                item_id = st.text_input("Item ID", value=str(uuid.uuid4())[:8].upper())
                name = st.text_input("Item Name")
                category = st.selectbox("Category", ["Raw Material", "Pre-Final", "Final Product"])
            
            with col2:
                unit = st.selectbox("Unit", ["kg", "g", "L", "ml", "pieces", "units"])
                current_stock = st.number_input("Current Stock", min_value=0.0, value=0.0)
                min_stock = st.number_input("Min Stock", min_value=0.0, value=0.0)
            
            submitted = st.form_submit_button("➕ Add Item", type="primary")
            
            if submitted:
                if name and item_id and branch_id:
                    add_item(item_id, name, category, unit, current_stock, min_stock, 0, "Main", "General", branch_id, st.session_state.username)
                    branch_name = branches_df[branches_df['id'] == branch_id]['branch_name'].iloc[0]
                    st.success(f"✅ Added {name} to {branch_name}!")
                    st.rerun()
                else:
                    st.error("❌ Please fill all required fields")
    
    with tab2:
        st.subheader("📋 All Items")
        
        # Branch filter
        branch_filter = st.selectbox(
            "🏪 Filter by Branch",
            options=["All Branches"] + branches_df['branch_name'].tolist()
        )
        
        if branch_filter == "All Branches":
            items_df = get_all_items()
        else:
            branch_id = branches_df[branches_df['branch_name'] == branch_filter]['id'].iloc[0]
            items_df = get_all_items(branch_id=branch_id)
        
        if not items_df.empty:
            # Category filter
            category_filter = st.selectbox("Filter by Category", 
                                         ["All", "Raw Material", "Pre-Final", "Final Product"])
            
            filtered_items = items_df.copy()
            if category_filter != "All":
                filtered_items = filtered_items[filtered_items['category'] == category_filter]
            
            # Add status column
            def get_status(row):
                if row['current_stock'] <= 0:
                    return "❌ OUT"
                elif row['current_stock'] <= row['min_stock']:
                    return "⚠️ LOW"
                else:
                    return "✅ OK"
            
            filtered_items['Status'] = filtered_items.apply(get_status, axis=1)
            
            display_df = filtered_items[['branch_name', 'id', 'name', 'category', 'current_stock', 'min_stock', 'unit', 'Status']]
            display_df.columns = ['Branch', 'ID', 'Name', 'Category', 'Stock', 'Min', 'Unit', 'Status']
            
            st.dataframe(display_df, use_container_width=True, height=400)

def show_reports():
    """Enhanced reports with branch breakdown"""
    st.header("📋 Reports & Analytics")
    
    branches_df = get_all_branches()
    items_df = get_all_items()
    
    if items_df.empty:
        st.info("No data available.")
        return
    
    tab1, tab2, tab3 = st.tabs(["📊 Overview", "🏪 By Branch", "📈 Movements"])
    
    with tab1:
        st.subheader("📊 System Overview")
        
        # High-level metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Branches", len(branches_df))
        
        with col2:
            st.metric("Total Items", len(items_df))
        
        with col3:
            in_stock = len(items_df[items_df['current_stock'] > 0])
            st.metric("Items In Stock", in_stock)
        
        with col4:
            critical = len(items_df[items_df['current_stock'] <= 0])
            st.metric("Critical Items", critical)
        
        # Category breakdown
        st.subheader("📦 By Category")
        category_summary = items_df.groupby('category').agg({
            'current_stock': 'sum',
            'name': 'count'
        }).rename(columns={'name': 'items', 'current_stock': 'total_stock'})
        
        st.dataframe(category_summary, use_container_width=True)
    
    with tab2:
        st.subheader("🏪 Branch Breakdown")
        
        branch_summary = []
        for _, branch in branches_df.iterrows():
            branch_items = items_df[items_df['branch_id'] == branch['id']]
            if not branch_items.empty:
                total_items = len(branch_items)
                in_stock = len(branch_items[branch_items['current_stock'] > 0])
                critical = len(branch_items[branch_items['current_stock'] <= 0])
                
                branch_summary.append({
                    'Branch': branch['branch_name'],
                    'Location': branch['location'],
                    'Total Items': total_items,
                    'In Stock': in_stock,
                    'Critical': critical,
                    'Performance': f"{(in_stock/total_items*100):.1f}%" if total_items > 0 else "0%"
                })
        
        if branch_summary:
            summary_df = pd.DataFrame(branch_summary)
            st.dataframe(summary_df, use_container_width=True)
    
    with tab3:
        st.subheader("📈 Recent Stock Movements")
        
        conn = sqlite3.connect('inventory.db')
        movements_df = pd.read_sql_query('''
            SELECT sm.*, i.name as item_name, i.unit, b.branch_name
            FROM stock_movements sm
            JOIN items i ON sm.item_id = i.id AND sm.branch_id = i.branch_id
            JOIN branches b ON sm.branch_id = b.id
            ORDER BY sm.date_time DESC 
            LIMIT 100
        ''', conn)
        conn.close()
        
        if not movements_df.empty:
            movements_df['date_time'] = pd.to_datetime(movements_df['date_time']).dt.strftime('%m-%d %H:%M')
            
            # Build tracking info
            def build_tracking_info(row):
                tracking_parts = []
                if row.get('batch_nr'):
                    tracking_parts.append(f"Batch: {row['batch_nr']}")
                if row.get('invoice_nr'):
                    tracking_parts.append(f"Inv: {row['invoice_nr']}")
                if row.get('po_nr'):
                    tracking_parts.append(f"PO: {row['po_nr']}")
                return " | ".join(tracking_parts) if tracking_parts else "-"
            
            movements_df['tracking'] = movements_df.apply(build_tracking_info, axis=1)
            
            display_df = movements_df[['date_time', 'branch_name', 'item_name', 'movement_type', 'quantity', 'unit', 'tracking', 'user_id']]
            display_df.columns = ['Date', 'Branch', 'Item', 'Type', 'Qty', 'Unit', 'Tracking', 'User']
            
            st.dataframe(display_df, use_container_width=True, height=400)
        else:
            st.info("No movements found.")

def show_manager_stock_movements():
    """Manager interface for viewing all stock movements with enhanced tracking"""
    st.header("📈 Stock Movement History")
    
    if not check_permission('warehouse_manager'):
        st.error("❌ Access denied.")
        return
    
    branches_df = get_all_branches()
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        branch_filter = st.selectbox(
            "🏪 Filter by Branch",
            options=["All Branches"] + branches_df['branch_name'].tolist()
        )
    
    with col2:
        category_filter = st.selectbox(
            "📦 Filter by Category",
            options=["All Categories", "Final Product", "Raw Material", "Pre-Final"]
        )
    
    with col3:
        user_filter = st.selectbox(
            "👤 Filter by User",
            options=["All Users", "My Movements", "Admin Movements", "Manager Movements"]
        )
    
    # Additional filters
    col4, col5 = st.columns(2)
    
    with col4:
        movement_filter = st.selectbox(
            "🔄 Movement Type",
            options=["All Types", "Admin Actions", "Transfers", "Production", "Stock In/Out", "Manager Actions"]
        )
    
    with col5:
        limit_records = st.selectbox(
            "📊 Show Records",
            options=[50, 100, 200, 500],
            index=1
        )
    
    # Get movements for all items
    conn = sqlite3.connect('inventory.db')
    
    # Build base query
    base_query = '''
        SELECT sm.*, i.name as item_name, i.unit, i.category, b.branch_name,
               b1.branch_name as from_branch_name,
               b2.branch_name as to_branch_name
        FROM stock_movements sm
        JOIN items i ON sm.item_id = i.id AND sm.branch_id = i.branch_id
        JOIN branches b ON sm.branch_id = b.id
        LEFT JOIN branches b1 ON sm.from_branch_id = b1.id
        LEFT JOIN branches b2 ON sm.to_branch_id = b2.id
        WHERE 1=1
    '''
    
    # Add filters
    params = []
    
    if branch_filter != "All Branches":
        branch_id = branches_df[branches_df['branch_name'] == branch_filter]['id'].iloc[0]
        base_query += " AND sm.branch_id = ?"
        params.append(branch_id)
    
    if category_filter != "All Categories":
        base_query += " AND i.category = ?"
        params.append(category_filter)
    
    if user_filter == "My Movements":
        base_query += " AND sm.user_id = ?"
        params.append(st.session_state.username)
    elif user_filter == "Admin Movements":
        base_query += " AND sm.user_id = 'admin'"
    elif user_filter == "Manager Movements":
        base_query += " AND sm.user_id LIKE '%manager%'"
    
    if movement_filter == "Admin Actions":
        base_query += " AND sm.movement_type LIKE 'ADMIN_%'"
    elif movement_filter == "Transfers":
        base_query += " AND sm.movement_type LIKE 'TRANSFER_%'"
    elif movement_filter == "Production":
        base_query += " AND sm.movement_type = 'PRODUCTION'"
    elif movement_filter == "Stock In/Out":
        base_query += " AND sm.movement_type IN ('IN', 'OUT')"
    elif movement_filter == "Manager Actions":
        base_query += " AND (sm.movement_type IN ('IN', 'OUT', 'PRODUCTION') OR sm.user_id LIKE '%manager%')"
    
    base_query += f" ORDER BY sm.date_time DESC LIMIT {limit_records}"
    
    movements_df = pd.read_sql_query(base_query, conn, params=params)
    conn.close()
    
    if not movements_df.empty:
        st.info(f"📊 Showing {len(movements_df)} movements (filtered)")
        
        # Process and display movements with enhanced information
        display_data = []
        
        for _, row in movements_df.iterrows():
            # Format movement type and details
            movement_info = row['movement_type']
            direction = ""
            
            if row['movement_type'] in ['TRANSFER_OUT', 'TRANSFER_IN']:
                if row['movement_type'] == 'TRANSFER_OUT':
                    direction = f"→ {row['to_branch_name']}" if row['to_branch_name'] else ""
                else:
                    direction = f"← {row['from_branch_name']}" if row['from_branch_name'] else ""
                movement_info = f"Transfer {direction}"
            elif row['movement_type'] in ['ADMIN_IN', 'ADMIN_OUT', 'ADMIN_SET']:
                movement_info = f"Admin {row['movement_type'].split('_')[1]}"
            elif row['movement_type'] == 'IN':
                movement_info = "Stock In"
            elif row['movement_type'] == 'OUT':
                movement_info = "Stock Out"
            elif row['movement_type'] == 'PRODUCTION':
                movement_info = "Production"
            
            # Build tracking info
            tracking_parts = []
            if row.get('batch_nr'):
                tracking_parts.append(f"Batch: {row['batch_nr']}")
            if row.get('invoice_nr'):
                tracking_parts.append(f"Inv: {row['invoice_nr']}")
            if row.get('po_nr'):
                tracking_parts.append(f"PO: {row['po_nr']}")
            
            tracking_info = " | ".join(tracking_parts) if tracking_parts else "-"
            
            # User color coding
            user_display = row['user_id']
            if 'admin' in row['user_id'].lower():
                user_display = f"🔧 {row['user_id']}"
            elif 'manager' in row['user_id'].lower():
                user_display = f"👨‍💼 {row['user_id']}"
            
            # Category color coding
            category_icon = {
                'Final Product': '🔥',
                'Raw Material': '🧪',
                'Pre-Final': '⚙️'
            }
            category_display = f"{category_icon.get(row['category'], '📦')} {row['category']}"
            
            display_data.append({
                'Date': row['date_time'][:16],
                'Branch': row['branch_name'],
                'Category': category_display,
                'Item': row['item_name'],
                'Movement': movement_info,
                'Quantity': f"{row['quantity']} {row['unit']}",
                'Reference': row['reference'][:30] + "..." if row['reference'] and len(row['reference']) > 30 else (row['reference'] or '-'),
                'Tracking': tracking_info,
                'User': user_display
            })
        
        if display_data:
            movements_display_df = pd.DataFrame(display_data)
            st.dataframe(movements_display_df, use_container_width=True, height=400)
            
            # Summary statistics
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_movements = len(movements_df)
                st.metric("Total Movements", total_movements)
            
            with col2:
                admin_actions = len(movements_df[movements_df['movement_type'].str.contains('ADMIN')])
                st.metric("Admin Actions", admin_actions)
            
            with col3:
                transfers = len(movements_df[movements_df['movement_type'].str.contains('TRANSFER')])
                st.metric("Transfers", transfers)
            
            with col4:
                production_moves = len(movements_df[movements_df['movement_type'] == 'PRODUCTION'])
                st.metric("Production", production_moves)
            
            # Show activity breakdown by category
            st.subheader("📊 Movement Breakdown")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                final_product_moves = len(movements_df[movements_df['category'] == 'Final Product'])
                st.metric("🔥 Final Products", final_product_moves)
            
            with col2:
                raw_material_moves = len(movements_df[movements_df['category'] == 'Raw Material'])
                st.metric("🧪 Raw Materials", raw_material_moves)
            
            with col3:
                pre_final_moves = len(movements_df[movements_df['category'] == 'Pre-Final'])
                st.metric("⚙️ Components", pre_final_moves)
            
            # User activity comparison
            if not movements_df.empty:
                st.subheader("👥 Activity by User Type")
                admin_count = len(movements_df[movements_df['user_id'].str.contains('admin', case=False)])
                manager_count = len(movements_df[movements_df['user_id'].str.contains('manager', case=False)])
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("🔧 Admin Actions", admin_count)
                with col2:
                    st.metric("👨‍💼 Manager Actions", manager_count)
        else:
            st.info("No movements found with the selected filters.")
    else:
        st.info("📊 No stock movements found.")
        st.markdown("""
        **Movements will appear here when:**
        - ✅ Stock is updated (IN/OUT)
        - ✅ Items are transferred between branches  
        - ✅ Products are produced
        - ✅ Admin makes stock adjustments
        - ✅ Any inventory changes occur
        
        **Enhanced Tracking includes:**
        - 📋 Batch numbers
        - 🧾 Invoice numbers  
        - 📝 PO numbers
        - 👤 User identification
        - 🏪 Branch information
        """)
    """Enhanced user management"""
    if not check_permission('warehouse_manager'):
        st.error("❌ Access denied.")
        return
    
    st.header("👥 User Management")
    
    # Show current users
    conn = sqlite3.connect('inventory.db')
    users_df = pd.read_sql_query("SELECT username, role, full_name, last_login FROM users ORDER BY role, username", conn)
    conn.close()
    
    st.subheader("👤 Current Users")
    
    if not users_df.empty:
        # Format display
        role_icons = {
            "warehouse_manager": "👨‍💼",
            "boss": "👔", 
            "viewer": "👁️",
            "admin": "🔧"
        }
        
        users_df['Role'] = users_df['role'].map(lambda x: f"{role_icons.get(x, '👤')} {x.replace('_', ' ').title()}")
        
        display_df = users_df[['username', 'Role', 'full_name', 'last_login']]
        display_df.columns = ['Username', 'Access Level', 'Full Name', 'Last Login']
        
        st.dataframe(display_df, use_container_width=True)
    
    # Tab layout for mobile
    tab1, tab2 = st.tabs(["➕ Add User", "🔒 Manage Users"])
    
    with tab1:
        st.subheader("Add New User")
        
        with st.form("add_user_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                new_username = st.text_input("Username", placeholder="e.g., john_smith")
                new_password = st.text_input("Password", type="password", placeholder="Strong password")
                new_full_name = st.text_input("Full Name", placeholder="e.g., John Smith")
            
            with col2:
                new_role = st.selectbox("Access Level", ["viewer", "admin", "boss", "warehouse_manager"])
                
                role_info = {
                    "viewer": "👁️ **Viewer**: Can only see final products by branch (no quantities).",
                    "admin": "🔧 **Admin**: Can update final product stock levels AND transfer between branches.",
                    "boss": "👔 **Boss**: Can view all inventory across branches (read-only).",
                    "warehouse_manager": "👨‍💼 **Manager**: Full access including branch management."
                }
                
                st.info(role_info[new_role])
            
            submitted = st.form_submit_button("➕ Create User", type="primary")
            
            if submitted:
                if new_username and new_password and new_full_name:
                    if len(new_password) < 6:
                        st.error("❌ Password must be at least 6 characters!")
                    else:
                        try:
                            conn = sqlite3.connect('inventory.db')
                            c = conn.cursor()
                            
                            # Check if username exists
                            existing = c.execute("SELECT username FROM users WHERE username = ?", (new_username,)).fetchone()
                            if existing:
                                st.error("❌ Username already exists!")
                            else:
                                password_hash = hashlib.sha256(new_password.encode()).hexdigest()
                                c.execute("INSERT INTO users (username, password_hash, role, full_name, created_date) VALUES (?, ?, ?, ?, ?)",
                                         (new_username, password_hash, new_role, new_full_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                                
                                conn.commit()
                                st.success(f"✅ User '{new_username}' created successfully!")
                                st.info(f"🔑 **Login Details:**\nUsername: `{new_username}`\nPassword: `{new_password}`")
                                st.rerun()
                            
                            conn.close()
                            
                        except sqlite3.Error as e:
                            st.error(f"❌ Database error: {str(e)}")
                else:
                    st.error("❌ Please fill in all fields!")
    
    with tab2:
        st.subheader("🔒 Manage Existing Users")
        
        if not users_df.empty:
            # User management options
            selected_user = st.selectbox(
                "Select User to Manage",
                options=[""] + [u for u in users_df['username'].tolist() if u != st.session_state.username],
                format_func=lambda x: "Select a user..." if x == "" else f"{x} - {users_df[users_df['username']==x]['full_name'].iloc[0] if x else ''}"
            )
            
            if selected_user:
                user_info = users_df[users_df['username'] == selected_user].iloc[0]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Username:** {user_info['username']}")
                    st.write(f"**Name:** {user_info['full_name']}")
                    st.write(f"**Role:** {user_info['Role']}")
                
                with col2:
                    # Reset password
                    new_password = st.text_input("New Password", type="password", placeholder="Leave empty to skip")
                    
                    if st.button("🔒 Reset Password"):
                        if new_password and len(new_password) >= 6:
                            conn = sqlite3.connect('inventory.db')
                            c = conn.cursor()
                            
                            password_hash = hashlib.sha256(new_password.encode()).hexdigest()
                            c.execute("UPDATE users SET password_hash = ? WHERE username = ?", 
                                     (password_hash, selected_user))
                            conn.commit()
                            conn.close()
                            
                            st.success(f"🔒 Password reset for '{selected_user}'!")
                            st.info(f"**New login details:**\nUsername: `{selected_user}`\nPassword: `{new_password}`")
                        else:
                            st.error("❌ Password must be at least 6 characters!")
                
                # Delete user
                st.markdown("---")
                st.subheader("🗑️ Delete User")
                st.warning(f"⚠️ **Delete user:** {selected_user}")
                
                if st.button("🗑️ DELETE USER", type="secondary"):
                    if st.session_state.get('confirm_delete_user') == selected_user:
                        # Delete user
                        conn = sqlite3.connect('inventory.db')
                        c = conn.cursor()
                        c.execute('DELETE FROM users WHERE username = ?', (selected_user,))
                        conn.commit()
                        conn.close()
                        
                        st.success(f"🗑️ User '{selected_user}' deleted successfully!")
                        if 'confirm_delete_user' in st.session_state:
                            del st.session_state['confirm_delete_user']
                        st.rerun()
                    else:
                        st.session_state['confirm_delete_user'] = selected_user
                        st.error("⚠️ Click DELETE USER again to confirm deletion!")

if __name__ == "__main__":
    main()
