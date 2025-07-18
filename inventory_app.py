import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime
import io
import uuid
import hashlib

# ===============================
# DATABASE SETUP & INITIALIZATION
# ===============================

def init_database():
    """Initialize all database tables"""
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
    
    # Items table
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
        created_date TEXT,
        created_by TEXT,
        FOREIGN KEY (final_product_id) REFERENCES items (id),
        FOREIGN KEY (ingredient_id) REFERENCES items (id),
        FOREIGN KEY (branch_id) REFERENCES branches (id)
    )''')
    
    # Stock movements table
    c.execute('''CREATE TABLE IF NOT EXISTS stock_movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id TEXT NOT NULL,
        branch_id INTEGER NOT NULL,
        movement_type TEXT NOT NULL,
        quantity REAL NOT NULL,
        reference TEXT,
        batch_nr TEXT,
        invoice_nr TEXT,
        po_nr TEXT,
        date_time TEXT,
        user_id TEXT,
        from_branch_id INTEGER,
        to_branch_id INTEGER,
        FOREIGN KEY (item_id) REFERENCES items (id),
        FOREIGN KEY (branch_id) REFERENCES branches (id)
    )''')
    
    # Create default users
    users_exist = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if users_exist == 0:
        default_users = [
            ("warehouse_manager", hashlib.sha256("manager123".encode()).hexdigest(), "warehouse_manager", "Warehouse Manager"),
            ("boss", hashlib.sha256("boss123".encode()).hexdigest(), "boss", "Boss/Owner"),
            ("viewer", hashlib.sha256("viewer123".encode()).hexdigest(), "viewer", "Branch Viewer"),
            ("admin", hashlib.sha256("admin123".encode()).hexdigest(), "admin", "Stock Admin")
        ]
        
        for username, password_hash, role, full_name in default_users:
            c.execute("INSERT INTO users (username, password_hash, role, full_name, created_date) VALUES (?, ?, ?, ?, ?)",
                     (username, password_hash, role, full_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    # Create default branches
    branches_exist = c.execute("SELECT COUNT(*) FROM branches").fetchone()[0]
    if branches_exist == 0:
        default_branches = [
            ("MAIN", "Main Warehouse", "Johannesburg", "Main Manager", "011-xxx-xxxx"),
            ("CPT", "Cape Town Branch", "Cape Town", "Cape Town Manager", "021-xxx-xxxx"),
            ("DBN", "Durban Branch", "Durban", "Durban Manager", "031-xxx-xxxx")
        ]
        
        for branch_code, branch_name, location, manager, contact in default_branches:
            c.execute("INSERT INTO branches (branch_code, branch_name, location, manager_name, contact_info, created_date) VALUES (?, ?, ?, ?, ?, ?)",
                     (branch_code, branch_name, location, manager, contact, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    conn.commit()
    conn.close()

def load_sample_data():
    """Load sample inventory data into main branch"""
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    
    # Check if data exists
    items_exist = c.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    if items_exist > 0:
        conn.close()
        return
    
    # Get main branch ID
    main_branch = c.execute("SELECT id FROM branches WHERE branch_code = 'MAIN'").fetchone()
    if not main_branch:
        conn.close()
        return
    
    main_branch_id = main_branch[0]
    
    # Sample data
    sample_items = [
        # Raw Materials
        ("LIG001", "LIGNO", "Raw Material", "kg", 300, 100),
        ("KOH001", "KOH", "Raw Material", "kg", 40, 50),
        ("ETH001", "ETHYLENE GLYCOL", "Raw Material", "kg", 64, 20),
        ("FOR001", "FORMIC ACID", "Raw Material", "kg", 678.5, 250),
        ("BEN001", "BENTONITE CLAY", "Raw Material", "kg", 40, 100),
        
        # Pre-Final Components
        ("LIB001", "LITHIUM BLACK POWDER", "Pre-Final", "kg", 2000, 500),
        ("2LB001", "2L BOXES", "Pre-Final", "pieces", 325, 50),
        ("6LB001", "6L BOXES", "Pre-Final", "pieces", 146, 50),
        ("9LB001", "9L BOXES", "Pre-Final", "pieces", 2, 50),
        ("2LE001", "2L EMPTY EXTINGUISHERS", "Pre-Final", "pieces", 9, 10),
        
        # Final Products
        ("LB9L001", "LITHIUM BLACK 9L", "Final Product", "pieces", 25, 20),
        ("LB6L001", "LITHIUM BLACK 6L", "Final Product", "pieces", 35, 15),
        ("LB2L001", "LITHIUM BLACK 2L", "Final Product", "pieces", 45, 10),
        ("SH20001", "SHIELD 20KG", "Final Product", "pieces", 15, 5),
        ("CT9L001", "CAPE TOWN 9L", "Final Product", "pieces", 12, 8),
        ("PT9L001", "PINE TOWN 9L", "Final Product", "pieces", 18, 10),
    ]
    
    for item_id, name, category, unit, current_stock, min_stock in sample_items:
        c.execute('''INSERT INTO items (id, branch_id, name, category, unit, current_stock, min_stock, cost_per_unit, location, warehouse_area, created_date, created_by)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (item_id, main_branch_id, name, category, unit, current_stock, min_stock, 0, "Main", "General",
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "system"))
    
    # Add sample BOM data
    sample_bom = [
        # LITHIUM BLACK 9L recipe
        ("LB9L001", "LIB001", 2.5),  # 2.5kg Lithium Black Powder
        ("LB9L001", "9LB001", 1),    # 1x 9L Box
        ("LB9L001", "9LS001", 1),    # 1x 9L Sticker
        
        # LITHIUM BLACK 6L recipe  
        ("LB6L001", "LIB001", 1.8),  # 1.8kg Lithium Black Powder
        ("LB6L001", "6LB001", 1),    # 1x 6L Box
        ("LB6L001", "6LS001", 1),    # 1x 6L Sticker
        ("LB6L001", "6LE001", 1),    # 1x 6L Empty Extinguisher
        
        # LITHIUM BLACK 2L recipe
        ("LB2L001", "LIB001", 0.8),  # 0.8kg Lithium Black Powder
        ("LB2L001", "2LB001", 1),    # 1x 2L Box
        ("LB2L001", "2LS001", 1),    # 1x 2L Sticker
        ("LB2L001", "2LE001", 1),    # 1x 2L Empty Extinguisher
    ]
    
    for final_product_id, ingredient_id, quantity_required in sample_bom:
        c.execute('''INSERT INTO bom (final_product_id, ingredient_id, quantity_required, branch_id, created_date, created_by)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (final_product_id, ingredient_id, quantity_required, main_branch_id,
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "system"))
    
    conn.commit()
    conn.close()

# ===============================
# AUTHENTICATION & PERMISSIONS
# ===============================

def authenticate_user(username, password):
    """Authenticate user and return role"""
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    result = c.execute("SELECT role, full_name FROM users WHERE username = ? AND password_hash = ?", 
                      (username, password_hash)).fetchone()
    
    if result:
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
    permissions = {
        'warehouse_manager': ['warehouse_manager'],
        'boss': ['boss', 'warehouse_manager'],
        'admin': ['admin'],
        'viewer': ['viewer']
    }
    
    return user_role in permissions.get(required_role, [])

# ===============================
# DATABASE OPERATIONS
# ===============================

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

def get_items_by_role(user_role, branch_id=None):
    """Get items based on user role"""
    conn = sqlite3.connect('inventory.db')
    
    if user_role == "viewer":
        # Viewers only see final products
        query = """SELECT i.*, b.branch_name, b.branch_code 
                   FROM items i 
                   JOIN branches b ON i.branch_id = b.id 
                   WHERE i.category = 'Final Product'"""
    else:
        # Others see all items
        query = """SELECT i.*, b.branch_name, b.branch_code 
                   FROM items i 
                   JOIN branches b ON i.branch_id = b.id"""
    
    if branch_id:
        query += f" AND i.branch_id = {branch_id}"
    
    query += " ORDER BY b.branch_name, i.category, i.name"
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def add_branch(branch_code, branch_name, location="", manager_name="", contact_info=""):
    """Add new branch"""
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    c.execute("INSERT INTO branches (branch_code, branch_name, location, manager_name, contact_info, created_date) VALUES (?, ?, ?, ?, ?, ?)",
              (branch_code, branch_name, location, manager_name, contact_info, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

def update_stock(item_id, branch_id, quantity, movement_type, reference="", batch_nr="", invoice_nr="", po_nr="", user_id="system"):
    """Update stock and record movement"""
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    
    # Update stock
    if movement_type in ['IN', 'ADMIN_IN', 'TRANSFER_IN', 'PRODUCTION']:
        c.execute("UPDATE items SET current_stock = current_stock + ? WHERE id = ? AND branch_id = ?", 
                 (quantity, item_id, branch_id))
    else:
        c.execute("UPDATE items SET current_stock = current_stock - ? WHERE id = ? AND branch_id = ?", 
                 (quantity, item_id, branch_id))
    
    # Record movement
    c.execute('''INSERT INTO stock_movements (item_id, branch_id, movement_type, quantity, reference, batch_nr, invoice_nr, po_nr, date_time, user_id)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (item_id, branch_id, movement_type, quantity, reference, batch_nr, invoice_nr, po_nr,
               datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
    
    conn.commit()
    conn.close()

def transfer_stock_between_branches(item_id, from_branch_id, to_branch_id, quantity, reference="", batch_nr="", invoice_nr="", po_nr="", user_id="system"):
    """Transfer stock between branches"""
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    
    try:
        # Check source stock
        from_item = c.execute("SELECT current_stock FROM items WHERE id = ? AND branch_id = ?", 
                            (item_id, from_branch_id)).fetchone()
        
        if not from_item or from_item[0] < quantity:
            conn.close()
            return False, "Insufficient stock in source branch"
        
        # Create item in destination if needed
        to_item = c.execute("SELECT current_stock FROM items WHERE id = ? AND branch_id = ?", 
                          (item_id, to_branch_id)).fetchone()
        
        if not to_item:
            item_details = c.execute("SELECT name, category, unit, min_stock, cost_per_unit, location, warehouse_area FROM items WHERE id = ? AND branch_id = ?", 
                                   (item_id, from_branch_id)).fetchone()
            
            if item_details:
                c.execute('''INSERT INTO items (id, branch_id, name, category, unit, current_stock, min_stock, cost_per_unit, location, warehouse_area, created_date, created_by)
                             VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)''',
                         (item_id, to_branch_id, item_details[0], item_details[1], item_details[2], 
                          item_details[3], item_details[4], item_details[5], item_details[6],
                          datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
        
        # Update stocks
        c.execute("UPDATE items SET current_stock = current_stock - ? WHERE id = ? AND branch_id = ?", 
                 (quantity, item_id, from_branch_id))
        c.execute("UPDATE items SET current_stock = current_stock + ? WHERE id = ? AND branch_id = ?", 
                 (quantity, item_id, to_branch_id))
        
        # Record movements
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        c.execute('''INSERT INTO stock_movements (item_id, branch_id, movement_type, quantity, reference, batch_nr, invoice_nr, po_nr, date_time, user_id, from_branch_id, to_branch_id)
                     VALUES (?, ?, 'TRANSFER_OUT', ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (item_id, from_branch_id, quantity, reference, batch_nr, invoice_nr, po_nr, timestamp, user_id, from_branch_id, to_branch_id))
        
        c.execute('''INSERT INTO stock_movements (item_id, branch_id, movement_type, quantity, reference, batch_nr, invoice_nr, po_nr, date_time, user_id, from_branch_id, to_branch_id)
                     VALUES (?, ?, 'TRANSFER_IN', ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (item_id, to_branch_id, quantity, reference, batch_nr, invoice_nr, po_nr, timestamp, user_id, from_branch_id, to_branch_id))
        
        conn.commit()
        conn.close()
        return True, f"Successfully transferred {quantity} units"
        
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Transfer failed: {str(e)}"

def get_bom(final_product_id, branch_id):
    """Get Bill of Materials for a product in a specific branch"""
    conn = sqlite3.connect('inventory.db')
    query = '''SELECT b.*, i.name as ingredient_name, i.unit, i.current_stock
               FROM bom b
               JOIN items i ON b.ingredient_id = i.id AND b.branch_id = i.branch_id
               WHERE b.final_product_id = ? AND b.branch_id = ?'''
    df = pd.read_sql_query(query, conn, params=[final_product_id, branch_id])
    conn.close()
    return df

def add_bom_item(final_product_id, ingredient_id, quantity_required, branch_id, user_id):
    """Add item to Bill of Materials"""
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO bom (final_product_id, ingredient_id, quantity_required, branch_id, created_date, created_by)
                 VALUES (?, ?, ?, ?, ?, ?)''', 
              (final_product_id, ingredient_id, quantity_required, branch_id, 
               datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
    conn.commit()
    conn.close()

def delete_bom_item(final_product_id, ingredient_id, branch_id):
    """Remove item from Bill of Materials"""
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    c.execute('DELETE FROM bom WHERE final_product_id = ? AND ingredient_id = ? AND branch_id = ?', 
              (final_product_id, ingredient_id, branch_id))
    conn.commit()
    conn.close()

def produce_item(final_product_id, branch_id, quantity_to_produce, user_id):
    """Produce final product and automatically deduct ingredients based on BOM"""
    bom_df = get_bom(final_product_id, branch_id)
    
    if bom_df.empty:
        return False, "No Bill of Materials found for this product"
    
    # Check if enough ingredients available
    insufficient_ingredients = []
    for _, row in bom_df.iterrows():
        required_qty = row['quantity_required'] * quantity_to_produce
        if row['current_stock'] < required_qty:
            insufficient_ingredients.append(f"{row['ingredient_name']}: Need {required_qty}, Have {row['current_stock']}")
    
    if insufficient_ingredients:
        return False, f"Insufficient ingredients: {'; '.join(insufficient_ingredients)}"
    
    try:
        # Deduct ingredients
        for _, row in bom_df.iterrows():
            required_qty = row['quantity_required'] * quantity_to_produce
            update_stock(row['ingredient_id'], branch_id, required_qty, 'OUT', 
                        f'Production of {quantity_to_produce} x {final_product_id}', '', '', '', user_id)
        
        # Add final product to stock
        update_stock(final_product_id, branch_id, quantity_to_produce, 'PRODUCTION', 
                    f'Produced {quantity_to_produce} units', '', '', '', user_id)
        
        return True, f"Successfully produced {quantity_to_produce} units"
    
    except Exception as e:
        return False, f"Error during production: {str(e)}"

def clean_duplicate_movements():
    """Clean up duplicate movement records"""
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    
    try:
        # Remove duplicate movements (keep only the first occurrence)
        c.execute('''
            DELETE FROM stock_movements 
            WHERE id NOT IN (
                SELECT MIN(id) 
                FROM stock_movements 
                GROUP BY item_id, branch_id, movement_type, quantity, date_time, user_id, from_branch_id, to_branch_id
            )
        ''')
        
        deleted = c.rowcount
        conn.commit()
        conn.close()
        return deleted
    except Exception as e:
        conn.rollback()
        conn.close()
        return 0

def add_item(item_id, name, category, unit, current_stock, min_stock, branch_id, user_id):
    """Add new item to branch"""
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    c.execute('''INSERT INTO items (id, branch_id, name, category, unit, current_stock, min_stock, cost_per_unit, location, warehouse_area, created_date, created_by)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (item_id, branch_id, name, category, unit, current_stock, min_stock, 0, "Main", "General",
               datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id))
    conn.commit()
    conn.close()

# ===============================
# LOGIN SYSTEM
# ===============================

def show_login():
    """Show login page"""
    st.markdown("""
    <style>
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
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="login-header">
        <div style="font-size: 3rem; margin-bottom: 0.5rem;">🔥</div>
        <h1 style="margin: 0; font-size: 2rem;">FLAMEBLOCK</h1>
        <h2 style="margin: 0; font-size: 1.6rem; opacity: 0.9;">MULTI-BRANCH INVENTORY</h2>
        <p style="margin: 0.5rem 0 0 0; font-size: 1rem; opacity: 0.8;">Professional Stock Control System</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("login_form"):
        st.markdown("#### 🔐 Secure Access")
        username = st.text_input("👤 Username", placeholder="Enter username")
        password = st.text_input("🔒 Password", type="password", placeholder="Enter password")
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
                    st.error("❌ Invalid credentials")
            else:
                st.error("❌ Please enter username and password")
    
    st.markdown("---")
    st.markdown("**🔐 Secure Access System**")
    st.info("Contact your system administrator for login credentials.")

# ===============================
# NAVIGATION SYSTEM
# ===============================

def get_navigation_items(user_role):
    """Get navigation items based on user role"""
    if user_role == "viewer":
        return [
            ("🏪", "Branches", "viewer_branches"),
            ("📦", "Products", "viewer_products")
        ]
    elif user_role == "admin":
        return [
            ("📊", "Dashboard", "admin_dashboard"),
            ("🔄", "Update Stock", "admin_update"),
            ("🔀", "Transfer", "admin_transfer"),
            ("📈", "Movements", "admin_movements")
        ]
    elif user_role == "boss":
        return [
            ("📊", "Dashboard", "boss_dashboard"),
            ("🏪", "Branches", "boss_branches"),
            ("📦", "Stock View", "boss_stock"),
            ("📈", "Movements", "boss_movements"),
            ("📋", "Reports", "boss_reports")
        ]
    elif user_role == "warehouse_manager":
        return [
            ("📊", "Dashboard", "manager_dashboard"),
            ("🏪", "Branches", "manager_branches"),
            ("📦", "Stock", "manager_stock"),
            ("🔄", "Transfers", "manager_transfers"),
            ("🏭", "Production", "manager_production"),
            ("🧾", "BOM", "manager_bom"),
            ("⚙️", "Items", "manager_items"),
            ("📈", "Movements", "manager_movements"),
            ("👥", "Users", "manager_users")
        ]
    return []

def show_navigation(user_role):
    """Show navigation based on user role"""
    menu_items = get_navigation_items(user_role)
    
    if 'current_page' not in st.session_state:
        st.session_state.current_page = menu_items[0][2] if menu_items else "dashboard"
    
    # Navigation style
    st.markdown("""
    <style>
    .nav-container {
        background: linear-gradient(90deg, #FF4B4B 0%, #FF6B6B 100%);
        padding: 0.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="nav-container">', unsafe_allow_html=True)
    
    cols = st.columns(len(menu_items))
    
    for i, (icon, label, page_key) in enumerate(menu_items):
        with cols[i]:
            button_text = f"{icon}\n{label}"
            if st.button(button_text, key=f"nav_{page_key}", use_container_width=True):
                st.session_state.current_page = page_key
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    return st.session_state.current_page

# ===============================
# VIEWER PAGES
# ===============================

def show_viewer_branches():
    """Viewer: Select branch to view final products"""
    st.header("🏪 Select Branch")
    
    branches_df = get_all_branches()
    
    if not branches_df.empty:
        selected_branch_id = st.selectbox(
            "🏪 Choose Branch to View",
            options=branches_df['id'].tolist(),
            format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]} - {branches_df[branches_df['id']==x]['location'].iloc[0]}"
        )
        
        if selected_branch_id:
            branch_info = branches_df[branches_df['id'] == selected_branch_id].iloc[0]
            
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #FF4B4B 0%, #FF6B6B 100%); 
                        padding: 1rem; border-radius: 10px; color: white; margin-bottom: 1rem;">
                <h3 style="margin: 0;">🏪 {branch_info['branch_name']}</h3>
                <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">📍 {branch_info['location']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Get final products for this branch
            items_df = get_items_by_role("viewer", selected_branch_id)
            
            if not items_df.empty:
                st.subheader("🔥 Available Products")
                
                for _, item in items_df.iterrows():
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.markdown(f"**{item['name']}**")
                    
                    with col2:
                        if item['current_stock'] > 0:
                            st.success("✅ Available")
                        else:
                            st.error("❌ Out of Stock")
                
                # Summary
                st.markdown("---")
                col1, col2 = st.columns(2)
                
                with col1:
                    available = len(items_df[items_df['current_stock'] > 0])
                    st.metric("✅ Available", available)
                
                with col2:
                    out_of_stock = len(items_df[items_df['current_stock'] <= 0])
                    st.metric("❌ Out of Stock", out_of_stock)
            else:
                st.info(f"No final products found in {branch_info['branch_name']}")
    else:
        st.error("No branches configured")

def show_viewer_products():
    """Viewer: View all final products across branches"""
    st.header("📦 All Final Products")
    
    branches_df = get_all_branches()
    items_df = get_items_by_role("viewer")
    
    if not branches_df.empty and not items_df.empty:
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
    else:
        st.info("No final products found")

# ===============================
# ADMIN PAGES
# ===============================

def show_admin_dashboard():
    """Admin: Dashboard for final products"""
    st.header("🔧 Stock Admin Dashboard")
    
    branches_df = get_all_branches()
    items_df = get_items_by_role("admin")
    
    if not items_df.empty:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Final Products", len(items_df))
        
        with col2:
            st.metric("Branches", len(branches_df))
        
        with col3:
            total_stock = items_df['current_stock'].sum()
            st.metric("Total Units", int(total_stock))
        
        with col4:
            out_of_stock = len(items_df[items_df['current_stock'] <= 0])
            st.metric("Out of Stock", out_of_stock)
        
        # Branch overview
        st.subheader("📊 Stock by Branch")
        
        for _, branch in branches_df.iterrows():
            branch_items = items_df[items_df['branch_id'] == branch['id']]
            
            if not branch_items.empty:
                with st.expander(f"🏪 {branch['branch_name']} ({len(branch_items)} products)"):
                    display_df = branch_items[['name', 'current_stock', 'min_stock', 'unit']].copy()
                    display_df.columns = ['Product', 'Current', 'Min', 'Unit']
                    st.dataframe(display_df, use_container_width=True)
    else:
        st.info("No final products found")

def show_admin_update():
    """Admin: Update final product stock with clear explanations"""
    st.header("🔄 Update Final Product Stock")
    
    # Add explanation of operations
    st.info("""
    📝 **Stock Update Operations:**
    - **SET**: Sets exact stock level (e.g., SET 50 = stock becomes exactly 50)
    - **ADD**: Increases current stock (e.g., ADD 10 = adds 10 to current stock)  
    - **SUBTRACT**: Decreases current stock (e.g., SUBTRACT 5 = removes 5 from current stock)
    """)
    
    branches_df = get_all_branches()
    
    # Branch selection
    selected_branch_id = st.selectbox(
        "🏪 Select Branch",
        options=branches_df['id'].tolist(),
        format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]}"
    )
    
    if selected_branch_id:
        items_df = get_items_by_role("admin", selected_branch_id)
        
        if not items_df.empty:
            # Current stock display
            st.subheader("📦 Current Stock")
            display_df = items_df[['name', 'current_stock', 'unit']].copy()
            display_df.columns = ['Product', 'Current Stock', 'Unit']
            st.dataframe(display_df, use_container_width=True)
            
            # Update form
            st.subheader("🔄 Update Stock")
            
            with st.form("admin_update_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    selected_item = st.selectbox(
                        "Product",
                        options=items_df['id'].tolist(),
                        format_func=lambda x: f"{items_df[items_df['id']==x]['name'].iloc[0]} (Current: {items_df[items_df['id']==x]['current_stock'].iloc[0]})"
                    )
                    
                    update_type = st.selectbox("Operation", ["SET", "ADD", "SUBTRACT"])
                    quantity = st.number_input("Quantity", min_value=0.0, value=0.0)
                    
                    # Show preview of operation
                    if selected_item:
                        current_stock = items_df[items_df['id'] == selected_item]['current_stock'].iloc[0]
                        if update_type == "SET":
                            st.info(f"📊 Result: Stock will be set to **{quantity}**")
                        elif update_type == "ADD":
                            new_stock = current_stock + quantity
                            st.info(f"📊 Result: {current_stock} + {quantity} = **{new_stock}**")
                        elif update_type == "SUBTRACT":
                            new_stock = max(0, current_stock - quantity)
                            st.info(f"📊 Result: {current_stock} - {quantity} = **{new_stock}**")
                
                with col2:
                    reference = st.text_input("Reference", placeholder="Reason for update")
                    batch_nr = st.text_input("Batch Number", placeholder="Optional")
                    invoice_nr = st.text_input("Invoice Number", placeholder="Optional")
                
                submitted = st.form_submit_button("🔄 Update Stock", type="primary")
                
                if submitted and selected_item and quantity >= 0:
                    current_item = items_df[items_df['id'] == selected_item].iloc[0]
                    
                    if update_type == "SET":
                        # Set absolute value
                        conn = sqlite3.connect('inventory.db')
                        c = conn.cursor()
                        old_stock = current_item['current_stock']
                        c.execute("UPDATE items SET current_stock = ? WHERE id = ? AND branch_id = ?", 
                                 (quantity, selected_item, selected_branch_id))
                        
                        c.execute('''INSERT INTO stock_movements (item_id, branch_id, movement_type, quantity, reference, batch_nr, invoice_nr, date_time, user_id)
                                     VALUES (?, ?, 'ADMIN_SET', ?, ?, ?, ?, ?, ?)''',
                                  (selected_item, selected_branch_id, quantity, f"SET from {old_stock} to {quantity} - {reference}", 
                                   batch_nr, invoice_nr, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.username))
                        
                        conn.commit()
                        conn.close()
                        
                        st.success(f"✅ Set {current_item['name']} from {old_stock} to {quantity} {current_item['unit']}")
                        st.rerun()
                    
                    elif update_type == "ADD":
                        if quantity > 0:
                            update_stock(selected_item, selected_branch_id, quantity, 'ADMIN_IN', 
                                        f"Added {quantity} - {reference}", batch_nr, invoice_nr, "", st.session_state.username)
                            new_stock = current_item['current_stock'] + quantity
                            st.success(f"✅ Added {quantity} {current_item['unit']} (New total: {new_stock})")
                            st.rerun()
                        else:
                            st.error("❌ Quantity must be greater than 0 for ADD")
                    
                    elif update_type == "SUBTRACT":
                        if quantity > 0 and current_item['current_stock'] >= quantity:
                            update_stock(selected_item, selected_branch_id, quantity, 'ADMIN_OUT', 
                                        f"Subtracted {quantity} - {reference}", batch_nr, invoice_nr, "", st.session_state.username)
                            new_stock = current_item['current_stock'] - quantity
                            st.success(f"✅ Subtracted {quantity} {current_item['unit']} (New total: {new_stock})")
                            st.rerun()
                        elif quantity <= 0:
                            st.error("❌ Quantity must be greater than 0 for SUBTRACT")
                        else:
                            st.error(f"❌ Cannot subtract {quantity}. Only {current_item['current_stock']} available")
        else:
            st.info("No final products in this branch")

def show_admin_transfer():
    """Admin: Transfer final products between branches"""
    st.header("🔀 Transfer Final Products")
    
    branches_df = get_all_branches()
    
    if len(branches_df) < 2:
        st.warning("Need at least 2 branches for transfers")
        return
    
    # Branch selection
    col1, col2 = st.columns(2)
    
    with col1:
        from_branch_id = st.selectbox(
            "📤 From Branch",
            options=branches_df['id'].tolist(),
            format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]}"
        )
    
    with col2:
        to_branches = [b for b in branches_df['id'].tolist() if b != from_branch_id]
        to_branch_id = st.selectbox(
            "📥 To Branch",
            options=to_branches,
            format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]}"
        )
    
    if from_branch_id and to_branch_id:
        # Get available items
        from_items = get_items_by_role("admin", from_branch_id)
        available_items = from_items[from_items['current_stock'] > 0]
        
        if not available_items.empty:
            # Transfer form
            with st.form("admin_transfer_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    selected_item = st.selectbox(
                        "📦 Product",
                        options=available_items['id'].tolist(),
                        format_func=lambda x: f"{available_items[available_items['id']==x]['name'].iloc[0]} ({available_items[available_items['id']==x]['current_stock'].iloc[0]})"
                    )
                    
                    if selected_item:
                        max_qty = available_items[available_items['id'] == selected_item]['current_stock'].iloc[0]
                        quantity = st.number_input("Quantity", min_value=0.0, max_value=max_qty, value=1.0)
                
                with col2:
                    reference = st.text_input("Reference", placeholder="Transfer reason")
                    batch_nr = st.text_input("Batch Number", placeholder="Optional")
                    invoice_nr = st.text_input("Invoice Number", placeholder="Optional")
                
                submitted = st.form_submit_button("🔀 Transfer", type="primary")
                
                if submitted and selected_item and quantity > 0:
                    success, message = transfer_stock_between_branches(
                        selected_item, from_branch_id, to_branch_id, quantity, 
                        f"ADMIN TRANSFER: {reference}", batch_nr, invoice_nr, "", st.session_state.username
                    )
                    
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        else:
            st.warning("No final products with stock in source branch")

