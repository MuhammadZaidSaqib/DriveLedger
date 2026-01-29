PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS expenses;
DROP TABLE IF EXISTS vehicles;

CREATE TABLE vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand TEXT NOT NULL,
    model TEXT NOT NULL,
    year INTEGER NOT NULL,
    purchase_price REAL NOT NULL,
    expected_sell_price REAL NOT NULL,
    date_added TEXT NOT NULL
);

CREATE TABLE sales (
    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_id INTEGER NOT NULL,
    customer_name TEXT NOT NULL,
    sale_price REAL NOT NULL,
    date TEXT NOT NULL,
    FOREIGN KEY(vehicle_id) REFERENCES vehicles(id)
);

CREATE TABLE expenses (
    expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    date TEXT NOT NULL
);

-- Sample Data (2023–2025)
INSERT INTO vehicles (brand, model, year, purchase_price, expected_sell_price, date_added) VALUES
('Toyota','Corolla',2023,18000,22000,'2023-02-15'),
('Honda','Civic',2023,17500,21500,'2023-06-10'),
('Suzuki','Swift',2024,14000,18000,'2024-01-20'),
('Hyundai','Elantra',2024,19000,23500,'2024-07-05'),
('Kia','Sportage',2025,26000,31000,'2025-03-18');

INSERT INTO expenses (description, amount, date) VALUES
('Showroom Rent',1200,'2023-01-05'),
('Marketing',850,'2023-05-18'),
('Maintenance',600,'2024-03-10'),
('Insurance',900,'2024-12-01'),
('Taxes',2000,'2025-12-20');
