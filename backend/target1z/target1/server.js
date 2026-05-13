const express = require('express');
const sqlite3 = require('sqlite3').verbose();

const app = express();
const port = 3002;

app.use(express.urlencoded({ extended: false }));
app.use(express.json());

// Set up In-Memory Database for Target 1
const db = new sqlite3.Database(':memory:', (err) => {
    if (err) {
        console.error('Database connection error:', err.message);
    } else {
        console.log('Connected to the SQLite database (in-memory).');
        db.serialize(() => {
            // Setup User Table
            db.run("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password TEXT)");
            db.run("INSERT INTO users (username, password) VALUES ('admin', 'super_secret_admin_pass_1234')");
            db.run("INSERT INTO users (username, password) VALUES ('jsmith', 'password123')");
            
            // Setup Product Table
            db.run("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, description TEXT)");
            db.run("INSERT INTO products (name, description) VALUES ('Basic Widget', 'A basic widget')");
            db.run("INSERT INTO products (name, description) VALUES ('Advanced Widget', 'An advanced widget')");
            db.run("INSERT INTO products (name, description) VALUES ('Secret Prototype', 'Confidential prototype specs')");

            // Setup Telemetry/Logs Table
            db.run("CREATE TABLE tracking_logs (id INTEGER PRIMARY KEY, user_agent TEXT, ip TEXT)");
        });
    }
});

// Middleware: 3. HTTP Header SQL Injection
// This runs on every request. It takes User-Agent and logs it unparameterized.
app.use((req, res, next) => {
    const userAgent = req.headers['user-agent'] || 'Unknown';
    const ip = req.headers['x-forwarded-for'] || req.socket.remoteAddress || 'Unknown';
    
    // INTENTIONAL SQLI: Logging HTTP headers directly without escaping
    const query = `INSERT INTO tracking_logs (user_agent, ip) VALUES ('${userAgent}', '${ip}')`;
    
    // We run it async so it doesn't block standard requests, but it will execute the injection
    db.run(query, (err) => {
        if (err) {
            console.error("Telemetry Logging Error:", err.message); // Could be used for error-based SQLi blindly
        }
    });
    next();
});

// Helper for UI
const renderPage = (title, content) => `
<html>
<head><title>${title}</title><style>body{font-family:sans-serif; margin:40px;} input{margin: 5px 0; padding:5px; width: 300px} button{padding: 5px 15px;} pre{background:#eee; padding:10px;}</style></head>
<body><h2>${title}</h2>${content}</body>
</html>
`;


// HOME ROUTE
app.get('/', (req, res) => {
    res.send(renderPage('Target 1: Master of SQLi', `
        <ul>
            <li><a href="/products?id=1">URL Query Test (GET)</a></li>
            <li><a href="/login">Form Input Test (POST)</a></li>
            <li><a href="/api/user/profile/jsmith">REST API Path Test (JSON)</a></li>
        </ul>
        <p><i>Note: The header injection is active in the background middleware for all routes! Try changing your User-Agent!</i></p>
    `));
});

// 1. URL Query Parameters (GET)
// Goal logic to teach: Union-Based or Boolean-Based
app.get('/products', (req, res) => {
    const id = req.query.id;
    if (!id) return res.send(renderPage('Products', '<p>Please provide an id, e.g., ?id=1</p>'));

    // INTENTIONAL SQLI: String concatenation for query parameter
    const query = `SELECT * FROM products WHERE id=${id}`;
    
    db.all(query, (err, rows) => {
        if (err) {
            // Echoing error creates Error-based SQLI potential
            return res.send(renderPage('Database Error', `<pre>${err.message}</pre>`));
        }
        
        let output = rows.map(r => `<div><strong>${r.name}:</strong> ${r.description}</div>`).join('<hr>');
        res.send(renderPage('Product Details', output || '<p>No product found.</p>'));
    });
});


// 2. Form Inputs (POST Requests)
// Goal logic to teach: Authentication Bypass / Error-Based
app.get('/login', (req, res) => {
    res.send(renderPage('Login Forms', `
        <form method="POST" action="/login">
            <label>Username:</label><br>
            <input type="text" name="username"><br>
            <label>Password:</label><br>
            <input type="password" name="password"><br>
            <button type="submit">Login</button>
        </form>
    `));
});

app.post('/login', (req, res) => {
    const { username, password } = req.body;
    
    // INTENTIONAL SQLI: Form fields concatenated directly
    const query = `SELECT * FROM users WHERE username='${username}' AND password='${password}'`;
    
    db.get(query, (err, row) => {
         if (err) {
            return res.send(renderPage('Database Error', `<pre>${err.message}</pre><p>Executing: ${query}</p>`));
        }
        if (row) {
            res.send(renderPage('Login Success', `<h3 style="color:green">Welcome, ${row.username}</h3><p>Your hash: ${row.password}</p>`));
        } else {
            res.send(renderPage('Login Failed', `<p style="color:red">Invalid credentials.</p>`));
        }
    });
});

// 4. REST API Endpoints
// Goal logic to teach: Injecting via path parameters
app.get('/api/user/profile/:username', (req, res) => {
    const username = req.params.username;
    
    // INTENTIONAL SQLI: REST parameter straight into query 
    const query = `SELECT username FROM users WHERE username='${username}'`;
    
    db.all(query, (err, rows) => {
        if (err) {
            return res.status(500).json({ status: "error", message: err.message, queryTraced: query });
        }
        if (rows.length > 0) {
            res.json({ status: "success", data: rows });
        } else {
            res.status(404).json({ status: "error", message: "User not found" });
        }
    });
});

app.listen(port, () => {
    console.log(`Target 1 Server running on http://localhost:${port}`);
});