def show_admin_movements():
    """Admin: View movements with proper filtering and cleanup"""
    st.header("📈 Stock Movements")
    
    # Cleanup option for admin
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("📊 Final Product Movement Records")
    
    with col2:
        if st.button("🧹 Clean Duplicates", type="secondary", help="Remove duplicate movement records"):
            deleted = clean_duplicate_movements()
            if deleted > 0:
                st.success(f"✅ Cleaned {deleted} duplicate records!")
                st.rerun()
            else:
                st.info("No duplicates found")
    
    # Filters
    col1, col2 = st.columns(2)
    
    with col1:
        branches_df = get_all_branches()
        branch_filter = st.selectbox(
            "🏪 Branch",
            options=["All"] + branches_df['branch_name'].tolist()
        )
    
    with col2:
        user_filter = st.selectbox(
            "👤 User",
            options=["All", "My Actions", "Manager Actions"]
        )
    
    # Get movements with proper filtering and deduplication
    conn = sqlite3.connect('inventory.db')
    
    query = '''
        SELECT DISTINCT sm.*, i.name as item_name, i.unit, b.branch_name
        FROM stock_movements sm
        JOIN items i ON sm.item_id = i.id 
        JOIN branches b ON sm.branch_id = b.id
        WHERE i.category = 'Final Product'
        AND EXISTS (SELECT 1 FROM items i2 WHERE i2.id = sm.item_id AND i2.branch_id = sm.branch_id)
    '''
    
    params = []
    
    # Branch filtering
    if branch_filter != "All":
        branch_id = branches_df[branches_df['branch_name'] == branch_filter]['id'].iloc[0]
        query += " AND sm.branch_id = ?"
        params.append(branch_id)
    
    # User filtering - Admin sees their actions and manager actions
    if user_filter == "My Actions":
        query += " AND sm.user_id = ?"
        params.append(st.session_state.username)
    elif user_filter == "Manager Actions":
        query += " AND sm.user_id LIKE '%manager%'"
    
    query += " ORDER BY sm.date_time DESC, sm.id DESC LIMIT 100"
    
    movements_df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if not movements_df.empty:
        st.info(f"📊 Found {len(movements_df)} movements")
        
        # Display movements
        display_data = []
        
        for _, row in movements_df.iterrows():
            tracking_info = []
            if row.get('batch_nr'):
                tracking_info.append(f"Batch: {row['batch_nr']}")
            if row.get('invoice_nr'):
                tracking_info.append(f"Inv: {row['invoice_nr']}")
            
            tracking = " | ".join(tracking_info) if tracking_info else "-"
            
            # Format movement type
            movement_type = row['movement_type']
            if movement_type == 'ADMIN_SET':
                movement_type = 'SET Stock'
            elif movement_type == 'ADMIN_IN':
                movement_type = 'ADD Stock'
            elif movement_type == 'ADMIN_OUT':
                movement_type = 'SUBTRACT Stock'
            elif movement_type == 'TRANSFER_OUT':
                movement_type = 'Transfer Out'
            elif movement_type == 'TRANSFER_IN':
                movement_type = 'Transfer In'
            
            display_data.append({
                'Date': row['date_time'][:16],
                'Branch': row['branch_name'],
                'Product': row['item_name'],
                'Type': movement_type,
                'Quantity': f"{row['quantity']} {row['unit']}",
                'Tracking': tracking,
                'Reference': row['reference'] or '-',
                'User': row['user_id']
            })
        
        if display_data:
            movements_display_df = pd.DataFrame(display_data)
            st.dataframe(movements_display_df, use_container_width=True, height=400)
            
            # Summary
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Movements", len(movements_df))
            
            with col2:
                my_actions = len(movements_df[movements_df['user_id'] == st.session_state.username])
                st.metric("My Actions", my_actions)
            
            with col3:
                manager_actions = len(movements_df[movements_df['user_id'].str.contains('manager', case=False)])
                st.metric("Manager Actions", manager_actions)
    else:
        st.info("No movements found with selected filters")
        if branch_filter != "All":
            st.info(f"💡 Try selecting 'All' branches or check if there are any final products in {branch_filter}")

