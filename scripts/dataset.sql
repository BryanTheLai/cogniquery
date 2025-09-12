-- Sample E-commerce Dataset for CogniQuery Demo
-- This dataset contains a hidden business problem: unprofitable sales in Southeast Asia due to excessive discounts

-- Drop tables if they exist to start fresh
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS regions CASCADE;

-- Create the Regions Table
CREATE TABLE regions (
    region_id SERIAL PRIMARY KEY,
    region_name VARCHAR(255) NOT NULL,
    country VARCHAR(255) NOT NULL
);

-- Create the Customers Table
CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    customer_name VARCHAR(255) NOT NULL,
    segment VARCHAR(50) NOT NULL
);

-- Create the Products Table
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    sub_category VARCHAR(100) NOT NULL
);

-- Create the main Orders Table
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    order_date DATE NOT NULL,
    customer_id INT REFERENCES customers(customer_id),
    product_id INT REFERENCES products(product_id),
    region_id INT REFERENCES regions(region_id),
    sales DECIMAL(10, 2) NOT NULL,
    quantity INT NOT NULL,
    discount DECIMAL(3, 2) NOT NULL,
    profit DECIMAL(10, 2) NOT NULL
);

-- Insert Data into Regions
INSERT INTO regions (region_id, region_name, country) VALUES
(1, 'Southeast Asia', 'Malaysia'),
(2, 'Southeast Asia', 'Singapore'),
(3, 'North America', 'United States'),
(4, 'Europe', 'Germany');

-- Insert Data into Customers
INSERT INTO customers (customer_id, customer_name, segment) VALUES
(1, 'Bryan Lee', 'Consumer'),
(2, 'Venture Corp', 'Corporate'),
(3, 'Anna Smith', 'Home Office'),
(4, 'Global Tech Inc', 'Corporate');

-- Insert Data into Products
INSERT INTO products (product_id, product_name, category, sub_category) VALUES
(1, 'Executive Leather Chair', 'Furniture', 'Chairs'),
(2, 'Conference Table', 'Furniture', 'Tables'),
(3, 'Pine Bookcase', 'Furniture', 'Bookcases'),
(4, 'Galaxy S25', 'Technology', 'Phones'),
(5, 'QuantumBook Pro', 'Technology', 'Laptops'),
(6, 'Smart Toaster Oven', 'Appliances', 'Kitchen'),
(7, 'Eco-Friendly Binders', 'Office Supplies', 'Binders');

-- Insert Order Data (Engineered for the Demo Story)
-- NOTE: The story is hidden in here. Tables in SEA have high sales but NEGATIVE profit due to high discounts.
INSERT INTO orders (order_date, customer_id, product_id, region_id, sales, quantity, discount, profit) VALUES
-- Profitable Sales (The Control Group)
('2024-10-05', 1, 4, 3, 1200.00, 2, 0.00, 480.00),  -- Phones in North America, no discount, high profit
('2024-11-12', 2, 5, 4, 3000.00, 2, 0.10, 900.00),  -- Laptops in Europe, small discount, good profit
('2024-11-20', 1, 1, 1, 600.00, 2, 0.10, 150.00),   -- Chairs in SEA, profitable

-- *** THE HIDDEN PROBLEM: UNPROFITABLE BEST-SELLERS IN SOUTHEAST ASIA ***
('2024-09-15', 2, 2, 1, 1800.00, 3, 0.50, -550.00), -- Tables in Malaysia, high sales, HUGE discount, BIG loss
('2024-10-22', 4, 2, 2, 1200.00, 2, 0.50, -380.00), -- Tables in Singapore, high sales, HUGE discount, BIG loss
('2024-08-01', 3, 3, 1, 800.00, 4, 0.60, -210.00),   -- Bookcases in Malaysia, high sales, HUGE discount, loss
('2024-11-30', 4, 6, 2, 450.00, 3, 0.40, -80.00),    -- Appliances in Singapore, decent sales, high discount, loss

-- More filler data to make it look real
('2025-01-20', 3, 7, 3, 50.00, 10, 0.00, 20.00),   -- Office Supplies in NA, profitable
('2025-02-10', 2, 1, 4, 900.00, 3, 0.10, 220.00),   -- Chairs in Europe, profitable
('2025-03-14', 1, 5, 1, 1500.00, 1, 0.15, 350.00),  -- Laptop in SEA, profitable
('2025-04-01', 4, 4, 2, 650.00, 1, 0.00, 250.00);    -- Phone in Singapore, profitable

-- Verify the data
SELECT 'Data loaded successfully!' as status;
SELECT COUNT(*) as total_orders FROM orders;
SELECT COUNT(*) as total_products FROM products;
SELECT COUNT(*) as total_customers FROM customers;
SELECT COUNT(*) as total_regions FROM regions;
