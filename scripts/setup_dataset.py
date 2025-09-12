#!/usr/bin/env python3
"""
CogniQuery Dataset Setup Script
Helps users easily set up the sample e-commerce dataset for demo purposes.
"""

import os
import psycopg2
from dotenv import load_dotenv

def setup_sample_data():
    """Set up the sample dataset in the configured database."""
    print("🤖 CogniQuery Dataset Setup")
    print("=" * 40)
    
    # Load environment variables
    load_dotenv()
    
    # Get database connection string
    db_conn_str = os.getenv("NEONDB_CONN_STR")
    
    if not db_conn_str:
        print("❌ Error: NEONDB_CONN_STR not found in environment variables.")
        print("Please set up your .env file with your database connection string.")
        return False
    
    # Read the SQL script
    script_path = os.path.join(os.path.dirname(__file__), "dataset.sql")
    
    if not os.path.exists(script_path):
        print(f"❌ Error: SQL script not found at {script_path}")
        return False
    
    try:
        with open(script_path, 'r') as f:
            sql_script = f.read()
        
        print(f"📖 Found SQL script: {script_path}")
        print(f"📊 Script size: {len(sql_script)} characters")
        
        # Connect to database
        print("🔗 Connecting to database...")
        conn = psycopg2.connect(db_conn_str)
        cursor = conn.cursor()
        
        # Execute the SQL script
        print("🚀 Executing SQL script...")
        cursor.execute(sql_script)
        conn.commit()
        
        # Verify the data was loaded
        print("✅ Verifying data setup...")
        cursor.execute("SELECT COUNT(*) FROM orders")
        order_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM products")
        product_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM customers")
        customer_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM regions")
        region_count = cursor.fetchone()[0]
        
        print(f"📊 Data loaded successfully!")
        print(f"   - {order_count} orders")
        print(f"   - {product_count} products")
        print(f"   - {customer_count} customers")
        print(f"   - {region_count} regions")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 Sample dataset setup complete!")
        print("\n💡 Try these sample queries in CogniQuery:")
        print("   • 'Our profit in Southeast Asia is a disaster. Find the top 3 sub-categories that are losing the most money in that region.'")
        print("   • 'Show me the relationship between discount levels and profitability.'")
        print("   • 'Which customer segment is most profitable and why?'")
        
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = setup_sample_data()
    if not success:
        print("\n❌ Setup failed. Please check your database connection and try again.")
        exit(1)
    else:
        print("\n✅ You're ready to use CogniQuery! Run 'streamlit run app.py' to get started.")