# ===============================
# BOSS PAGES (READ-ONLY)
# ===============================

def show_boss_dashboard():
    """Boss: Overview dashboard"""
    st.header("📊 Management Overview")
    
    branches_df = get_all_branches()
    items_df = get_items_by_role("boss")
    
    # High-level metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Branches", len(branches_df))
    
    with col2:
        st.metric("Total Items", len(items_df))
    
    with col3:
        final_products = len(items_df[items_df['category'] == 'Final Product'])
        st.metric("Final Products", final_products)
    
    with col4:
        critical = len(items_df[items_df['current_stock'] <= 0])
        st.metric("Critical Items", critical)
    
    # Branch performance
    st.subheader("🏪 Branch Performance")
    
    branch_data = []
    for _, branch in branches_df.iterrows():
        branch_items = items_df[items_df['branch_id'] == branch['id']]
        if not branch_items.empty:
            final_count = len(branch_items[branch_items['category'] == 'Final Product'])
            critical_count = len(branch_items[branch_items['current_stock'] <= 0])
            
            branch_data.append({
                'Branch': branch['branch_name'],
                'Location': branch['location'],
                'Total Items': len(branch_items),
                'Final Products': final_count,
                'Critical': critical_count
            })
    
    if branch_data:
        summary_df = pd.DataFrame(branch_data)
        st.dataframe(summary_df, use_container_width=True)

def show_boss_branches():
    """Boss: View all branches"""
    st.header("🏪 Branch Overview")
    
    branches_df = get_all_branches()
    items_df = get_items_by_role("boss")
    
    for _, branch in branches_df.iterrows():
        with st.expander(f"🏪 {branch['branch_name']} - {branch['location']}", expanded=False):
            branch_items = items_df[items_df['branch_id'] == branch['id']]
            
            if not branch_items.empty:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Items", len(branch_items))
                
                with col2:
                    final_products = len(branch_items[branch_items['category'] == 'Final Product'])
                    st.metric("Final Products", final_products)
                
                with col3:
                    critical = len(branch_items[branch_items['current_stock'] <= 0])
                    st.metric("Critical", critical)
            else:
                st.info("No items in this branch")

def show_boss_stock():
    """Boss: View stock across all branches"""
    st.header("📦 Stock Overview")
    
    branches_df = get_all_branches()
    
    # Branch filter
    branch_filter = st.selectbox(
        "🏪 Filter by Branch",
        options=["All Branches"] + branches_df['branch_name'].tolist()
    )
    
    # Category filter
    category_filter = st.selectbox(
        "📦 Category",
        options=["All", "Final Product", "Raw Material", "Pre-Final"]
    )
    
    # Get filtered data
    if branch_filter == "All Branches":
        items_df = get_items_by_role("boss")
    else:
        branch_id = branches_df[branches_df['branch_name'] == branch_filter]['id'].iloc[0]
        items_df = get_items_by_role("boss", branch_id)
    
    if category_filter != "All":
        items_df = items_df[items_df['category'] == category_filter]
    
    if not items_df.empty:
        # Add status
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
        
        # Summary
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

def show_boss_movements():
    """Boss: View all movements"""
    st.header("📈 Movement History")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        branches_df = get_all_branches()
        branch_filter = st.selectbox(
            "🏪 Branch",
            options=["All"] + branches_df['branch_name'].tolist()
        )
    
    with col2:
        category_filter = st.selectbox(
            "📦 Category",
            options=["All", "Final Product", "Raw Material", "Pre-Final"]
        )
    
    with col3:
        user_filter = st.selectbox(
            "👤 User Type",
            options=["All", "Admin", "Manager"]
        )
    
    # Get movements
    conn = sqlite3.connect('inventory.db')
    
    query = '''
        SELECT sm.*, i.name as item_name, i.unit, i.category, b.branch_name
        FROM stock_movements sm
        JOIN items i ON sm.item_id = i.id AND sm.branch_id = i.branch_id
        JOIN branches b ON sm.branch_id = b.id
        WHERE 1=1
    '''
    
    params = []
    
    if branch_filter != "All":
        branch_id = branches_df[branches_df['branch_name'] == branch_filter]['id'].iloc[0]
        query += " AND sm.branch_id = ?"
        params.append(branch_id)
    
    if category_filter != "All":
        query += " AND i.category = ?"
        params.append(category_filter)
    
    if user_filter == "Admin":
        query += " AND sm.user_id = 'admin'"
    elif user_filter == "Manager":
        query += " AND sm.user_id LIKE '%manager%'"
    
    query += " ORDER BY sm.date_time DESC LIMIT 100"
    
    movements_df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if not movements_df.empty:
        display_df = movements_df[['date_time', 'branch_name', 'category', 'item_name', 'movement_type', 'quantity', 'unit', 'user_id']]
        display_df.columns = ['Date', 'Branch', 'Category', 'Item', 'Type', 'Qty', 'Unit', 'User']
        display_df['Date'] = pd.to_datetime(display_df['Date']).dt.strftime('%m-%d %H:%M')
        
        st.dataframe(display_df, use_container_width=True, height=400)
        
        # Summary
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Movements", len(movements_df))
        
        with col2:
            admin_moves = len(movements_df[movements_df['user_id'] == 'admin'])
            st.metric("Admin Actions", admin_moves)
        
        with col3:
            manager_moves = len(movements_df[movements_df['user_id'].str.contains('manager', case=False)])
            st.metric("Manager Actions", manager_moves)

def show_boss_reports():
    """Boss: Management reports"""
    st.header("📋 Management Reports")
    
    items_df = get_items_by_role("boss")
    branches_df = get_all_branches()
    
    if not items_df.empty:
        # Category summary
        st.subheader("📊 Inventory by Category")
        category_summary = items_df.groupby('category').agg({
            'current_stock': 'sum',
            'name': 'count'
        }).rename(columns={'name': 'items', 'current_stock': 'total_stock'})
        
        st.dataframe(category_summary, use_container_width=True)
        
        # Branch summary
        st.subheader("🏪 Inventory by Branch")
        branch_summary = []
        
        for _, branch in branches_df.iterrows():
            branch_items = items_df[items_df['branch_id'] == branch['id']]
            if not branch_items.empty:
                total_stock = branch_items['current_stock'].sum()
                final_products = len(branch_items[branch_items['category'] == 'Final Product'])
                critical = len(branch_items[branch_items['current_stock'] <= 0])
                
                branch_summary.append({
                    'Branch': branch['branch_name'],
                    'Location': branch['location'],
                    'Total Items': len(branch_items),
                    'Final Products': final_products,
                    'Total Stock': int(total_stock),
                    'Critical': critical
                })
        
        if branch_summary:
            summary_df = pd.DataFrame(branch_summary)
            st.dataframe(summary_df, use_container_width=True)
        
        # Critical items
        critical_items = items_df[items_df['current_stock'] <= 0]
        if not critical_items.empty:
            st.subheader("🚨 Critical Items")
            critical_display = critical_items[['branch_name', 'name', 'category', 'current_stock', 'min_stock']]
            critical_display.columns = ['Branch', 'Item', 'Category', 'Current', 'Min Required']
            st.dataframe(critical_display, use_container_width=True)

# ===============================
# WAREHOUSE MANAGER PAGES
# ===============================

def show_manager_dashboard():
    """Manager: Full dashboard"""
    st.header("📊 Warehouse Manager Dashboard")
    
    branches_df = get_all_branches()
    items_df = get_items_by_role("warehouse_manager")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Branches", len(branches_df))
    
    with col2:
        st.metric("Total Items", len(items_df))
    
    with col3:
        final_products = len(items_df[items_df['category'] == 'Final Product'])
        st.metric("Final Products", final_products)
    
    with col4:
        critical = len(items_df[items_df['current_stock'] <= 0])
        st.metric("Critical Items", critical)
    
    # Branch status
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
                
                # Critical items
                critical_items = branch_items[branch_items['current_stock'] <= 0]
                if not critical_items.empty:
                    st.error(f"🚨 Critical items in {branch['branch_name']}:")
                    for _, item in critical_items.iterrows():
                        st.write(f"❌ {item['name']}")

def show_manager_branches():
    """Manager: Branch management"""
    st.header("🏪 Branch Management")
    
    tab1, tab2 = st.tabs(["🏪 View Branches", "➕ Add Branch"])
    
    with tab1:
        branches_df = get_all_branches()
        
        for _, branch in branches_df.iterrows():
            with st.expander(f"🏪 {branch['branch_name']} - {branch['location']}", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Code:** {branch['branch_code']}")
                    st.write(f"**Manager:** {branch['manager_name']}")
                    st.write(f"**Contact:** {branch['contact_info']}")
                
                with col2:
                    st.write(f"**Created:** {branch['created_date'][:10]}")
                    
                    # Branch stats
                    items_df = get_items_by_role("warehouse_manager", branch['id'])
                    if not items_df.empty:
                        st.write(f"**Items:** {len(items_df)}")
                        critical = len(items_df[items_df['current_stock'] <= 0])
                        st.write(f"**Critical:** {critical}")
    
    with tab2:
        st.subheader("➕ Add New Branch")
        
        with st.form("add_branch_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                branch_code = st.text_input("Branch Code", placeholder="e.g., JHB, PE")
                branch_name = st.text_input("Branch Name", placeholder="e.g., Johannesburg Branch")
                location = st.text_input("Location", placeholder="e.g., Johannesburg, GP")
            
            with col2:
                manager_name = st.text_input("Manager Name")
                contact_info = st.text_input("Contact Info")
            
            submitted = st.form_submit_button("🏪 Add Branch", type="primary")
            
            if submitted and branch_code and branch_name:
                try:
                    add_branch(branch_code.upper(), branch_name, location, manager_name, contact_info)
                    st.success(f"✅ Added branch: {branch_name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

def show_manager_stock():
    """Manager: Stock management with proper movement tracking"""
    st.header("📦 Stock Management")
    
    branches_df = get_all_branches()
    
    # Branch selection
    selected_branch_id = st.selectbox(
        "🏪 Select Branch",
        options=branches_df['id'].tolist(),
        format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]}"
    )
    
    if selected_branch_id:
        branch_name = branches_df[branches_df['id'] == selected_branch_id]['branch_name'].iloc[0]
        st.info(f"📍 Managing stock for: **{branch_name}**")
        
        items_df = get_items_by_role("warehouse_manager", selected_branch_id)
        
        # Category filter
        category_filter = st.selectbox("Category", ["All", "Raw Material", "Pre-Final", "Final Product"])
        
        if category_filter != "All":
            items_df = items_df[items_df['category'] == category_filter]
        
        if not items_df.empty:
            # Add status
            def get_status(row):
                if row['current_stock'] <= 0:
                    return "❌ OUT"
                elif row['current_stock'] <= row['min_stock']:
                    return "⚠️ LOW"
                else:
                    return "✅ OK"
            
            items_df['Status'] = items_df.apply(get_status, axis=1)
            
            display_df = items_df[['id', 'name', 'category', 'current_stock', 'unit', 'Status']]
            display_df.columns = ['ID', 'Name', 'Category', 'Stock', 'Unit', 'Status']
            
            st.dataframe(display_df, use_container_width=True, height=300)
            
            # Quick update with better tracking
            st.subheader("⚡ Quick Stock Update")
            
            with st.form("quick_update_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    selected_item = st.selectbox(
                        "Item",
                        options=items_df['id'].tolist(),
                        format_func=lambda x: f"{items_df[items_df['id']==x]['name'].iloc[0]} (Current: {items_df[items_df['id']==x]['current_stock'].iloc[0]})"
                    )
                    quantity = st.number_input("Quantity", value=0.0)
                    movement_type = st.selectbox("Type", ["IN", "OUT"])
                
                with col2:
                    reference = st.text_input("Reference", placeholder="Delivery, sale, adjustment, etc.")
                    batch_nr = st.text_input("Batch Number", placeholder="Optional")
                    invoice_nr = st.text_input("Invoice Number", placeholder="Optional")
                
                submitted = st.form_submit_button("💾 Update Stock", type="primary")
                
                if submitted and selected_item and quantity != 0:
                    try:
                        # Get current item info for feedback
                        current_item = items_df[items_df['id'] == selected_item].iloc[0]
                        old_stock = current_item['current_stock']
                        
                        # Update stock with enhanced tracking
                        update_stock(selected_item, selected_branch_id, abs(quantity), movement_type, 
                                   reference, batch_nr, invoice_nr, "", st.session_state.username)
                        
                        # Calculate new stock for feedback
                        if movement_type == "IN":
                            new_stock = old_stock + abs(quantity)
                            st.success(f"✅ Added {abs(quantity)} {current_item['unit']} to {current_item['name']} (New total: {new_stock})")
                        else:
                            new_stock = max(0, old_stock - abs(quantity))
                            st.success(f"✅ Removed {abs(quantity)} {current_item['unit']} from {current_item['name']} (New total: {new_stock})")
                        
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error updating stock: {str(e)}")
                elif submitted:
                    st.error("❌ Please select an item and enter a non-zero quantity")
            
            # Summary stats
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Items", len(items_df))
            
            with col2:
                in_stock = len(items_df[items_df['current_stock'] > 0])
                st.metric("In Stock", in_stock)
            
            with col3:
                low_stock = len(items_df[items_df['current_stock'] <= items_df['min_stock']])
                st.metric("Low Stock", low_stock)
            
            with col4:
                out_of_stock = len(items_df[items_df['current_stock'] <= 0])
                st.metric("Out of Stock", out_of_stock)
        else:
            st.warning(f"No items found in {branch_name} for the selected category.")
            st.info("💡 Add items using the 'Items' section or transfer from other branches.")

def show_manager_transfers():
    """Manager: Stock transfers"""
    st.header("🔄 Stock Transfers")
    
    branches_df = get_all_branches()
    
    if len(branches_df) < 2:
        st.warning("Need at least 2 branches")
        return
    
    tab1, tab2 = st.tabs(["🔄 Transfer", "📈 History"])
    
    with tab1:
        # Branch selection
        col1, col2 = st.columns(2)
        
        with col1:
            from_branch_id = st.selectbox(
                "📤 From",
                options=branches_df['id'].tolist(),
                format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]}"
            )
        
        with col2:
            to_branches = [b for b in branches_df['id'].tolist() if b != from_branch_id]
            to_branch_id = st.selectbox(
                "📥 To",
                options=to_branches,
                format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]}"
            )
        
        if from_branch_id and to_branch_id:
            # Get available items
            from_items = get_items_by_role("warehouse_manager", from_branch_id)
            available_items = from_items[from_items['current_stock'] > 0]
            
            if not available_items.empty:
                with st.form("transfer_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        selected_item = st.selectbox(
                            "📦 Item",
                            options=available_items['id'].tolist(),
                            format_func=lambda x: f"{available_items[available_items['id']==x]['name'].iloc[0]} ({available_items[available_items['id']==x]['current_stock'].iloc[0]})"
                        )
                        
                        if selected_item:
                            max_qty = available_items[available_items['id'] == selected_item]['current_stock'].iloc[0]
                            quantity = st.number_input("Quantity", min_value=0.0, max_value=max_qty, value=1.0)
                    
                    with col2:
                        reference = st.text_input("Reference")
                        batch_nr = st.text_input("Batch Number")
                    
                    submitted = st.form_submit_button("🔄 Transfer", type="primary")
                    
                    if submitted and selected_item and quantity > 0:
                        success, message = transfer_stock_between_branches(
                            selected_item, from_branch_id, to_branch_id, quantity, 
                            reference, batch_nr, "", "", st.session_state.username
                        )
                        
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
            else:
                st.warning("No items with stock in source branch")
    
    with tab2:
        # Transfer history
        conn = sqlite3.connect('inventory.db')
        transfers_df = pd.read_sql_query('''
            SELECT sm.*, i.name as item_name, i.unit,
                   b1.branch_name as from_branch_name,
                   b2.branch_name as to_branch_name
            FROM stock_movements sm
            JOIN items i ON sm.item_id = i.id AND sm.branch_id = i.branch_id
            LEFT JOIN branches b1 ON sm.from_branch_id = b1.id
            LEFT JOIN branches b2 ON sm.to_branch_id = b2.id
            WHERE sm.movement_type = 'TRANSFER_OUT'
            ORDER BY sm.date_time DESC 
            LIMIT 50
        ''', conn)
        conn.close()
        
        if not transfers_df.empty:
            display_df = transfers_df[['date_time', 'item_name', 'quantity', 'unit', 
                                     'from_branch_name', 'to_branch_name', 'reference', 'user_id']]
            display_df.columns = ['Date', 'Item', 'Qty', 'Unit', 'From', 'To', 'Reference', 'User']
            display_df['Date'] = pd.to_datetime(display_df['Date']).dt.strftime('%m-%d %H:%M')
            
            st.dataframe(display_df, use_container_width=True, height=400)

def show_manager_production():
    """Manager: Production management with BOM integration"""
    st.header("🏭 Production Center")
    
    branches_df = get_all_branches()
    
    # Branch selection
    selected_branch_id = st.selectbox(
        "🏪 Production Branch",
        options=branches_df['id'].tolist(),
        format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]}"
    )
    
    if selected_branch_id:
        branch_name = branches_df[branches_df['id'] == selected_branch_id]['branch_name'].iloc[0]
        st.info(f"🏭 Production at: **{branch_name}**")
        
        items_df = get_items_by_role("warehouse_manager", selected_branch_id)
        final_products = items_df[items_df['category'] == 'Final Product']
        
        if not final_products.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                selected_product = st.selectbox(
                    "🔥 Final Product",
                    options=final_products['id'].tolist(),
                    format_func=lambda x: f"{final_products[final_products['id']==x]['name'].iloc[0]}"
                )
                
                quantity = st.number_input("Quantity to Produce", min_value=1, value=1)
                
                if st.button("🚀 Start Production", type="primary"):
                    if selected_product and quantity > 0:
                        # Use BOM-based production
                        success, message = produce_item(selected_product, selected_branch_id, quantity, st.session_state.username)
                        
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                            # If no BOM, offer simple production
                            if "No Bill of Materials found" in message:
                                st.warning("⚠️ No BOM defined. Using simple production (no ingredient deduction).")
                                if st.button("🔄 Produce Without BOM", type="secondary"):
                                    update_stock(selected_product, selected_branch_id, quantity, 'PRODUCTION', 
                                               f'Simple production: {quantity} units', '', '', '', st.session_state.username)
                                    st.success(f"✅ Produced {quantity} units (no ingredients deducted)!")
                                    st.rerun()
            
            with col2:
                if selected_product:
                    product_info = final_products[final_products['id'] == selected_product].iloc[0]
                    
                    st.subheader("📦 Product Info")
                    st.write(f"**Current Stock:** {product_info['current_stock']} {product_info['unit']}")
                    st.write(f"**Min Stock:** {product_info['min_stock']} {product_info['unit']}")
                    
                    # Show BOM requirements
                    st.subheader("🧾 Recipe (BOM)")
                    bom_df = get_bom(selected_product, selected_branch_id)
                    
                    if not bom_df.empty:
                        st.write(f"**To produce {quantity} units:**")
                        
                        can_produce = True
                        for _, row in bom_df.iterrows():
                            required_qty = row['quantity_required'] * quantity
                            available_qty = row['current_stock']
                            
                            if available_qty >= required_qty:
                                status = "✅"
                                color = "green"
                            else:
                                status = "❌"
                                color = "red"
                                can_produce = False
                            
                            st.markdown(f"{status} **{row['ingredient_name']}**: Need {required_qty} {row['unit']} (Available: {available_qty})")
                        
                        st.markdown("---")
                        if can_produce:
                            st.success("✅ Can produce - All ingredients available")
                        else:
                            st.error("❌ Cannot produce - Insufficient ingredients")
                    else:
                        st.warning("⚠️ No BOM defined for this product")
                        st.info("💡 Create a BOM in the 'BOM' section to enable automatic ingredient deduction")
        else:
            st.warning("No final products found in this branch")
            st.info("💡 Add final products using the 'Items' section")

def show_manager_bom():
    """Manager: Bill of Materials management"""
    st.header("🧾 Bill of Materials (BOM)")
    
    branches_df = get_all_branches()
    
    # Branch selection
    selected_branch_id = st.selectbox(
        "🏪 Select Branch",
        options=branches_df['id'].tolist(),
        format_func=lambda x: f"{branches_df[branches_df['id']==x]['branch_name'].iloc[0]}"
    )
    
    if selected_branch_id:
        branch_name = branches_df[branches_df['id'] == selected_branch_id]['branch_name'].iloc[0]
        items_df = get_items_by_role("warehouse_manager", selected_branch_id)
        final_products = items_df[items_df['category'] == 'Final Product']
        
        if final_products.empty:
            st.warning("No final products found in this branch")
            st.info("💡 Add final products first using the 'Items' section")
            return
        
        st.info(f"📍 Managing BOM for: **{branch_name}**")
        
        tab1, tab2, tab3 = st.tabs(["📋 View BOM", "➕ Add Recipe", "🗑️ Manage Ingredients"])
        
        with tab1:
            st.subheader("📋 Current Bill of Materials")
            
            selected_product = st.selectbox(
                "🔥 Select Final Product",
                options=final_products['id'].tolist(),
                format_func=lambda x: f"{final_products[final_products['id']==x]['name'].iloc[0]}",
                key="view_bom_product"
            )
            
            if selected_product:
                product_name = final_products[final_products['id'] == selected_product]['name'].iloc[0]
                st.markdown(f"**Recipe for: {product_name}**")
                
                bom_df = get_bom(selected_product, selected_branch_id)
                
                if not bom_df.empty:
                    # Show current BOM
                    display_bom = bom_df[['ingredient_name', 'quantity_required', 'unit', 'current_stock']].copy()
                    display_bom.columns = ['Ingredient', 'Required Qty', 'Unit', 'Available Stock']
                    
                    # Add status column
                    def get_ingredient_status(row):
                        if row['Available Stock'] >= row['Required Qty']:
                            return "✅ OK"
                        elif row['Available Stock'] > 0:
                            return "⚠️ LOW"
                        else:
                            return "❌ OUT"
                    
                    display_bom['Status'] = display_bom.apply(get_ingredient_status, axis=1)
                    st.dataframe(display_bom, use_container_width=True)
                    
                    # Production capacity
                    st.subheader("🏭 Production Capacity")
                    if not bom_df.empty:
                        max_production = float('inf')
                        limiting_ingredient = ""
                        
                        for _, row in bom_df.iterrows():
                            possible_qty = int(row['current_stock'] / row['quantity_required'])
                            if possible_qty < max_production:
                                max_production = possible_qty
                                limiting_ingredient = row['ingredient_name']
                        
                        if max_production == float('inf'):
                            max_production = 0
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Max Production", f"{max_production} units")
                        with col2:
                            if limiting_ingredient:
                                st.info(f"🔗 Limited by: {limiting_ingredient}")
                else:
                    st.info("No BOM defined for this product")
                    st.markdown("💡 Use the 'Add Recipe' tab to create one")
        
        with tab2:
            st.subheader("➕ Add Ingredient to Recipe")
            
            # Product selection
            selected_product = st.selectbox(
                "🔥 Final Product",
                options=final_products['id'].tolist(),
                format_func=lambda x: f"{final_products[final_products['id']==x]['name'].iloc[0]}",
                key="add_bom_product"
            )
            
            if selected_product:
                # Available ingredients (Raw Materials and Pre-Final)
                available_ingredients = items_df[items_df['category'].isin(['Raw Material', 'Pre-Final'])]
                
                if not available_ingredients.empty:
                    with st.form("add_bom_form"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            ingredient_id = st.selectbox(
                                "🧪 Ingredient",
                                options=available_ingredients['id'].tolist(),
                                format_func=lambda x: f"{available_ingredients[available_ingredients['id']==x]['name'].iloc[0]} ({available_ingredients[available_ingredients['id']==x]['current_stock'].iloc[0]} {available_ingredients[available_ingredients['id']==x]['unit'].iloc[0]})"
                            )
                        
                        with col2:
                            quantity_required = st.number_input("Quantity Required per Unit", min_value=0.001, value=1.0, step=0.1)
                        
                        submitted = st.form_submit_button("➕ Add to Recipe", type="primary")
                        
                        if submitted and ingredient_id:
                            try:
                                add_bom_item(selected_product, ingredient_id, quantity_required, selected_branch_id, st.session_state.username)
                                ingredient_name = available_ingredients[available_ingredients['id'] == ingredient_id]['name'].iloc[0]
                                product_name = final_products[final_products['id'] == selected_product]['name'].iloc[0]
                                st.success(f"✅ Added {ingredient_name} to {product_name} recipe!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error adding ingredient: {str(e)}")
                else:
                    st.warning("No raw materials or components found")
                    st.info("💡 Add raw materials and components first using the 'Items' section")
        
        with tab3:
            st.subheader("🗑️ Manage Recipe Ingredients")
            
            # Product selection
            selected_product = st.selectbox(
                "🔥 Final Product",
                options=final_products['id'].tolist(),
                format_func=lambda x: f"{final_products[final_products['id']==x]['name'].iloc[0]}",
                key="manage_bom_product"
            )
            
            if selected_product:
                bom_df = get_bom(selected_product, selected_branch_id)
                
                if not bom_df.empty:
                    st.write("**Current Ingredients:**")
                    
                    for _, row in bom_df.iterrows():
                        col1, col2, col3 = st.columns([3, 1, 1])
                        
                        with col1:
                            st.write(f"🧪 **{row['ingredient_name']}**: {row['quantity_required']} {row['unit']}")
                        
                        with col2:
                            # Edit quantity
                            new_qty = st.number_input("", value=float(row['quantity_required']), key=f"qty_{row['ingredient_id']}", min_value=0.001)
                            if new_qty != row['quantity_required']:
                                if st.button("💾", key=f"save_{row['ingredient_id']}"):
                                    add_bom_item(selected_product, row['ingredient_id'], new_qty, selected_branch_id, st.session_state.username)
                                    st.success("✅ Updated!")
                                    st.rerun()
                        
                        with col3:
                            # Delete ingredient
                            if st.button("🗑️", key=f"del_{row['ingredient_id']}", type="secondary"):
                                delete_bom_item(selected_product, row['ingredient_id'], selected_branch_id)
                                st.success("✅ Removed ingredient!")
                                st.rerun()
                else:
                    st.info("No ingredients in this recipe")
        
        # Quick stats
        if not final_products.empty:
            st.markdown("---")
            st.subheader("📊 BOM Statistics")
            
            total_products = len(final_products)
            products_with_bom = 0
            
            for _, product in final_products.iterrows():
                bom_df = get_bom(product['id'], selected_branch_id)
                if not bom_df.empty:
                    products_with_bom += 1
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Final Products", total_products)
            
            with col2:
                st.metric("With BOM", products_with_bom)
            
            with col3:
                st.metric("Without BOM", total_products - products_with_bom)

def show_manager_items():
    """Manager: Item management with delete functionality"""
    st.header("⚙️ Item Management")
    
    tab1, tab2, tab3 = st.tabs(["➕ Add Item", "📋 View Items", "🗑️ Delete Items"])
    
    with tab1:
        branches_df = get_all_branches()
        
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
            
            if submitted and name and item_id and branch_id:
                try:
                    add_item(item_id, name, category, unit, current_stock, min_stock, branch_id, st.session_state.username)
                    st.success(f"✅ Added {name}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
    with tab2:
        # View items by branch
        branches_df = get_all_branches()
        branch_filter = st.selectbox(
            "🏪 Filter by Branch",
            options=["All"] + branches_df['branch_name'].tolist()
        )
        
        if branch_filter == "All":
            items_df = get_items_by_role("warehouse_manager")
        else:
            branch_id = branches_df[branches_df['branch_name'] == branch_filter]['id'].iloc[0]
            items_df = get_items_by_role("warehouse_manager", branch_id)
        
        if not items_df.empty:
            display_df = items_df[['branch_name', 'id', 'name', 'category', 'current_stock', 'min_stock', 'unit']]
            display_df.columns = ['Branch', 'ID', 'Name', 'Category', 'Stock', 'Min', 'Unit']
            
            st.dataframe(display_df, use_container_width=True, height=400)
    
    with tab3:
        st.subheader("🗑️ Delete Items")
        st.warning("⚠️ **DANGER ZONE** - Item deletion cannot be undone!")
        
        # Branch selection for deletion
        branches_df = get_all_branches()
        del_branch_filter = st.selectbox(
            "🏪 Select Branch",
            options=branches_df['branch_name'].tolist(),
            key="delete_branch_filter"
        )
        
        if del_branch_filter:
            branch_id = branches_df[branches_df['branch_name'] == del_branch_filter]['id'].iloc[0]
            items_df = get_items_by_role("warehouse_manager", branch_id)
            
            if not items_df.empty:
                col1, col2 = st.columns(2)
                
                with col1:
                    item_to_delete = st.selectbox(
                        "🗑️ Select Item to DELETE",
                        options=[""] + items_df['id'].tolist(),
                        format_func=lambda x: "SELECT ITEM TO DELETE" if x == "" else f"DELETE: {x} - {items_df[items_df['id']==x]['name'].iloc[0]}"
                    )
                    
                    if item_to_delete and item_to_delete != "":
                        item_info = items_df[items_df['id'] == item_to_delete].iloc[0]
                        
                        st.error(f"""
                        **⚠️ ITEM TO BE DELETED:**
                        - **ID:** {item_info['id']}
                        - **Name:** {item_info['name']}
                        - **Category:** {item_info['category']}
                        - **Stock:** {item_info['current_stock']} {item_info['unit']}
                        - **Branch:** {item_info['branch_name']}
                        """)
                
                with col2:
                    if item_to_delete and item_to_delete != "":
                        st.write("**Deletion Controls:**")
                        
                        if st.button("🗑️ DELETE THIS ITEM", type="secondary", use_container_width=True):
                            if st.session_state.get('confirm_delete_item') == item_to_delete:
                                # DELETE THE ITEM
                                try:
                                    conn = sqlite3.connect('inventory.db')
                                    c = conn.cursor()
                                    
                                    # Delete from all tables
                                    c.execute('DELETE FROM items WHERE id = ? AND branch_id = ?', (item_to_delete, branch_id))
                                    c.execute('DELETE FROM stock_movements WHERE item_id = ? AND branch_id = ?', (item_to_delete, branch_id))
                                    
                                    conn.commit()
                                    conn.close()
                                    
                                    st.success(f"🗑️ DELETED '{item_info['name']}' from {item_info['branch_name']}!")
                                    if 'confirm_delete_item' in st.session_state:
                                        del st.session_state['confirm_delete_item']
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error deleting item: {str(e)}")
                            else:
                                st.session_state['confirm_delete_item'] = item_to_delete
                                st.error("⚠️ CLICK DELETE AGAIN TO CONFIRM!")
                        
                        if st.button("❌ Cancel Deletion", use_container_width=True):
                            if 'confirm_delete_item' in st.session_state:
                                del st.session_state['confirm_delete_item']
                            st.rerun()
                        
                        # Clear stock option
                        if item_info['current_stock'] > 0:
                            if st.button(f"📉 Clear Stock ({item_info['current_stock']} {item_info['unit']})", use_container_width=True):
                                update_stock(item_to_delete, branch_id, item_info['current_stock'], 'OUT', 
                                           'Stock cleared for deletion', '', '', '', st.session_state.username)
                                st.success("Stock cleared to zero!")
                                st.rerun()
            else:
                st.info(f"No items found in {del_branch_filter}")
    
    # Quick stats
    items_df = get_items_by_role("warehouse_manager")
    if not items_df.empty:
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Items", len(items_df))
        
        with col2:
            active_items = len(items_df[items_df['current_stock'] > 0])
            st.metric("Active Items", active_items)
        
        with col3:
            low_stock_items = len(items_df[items_df['current_stock'] <= items_df['min_stock']])
            st.metric("Low Stock", low_stock_items)
        
        with col4:
            zero_stock_items = len(items_df[items_df['current_stock'] <= 0])
            st.metric("Zero Stock", zero_stock_items)

def show_manager_movements():
    """Manager: View all movements with enhanced filtering and cleanup"""
    st.header("📈 Movement History")
    
    # Cleanup option
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.subheader("📊 Stock Movement Records")
    
    with col2:
        if st.button("🧹 Clean Duplicates", type="secondary", help="Remove duplicate movement records"):
            deleted = clean_duplicate_movements()
            if deleted > 0:
                st.success(f"✅ Cleaned {deleted} duplicate records!")
                st.rerun()
            else:
                st.info("No duplicates found")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        branches_df = get_all_branches()
        branch_filter = st.selectbox(
            "🏪 Branch",
            options=["All"] + branches_df['branch_name'].tolist()
        )
    
    with col2:
        category_filter = st.selectbox(
            "📦 Category",
            options=["All", "Final Product", "Raw Material", "Pre-Final"]
        )
    
    with col3:
        user_filter = st.selectbox(
            "👤 User",
            options=["All", "My Actions", "Admin Actions"]
        )
    
    # Additional filters
    col4, col5 = st.columns(2)
    
    with col4:
        movement_filter = st.selectbox(
            "🔄 Type",
            options=["All", "Transfers", "Production", "Admin Updates", "Stock Updates"]
        )
    
    with col5:
        limit_records = st.selectbox(
            "📊 Records",
            options=[50, 100, 200],
            index=1
        )
    
    # Get movements with better deduplication
    conn = sqlite3.connect('inventory.db')
    
    query = '''
        SELECT DISTINCT sm.*, i.name as item_name, i.unit, i.category, b.branch_name
        FROM stock_movements sm
        JOIN items i ON sm.item_id = i.id 
        JOIN branches b ON sm.branch_id = b.id
        WHERE EXISTS (SELECT 1 FROM items i2 WHERE i2.id = sm.item_id AND i2.branch_id = sm.branch_id)
    '''
    
    params = []
    
    # Branch filtering
    if branch_filter != "All":
        branch_id = branches_df[branches_df['branch_name'] == branch_filter]['id'].iloc[0]
        query += " AND sm.branch_id = ?"
        params.append(branch_id)
    
    # Category filtering
    if category_filter != "All":
        query += " AND i.category = ?"
        params.append(category_filter)
    
    # User filtering - Manager sees their actions and admin actions
    if user_filter == "My Actions":
        query += " AND sm.user_id = ?"
        params.append(st.session_state.username)
    elif user_filter == "Admin Actions":
        query += " AND sm.user_id = 'admin'"
    
    # Movement type filtering
    if movement_filter == "Transfers":
        query += " AND sm.movement_type LIKE 'TRANSFER_%'"
    elif movement_filter == "Production":
        query += " AND sm.movement_type = 'PRODUCTION'"
    elif movement_filter == "Admin Updates":
        query += " AND sm.movement_type LIKE 'ADMIN_%'"
    elif movement_filter == "Stock Updates":
        query += " AND sm.movement_type IN ('IN', 'OUT')"
    
    query += f" ORDER BY sm.date_time DESC, sm.id DESC LIMIT {limit_records}"
    
    movements_df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if not movements_df.empty:
        st.info(f"📊 Found {len(movements_df)} movements")
        
        # Build tracking info and display
        def build_tracking(row):
            tracking = []
            if row.get('batch_nr'):
                tracking.append(f"Batch: {row['batch_nr']}")
            if row.get('invoice_nr'):
                tracking.append(f"Inv: {row['invoice_nr']}")
            return " | ".join(tracking) if tracking else "-"
        
        movements_df['Tracking'] = movements_df.apply(build_tracking, axis=1)
        
        # Format movement types for better readability
        def format_movement_type(movement_type):
            if movement_type == 'ADMIN_SET':
                return 'Admin: SET'
            elif movement_type == 'ADMIN_IN':
                return 'Admin: ADD'
            elif movement_type == 'ADMIN_OUT':
                return 'Admin: SUBTRACT'
            elif movement_type == 'TRANSFER_OUT':
                return 'Transfer: OUT'
            elif movement_type == 'TRANSFER_IN':
                return 'Transfer: IN'
            else:
                return movement_type
        
        movements_df['FormattedType'] = movements_df['movement_type'].apply(format_movement_type)
        
        display_df = movements_df[['date_time', 'branch_name', 'category', 'item_name', 'FormattedType', 'quantity', 'unit', 'Tracking', 'user_id']]
        display_df.columns = ['Date', 'Branch', 'Category', 'Item', 'Type', 'Qty', 'Unit', 'Tracking', 'User']
        display_df['Date'] = pd.to_datetime(display_df['Date']).dt.strftime('%m-%d %H:%M')
        
        st.dataframe(display_df, use_container_width=True, height=400)
        
        # Summary statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Movements", len(movements_df))
        
        with col2:
            my_actions = len(movements_df[movements_df['user_id'] == st.session_state.username])
            st.metric("My Actions", my_actions)
        
        with col3:
            admin_actions = len(movements_df[movements_df['user_id'] == 'admin'])
            st.metric("Admin Actions", admin_actions)
        
        with col4:
            transfers = len(movements_df[movements_df['movement_type'].str.contains('TRANSFER')])
            st.metric("Transfers", transfers)
    else:
        st.info("No movements found with selected filters")
        if branch_filter != "All":
            st.info(f"💡 Try selecting 'All' branches or check if there are items in {branch_filter}")

def show_manager_users():
    """Manager: User management with full CRUD operations"""
    st.header("👥 User Management")
    
    # Show current users
    conn = sqlite3.connect('inventory.db')
    users_df = pd.read_sql_query("SELECT username, role, full_name, last_login FROM users ORDER BY role", conn)
    conn.close()
    
    st.subheader("👤 Current Users")
    
    if not users_df.empty:
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
    
    # Tabs for user management
    tab1, tab2, tab3 = st.tabs(["➕ Add User", "✏️ Edit Users", "🔒 Reset Password"])
    
    with tab1:
        st.subheader("➕ Add New User")
        
        with st.form("add_user_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                new_username = st.text_input("Username")
                new_password = st.text_input("Password", type="password")
                new_full_name = st.text_input("Full Name")
            
            with col2:
                new_role = st.selectbox("Role", ["viewer", "admin", "boss", "warehouse_manager"])
                
                role_info = {
                    "viewer": "👁️ **Viewer**: Final products by branch only",
                    "admin": "🔧 **Admin**: Final products stock management",
                    "boss": "👔 **Boss**: View all, edit nothing",
                    "warehouse_manager": "👨‍💼 **Manager**: Full access"
                }
                
                st.info(role_info[new_role])
            
            submitted = st.form_submit_button("➕ Create User", type="primary")
            
            if submitted and new_username and new_password and new_full_name:
                if len(new_password) < 6:
                    st.error("❌ Password must be at least 6 characters")
                else:
                    try:
                        conn = sqlite3.connect('inventory.db')
                        c = conn.cursor()
                        
                        # Check if exists
                        existing = c.execute("SELECT username FROM users WHERE username = ?", (new_username,)).fetchone()
                        if existing:
                            st.error("❌ Username already exists")
                        else:
                            password_hash = hashlib.sha256(new_password.encode()).hexdigest()
                            c.execute("INSERT INTO users (username, password_hash, role, full_name, created_date) VALUES (?, ?, ?, ?, ?)",
                                     (new_username, password_hash, new_role, new_full_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                            
                            conn.commit()
                            st.success(f"✅ User '{new_username}' created!")
                            st.info(f"🔑 **Login:** `{new_username}` / `{new_password}`")
                            st.rerun()
                        
                        conn.close()
                        
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
    
    with tab2:
        st.subheader("✏️ Edit Users")
        
        if not users_df.empty:
            # Select user to edit (exclude current user)
            other_users = users_df[users_df['username'] != st.session_state.username]
            
            if not other_users.empty:
                selected_user = st.selectbox(
                    "Select User to Edit",
                    options=[""] + other_users['username'].tolist(),
                    format_func=lambda x: "Select a user..." if x == "" else f"{x} - {other_users[other_users['username']==x]['full_name'].iloc[0] if x else ''}"
                )
                
                if selected_user:
                    user_info = users_df[users_df['username'] == selected_user].iloc[0]
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Username:** {user_info['username']}")
                        st.write(f"**Name:** {user_info['full_name']}")
                        st.write(f"**Role:** {user_info['Role']}")
                        st.write(f"**Last Login:** {user_info['last_login'] or 'Never'}")
                    
                    with col2:
                        # Edit user details
                        with st.form("edit_user_form"):
                            new_full_name = st.text_input("Update Full Name", value=user_info['full_name'])
                            new_role = st.selectbox("Update Role", 
                                                   ["viewer", "admin", "boss", "warehouse_manager"],
                                                   index=["viewer", "admin", "boss", "warehouse_manager"].index(user_info['username'].split('_')[0] if '_' in user_info['username'] else user_info['Role'].split()[-1].lower()))
                            
                            col2a, col2b = st.columns(2)
                            
                            with col2a:
                                update_submitted = st.form_submit_button("💾 Update User", type="primary")
                            
                            with col2b:
                                st.write("")  # Spacing
                            
                            if update_submitted:
                                try:
                                    conn = sqlite3.connect('inventory.db')
                                    c = conn.cursor()
                                    c.execute("UPDATE users SET full_name = ?, role = ? WHERE username = ?",
                                             (new_full_name, new_role, selected_user))
                                    conn.commit()
                                    conn.close()
                                    
                                    st.success(f"✅ Updated user '{selected_user}'!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error updating user: {str(e)}")
                    
                    # Delete user section
                    st.markdown("---")
                    st.subheader("🗑️ Delete User")
                    st.warning(f"⚠️ **Delete user:** {selected_user}")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("🗑️ DELETE USER", type="secondary", use_container_width=True):
                            if st.session_state.get('confirm_delete_user') == selected_user:
                                try:
                                    conn = sqlite3.connect('inventory.db')
                                    c = conn.cursor()
                                    c.execute('DELETE FROM users WHERE username = ?', (selected_user,))
                                    conn.commit()
                                    conn.close()
                                    
                                    st.success(f"🗑️ User '{selected_user}' deleted successfully!")
                                    if 'confirm_delete_user' in st.session_state:
                                        del st.session_state['confirm_delete_user']
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error deleting user: {str(e)}")
                            else:
                                st.session_state['confirm_delete_user'] = selected_user
                                st.error("⚠️ Click DELETE USER again to confirm!")
                    
                    with col2:
                        if st.button("❌ Cancel", use_container_width=True):
                            if 'confirm_delete_user' in st.session_state:
                                del st.session_state['confirm_delete_user']
                            st.rerun()
            else:
                st.info("You are the only user in the system.")
        else:
            st.info("No users found.")
    
    with tab3:
        st.subheader("🔒 Reset Password")
        
        if not users_df.empty:
            # Select user for password reset (exclude current user)
            other_users = users_df[users_df['username'] != st.session_state.username]
            
            if not other_users.empty:
                user_to_reset = st.selectbox(
                    "Select User for Password Reset",
                    options=other_users['username'].tolist(),
                    format_func=lambda x: f"{x} - {other_users[other_users['username']==x]['full_name'].iloc[0]}"
                )
                
                if user_to_reset:
                    with st.form("reset_password_form"):
                        new_temp_password = st.text_input("New Password", type="password", placeholder="Enter new password")
                        confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm new password")
                        
                        reset_submitted = st.form_submit_button("🔒 Reset Password", type="primary")
                        
                        if reset_submitted:
                            if not new_temp_password:
                                st.error("❌ Please enter a new password")
                            elif len(new_temp_password) < 6:
                                st.error("❌ Password must be at least 6 characters!")
                            elif new_temp_password != confirm_password:
                                st.error("❌ Passwords do not match!")
                            else:
                                try:
                                    conn = sqlite3.connect('inventory.db')
                                    c = conn.cursor()
                                    
                                    password_hash = hashlib.sha256(new_temp_password.encode()).hexdigest()
                                    c.execute("UPDATE users SET password_hash = ? WHERE username = ?", 
                                             (password_hash, user_to_reset))
                                    conn.commit()
                                    conn.close()
                                    
                                    st.success(f"🔒 Password reset for '{user_to_reset}'!")
                                    st.info(f"**New login details:**\nUsername: `{user_to_reset}`\nPassword: `{new_temp_password}`")
                                except Exception as e:
                                    st.error(f"❌ Error resetting password: {str(e)}")
            else:
                st.info("No other users to reset passwords for.")
        else:
            st.info("No users found.")
    
    # Security tips
    with st.expander("🛡️ Security Tips"):
        st.markdown("""
        ### 🔐 User Management Best Practices:
        - ✅ **Use strong passwords** (at least 8 characters)
        - ✅ **Remove users** who no longer need access
        - ✅ **Review user roles** regularly
        - ✅ **Change default passwords** immediately after first login
        
        ### 👥 Role Guidelines:
        - **👁️ Viewer**: Sales staff, drivers, general employees
        - **🔧 Admin**: Stock controllers (final products only)
        - **👔 Boss**: Management, supervisors (view-only access)
        - **👨‍💼 Manager**: Warehouse staff, inventory controllers (full access)
        """)
    
    # User activity summary
    if not users_df.empty:
        st.subheader("📊 User Summary")
        
        role_counts = users_df['Role'].value_counts()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            manager_count = len(users_df[users_df['role'] == 'warehouse_manager'])
            st.metric("👨‍💼 Managers", manager_count)
        
        with col2:
            boss_count = len(users_df[users_df['role'] == 'boss'])
            st.metric("👔 Bosses", boss_count)
        
        with col3:
            admin_count = len(users_df[users_df['role'] == 'admin'])
            st.metric("🔧 Admins", admin_count)
        
        with col4:
            viewer_count = len(users_df[users_df['role'] == 'viewer'])
            st.metric("👁️ Viewers", viewer_count)

# ===============================
# MAIN APPLICATION
# ===============================

def main():
    st.set_page_config(
        page_title="🔥 FLAMEBLOCK INVENTORY",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Hide Streamlit elements
    st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {visibility: hidden;}
    .stDecoration {visibility: hidden;}
    .viewerBadge_container__1QSob {display: none;}
    
    .main .block-container {
        padding-top: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    .stDataFrame [data-testid="stElementToolbar"] {
        display: none;
    }
    
    @media (max-width: 768px) {
        .main .block-container {
            padding: 0.5rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize database
    init_database()
    
    # Check authentication
    if not st.session_state.get('authenticated', False):
        show_login()
        return
    
    # Load sample data if needed
    items_df = get_items_by_role("warehouse_manager")
    if items_df.empty:
        with st.spinner("Loading inventory data..."):
            load_sample_data()
            st.success("✅ Inventory data loaded!")
            st.rerun()
    
    # Header
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("""
        <div style="display: flex; align-items: center; margin-bottom: 1rem;">
            <div style="font-size: 2rem; margin-right: 0.5rem;">🔥</div>
            <div>
                <h1 style="margin: 0; color: #262730; font-size: 1.8rem;">FLAMEBLOCK INVENTORY</h1>
                <p style="margin: 0; color: #666; font-size: 0.8rem;">Multi-Branch Stock Control</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        role_display = {
            'warehouse_manager': '👨‍💼 Warehouse Manager',
            'boss': '👔 Boss/Owner', 
            'viewer': '👁️ Branch Viewer',
            'admin': '🔧 Stock Admin'
        }
        st.markdown(f"**{role_display.get(st.session_state.user_role)} - {st.session_state.full_name}**")
    
    with col2:
        if st.button("🚪 Logout", type="secondary", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    # Navigation and routing
    current_page = show_navigation(st.session_state.user_role)
    
    # Route to pages
    try:
        # Viewer pages
        if current_page == "viewer_branches":
            show_viewer_branches()
        elif current_page == "viewer_products":
            show_viewer_products()
        
        # Admin pages
        elif current_page == "admin_dashboard":
            show_admin_dashboard()
        elif current_page == "admin_update":
            show_admin_update()
        elif current_page == "admin_transfer":
            show_admin_transfer()
        elif current_page == "admin_movements":
            show_admin_movements()
        
        # Boss pages
        elif current_page == "boss_dashboard":
            show_boss_dashboard()
        elif current_page == "boss_branches":
            show_boss_branches()
        elif current_page == "boss_stock":
            show_boss_stock()
        elif current_page == "boss_movements":
            show_boss_movements()
        elif current_page == "boss_reports":
            show_boss_reports()
        
        # Manager pages
        elif current_page == "manager_dashboard":
            show_manager_dashboard()
        elif current_page == "manager_branches":
            show_manager_branches()
        elif current_page == "manager_stock":
            show_manager_stock()
        elif current_page == "manager_transfers":
            show_manager_transfers()
        elif current_page == "manager_production":
            show_manager_production()
        elif current_page == "manager_bom":
            show_manager_bom()
        elif current_page == "manager_items":
            show_manager_items()
        elif current_page == "manager_movements":
            show_manager_movements()
        elif current_page == "manager_users":
            show_manager_users()
        
        else:
            st.error("Page not found")
    
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.info("Please try refreshing the page or contact support.")

if __name__ == "__main__":
    main()
