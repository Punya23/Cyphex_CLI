/**
 * CYPHEX VulnCorp — Intentionally Vulnerable Express.js Application
 * 
 * THIS APP IS DELIBERATELY INSECURE. It contains 14+ real vulnerabilities
 * for testing the CYPHEX exploitation pipeline.
 * 
 * DO NOT deploy this in production. Run only inside Docker sandbox.
 * 
 * Vulnerabilities:
 *  1.  SQL Injection on /api/login (username param)
 *  2.  SQL Injection on /api/search (q param)
 *  3.  Reflected XSS on /search (q param)
 *  4.  Stored XSS on /api/comments (comment field)
 *  5.  IDOR on /api/user/:id (no auth check)
 *  6.  Broken auth — JWT with weak secret "secret123"
 *  7.  Exposed .env with DB_PASS, AWS_KEY, JWT_SECRET
 *  8.  No CSRF tokens on any forms
 *  9.  Directory traversal on /api/file?path=
 *  10. Command injection on /api/ping?host=
 *  11. Hardcoded credentials: admin/admin123
 *  12. Mass assignment on /api/user/update
 *  13. Open redirect on /redirect?url=
 *  14. Missing all security headers
 */

const express = require('express');
const mysql = require('mysql2/promise');
const jwt = require('jsonwebtoken');
const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// ════════════════════════════════════════
// VULN #14: No security headers at all
// VULN #7: Server info disclosure
// ════════════════════════════════════════
app.use((req, res, next) => {
    res.setHeader('X-Powered-By', 'Express/4.18.2');
    res.setHeader('Server', 'Apache/2.4.41 (Ubuntu)');
    // Intentionally missing:
    // - Content-Security-Policy
    // - X-Frame-Options
    // - X-Content-Type-Options
    // - Strict-Transport-Security
    // - Referrer-Policy
    // - Permissions-Policy
    next();
});

// ════════════════════════════════════════
// Database setup (MySQL)
// ════════════════════════════════════════
let db;

async function initDB() {
    // Wait for MySQL to be ready
    for (let i = 0; i < 30; i++) {
        try {
            db = await mysql.createConnection({
                host: process.env.DB_HOST || 'db',
                user: process.env.DB_USER || 'root',
                password: process.env.DB_PASS || 'vulncorp_pass',
                database: process.env.DB_NAME || 'vulncorp',
                multipleStatements: true,  // VULN: allows stacked queries
            });
            console.log('Database connected');
            await seedDB();
            return;
        } catch (e) {
            console.log(`Waiting for DB... (${i + 1}/30)`);
            await new Promise(r => setTimeout(r, 2000));
        }
    }
    console.error('Failed to connect to database');
}

async function seedDB() {
    await db.query(`
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100),
            password VARCHAR(255),
            password_hash VARCHAR(255),
            email VARCHAR(200),
            role VARCHAR(50) DEFAULT 'user',
            ssn VARCHAR(20),
            phone VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(200),
            description TEXT,
            price DECIMAL(10,2),
            category VARCHAR(100)
        );

        CREATE TABLE IF NOT EXISTS comments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100),
            comment TEXT,
            page VARCHAR(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            product_id INT,
            credit_card VARCHAR(20),
            amount DECIMAL(10,2),
            status VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    `);

    // Seed data
    const [existing] = await db.query('SELECT COUNT(*) as count FROM users');
    if (existing[0].count === 0) {
        // VULN #11: Hardcoded credentials
        await db.query(`
            INSERT INTO users (username, password, password_hash, email, role, ssn, phone) VALUES
            ('admin', 'admin123', '0192023a7bbd73250516f069df18b500', 'admin@vulncorp.com', 'superadmin', '123-45-6789', '555-0100'),
            ('john', 'password123', '482c811da5d5b4bc6d497ffa98491e38', 'john@vulncorp.com', 'user', '234-56-7890', '555-0101'),
            ('jane', 'letmein', '0d107d09f5bbe40cade3de5c71e9e9b7', 'jane@vulncorp.com', 'editor', '345-67-8901', '555-0102'),
            ('bob', 'qwerty', 'd8578edf8458ce06fbc5bb76a58c5ca4', 'bob@vulncorp.com', 'user', '456-78-9012', '555-0103'),
            ('testuser', 'test', '098f6bcd4621d373cade4e832627b4f6', 'test@vulncorp.com', 'user', '567-89-0123', '555-0104');

            INSERT INTO products (name, description, price, category) VALUES
            ('Enterprise License', 'Full enterprise software license', 9999.99, 'software'),
            ('Security Audit', 'Professional security audit package', 4999.99, 'services'),
            ('Cloud Hosting', 'Annual cloud hosting plan', 2999.99, 'cloud'),
            ('Training Course', 'Cybersecurity training course', 1499.99, 'education'),
            ('Consulting', 'Security consulting hourly', 299.99, 'services');

            INSERT INTO comments (username, comment, page) VALUES
            ('john', 'Great product!', '/products'),
            ('jane', 'Need more documentation', '/products'),
            ('admin', 'Updated the FAQ section', '/about');

            INSERT INTO orders (user_id, product_id, credit_card, amount, status) VALUES
            (1, 1, '4111-1111-1111-1111', 9999.99, 'completed'),
            (2, 2, '4222-2222-2222-2222', 4999.99, 'completed'),
            (3, 3, '4333-3333-3333-3333', 2999.99, 'pending'),
            (2, 4, '4222-2222-2222-2222', 1499.99, 'completed');
        `);
        console.log('Database seeded with test data');
    }
}

// ════════════════════════════════════════
// JWT Secret — VULN #6: Weak secret
// ════════════════════════════════════════
const JWT_SECRET = 'secret123';

// ════════════════════════════════════════
// ROUTES
// ════════════════════════════════════════

// Homepage
app.get('/', (req, res) => {
    res.send(`<!DOCTYPE html>
<html>
<head><title>VulnCorp — Enterprise Portal</title></head>
<body>
<h1>VulnCorp Enterprise Portal</h1>
<p>Welcome to our enterprise portal.</p>
<nav>
    <a href="/login">Login</a> | 
    <a href="/search">Search</a> | 
    <a href="/admin">Admin</a> | 
    <a href="/api/users">API</a> |
    <a href="/comments">Comments</a>
</nav>
<form action="/contact" method="POST">
    <input name="name" placeholder="Your name">
    <input name="email" placeholder="Email">
    <textarea name="message"></textarea>
    <button>Send</button>
</form>
<!-- TODO: remove debug mode before production -->
<script>var debug = true; console.log("Debug mode ON");</script>
</body>
</html>`);
});

// Login page
app.get('/login', (req, res) => {
    res.send(`<!DOCTYPE html>
<html>
<head><title>Login — VulnCorp</title></head>
<body>
<h2>Login</h2>
<form action="/api/login" method="POST">
    <input name="username" placeholder="Username"><br>
    <input name="password" type="password" placeholder="Password"><br>
    <button type="submit">Login</button>
</form>
<p>Forgot password? <a href="/reset">Reset</a></p>
<!-- TODO: remove test credentials admin/admin123 -->
</body>
</html>`);
});

// ════════════════════════════════════════
// VULN #1: SQL Injection on login
// ════════════════════════════════════════
app.post('/api/login', async (req, res) => {
    const { username, password } = req.body;
    try {
        // VULNERABLE: Direct string interpolation
        const query = `SELECT * FROM users WHERE username='${username}' AND password='${password}'`;
        const [rows] = await db.query(query);
        
        if (rows.length > 0) {
            const user = rows[0];
            const token = jwt.sign(
                { id: user.id, username: user.username, role: user.role },
                JWT_SECRET
            );
            res.json({
                success: true,
                user: user.username,
                role: user.role,
                token: token,
                sql_debug: query  // VULN: SQL query leaked in response
            });
        } else {
            res.status(401).json({
                success: false,
                error: 'Invalid credentials',
                sql_debug: query  // VULN: SQL query leaked
            });
        }
    } catch (err) {
        res.status(500).json({
            error: err.message,
            sql_debug: `SELECT * FROM users WHERE username='${username}'`
        });
    }
});

// ════════════════════════════════════════
// VULN #3: Reflected XSS on search
// ════════════════════════════════════════
app.get('/search', (req, res) => {
    const q = req.query.q || '';
    // VULNERABLE: User input reflected without sanitization
    res.send(`<!DOCTYPE html>
<html>
<head><title>Search — VulnCorp</title></head>
<body>
<h2>Search Products</h2>
<form action="/search" method="GET">
    <input name="q" placeholder="Search..." value="${q}">
    <button>Go</button>
</form>
<div id="results">Results for: ${q}</div>
<script>
var q = new URLSearchParams(location.search).get("q");
if (q) document.getElementById("results").innerHTML = "Results for: " + q;
</script>
</body>
</html>`);
});

// ════════════════════════════════════════
// VULN #2: SQL Injection on search API  
// ════════════════════════════════════════
app.get('/api/search', async (req, res) => {
    const q = req.query.q || '';
    try {
        // VULNERABLE: Direct interpolation
        const query = `SELECT * FROM products WHERE name LIKE '%${q}%' OR description LIKE '%${q}%'`;
        const [rows] = await db.query(query);
        res.json({ results: rows, query: query });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// ════════════════════════════════════════
// VULN #5: IDOR on user endpoint
// ════════════════════════════════════════
app.get('/api/user/:id', async (req, res) => {
    try {
        // VULNERABLE: No authorization check
        const [rows] = await db.query(
            `SELECT id, username, email, role, ssn, phone FROM users WHERE id=${req.params.id}`
        );
        if (rows.length > 0) {
            res.json(rows[0]);
        } else {
            res.status(404).json({ error: 'User not found' });
        }
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// VULN: List all users with sensitive data
app.get('/api/users', async (req, res) => {
    try {
        const [rows] = await db.query(
            'SELECT id, username, email, role, password_hash FROM users'
        );
        res.json(rows);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// ════════════════════════════════════════
// VULN #4: Stored XSS on comments
// ════════════════════════════════════════
app.get('/comments', async (req, res) => {
    try {
        const [rows] = await db.query('SELECT * FROM comments ORDER BY created_at DESC');
        let commentsHtml = rows.map(c => 
            // VULNERABLE: Stored comment rendered without escaping
            `<div class="comment"><b>${c.username}</b>: ${c.comment}</div>`
        ).join('');
        
        res.send(`<!DOCTYPE html>
<html>
<head><title>Comments — VulnCorp</title></head>
<body>
<h2>Comments</h2>
${commentsHtml}
<h3>Add Comment</h3>
<form action="/api/comments" method="POST">
    <input name="username" placeholder="Your name"><br>
    <textarea name="comment" placeholder="Your comment"></textarea><br>
    <button>Submit</button>
</form>
</body>
</html>`);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.post('/api/comments', async (req, res) => {
    const { username, comment } = req.body;
    try {
        // VULNERABLE: Stores raw user input (XSS)
        await db.query(
            'INSERT INTO comments (username, comment, page) VALUES (?, ?, ?)',
            [username, comment, '/comments']
        );
        res.json({ success: true, message: `Thank you ${username}! Your comment: ${comment}` });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// ════════════════════════════════════════
// VULN #10: Command Injection on ping
// ════════════════════════════════════════
app.get('/api/ping', (req, res) => {
    const host = req.query.host || '127.0.0.1';
    // VULNERABLE: Direct shell command execution with user input
    exec(`ping -c 1 ${host}`, { timeout: 10000 }, (err, stdout, stderr) => {
        res.json({
            host: host,
            output: stdout || stderr || (err ? err.message : 'No output'),
            command: `ping -c 1 ${host}`  // VULN: Leaking executed command
        });
    });
});

// ════════════════════════════════════════
// VULN #9: Directory Traversal
// ════════════════════════════════════════
app.get('/api/file', (req, res) => {
    const filePath = req.query.path || 'readme.txt';
    // VULNERABLE: No path sanitization
    const fullPath = `/var/www/${filePath}`;
    try {
        const content = fs.readFileSync(fullPath, 'utf-8');
        res.send(content);
    } catch (err) {
        res.status(404).json({ error: `File not found: ${fullPath}` });
    }
});

// ════════════════════════════════════════
// VULN #12: Mass Assignment
// ════════════════════════════════════════
app.post('/api/user/update', async (req, res) => {
    // VULNERABLE: Accepts any field including 'role'
    const data = req.body;
    if (data.username) {
        try {
            const fields = Object.entries(data)
                .filter(([k]) => k !== 'id')
                .map(([k, v]) => `${k}='${v}'`)
                .join(', ');
            await db.query(`UPDATE users SET ${fields} WHERE username='${data.username}'`);
            res.json({ success: true, updated: data });
        } catch (err) {
            res.status(500).json({ error: err.message });
        }
    } else {
        res.status(400).json({ error: 'username required' });
    }
});

// ════════════════════════════════════════
// VULN #13: Open Redirect
// ════════════════════════════════════════
app.get('/redirect', (req, res) => {
    const url = req.query.url || '/';
    // VULNERABLE: Redirects to arbitrary URLs
    res.redirect(url);
});

// ════════════════════════════════════════
// VULN #7: Exposed sensitive files
// ════════════════════════════════════════
app.get('/.env', (req, res) => {
    res.type('text/plain').send(
`DB_HOST=mysql.vulncorp.internal
DB_USER=root
DB_PASS=vulncorp_super_secret_2024
AWS_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
STRIPE_SK=sk_live_51J3XfKLkjeYRE8W3x7QmPk
JWT_SECRET=secret123
REDIS_URL=redis://internal-redis:6379
MONGO_URI=mongodb://admin:secret@internal-mongo:27017
API_KEY=cyph3x_internal_api_key_do_not_share`
    );
});

app.get('/.git/HEAD', (req, res) => {
    res.type('text/plain').send('ref: refs/heads/main');
});

// Admin page with exposed info
app.get('/admin', (req, res) => {
    res.send(`<!DOCTYPE html>
<html>
<head><title>Admin — VulnCorp</title></head>
<body>
<h2>Admin Dashboard</h2>
<p>Server: Apache/2.4.41 (Ubuntu)</p>
<p>PHP Version: 7.2.10</p>
<p>Node: ${process.version}</p>
<a href="/admin/phpinfo">PHP Info</a> | <a href="/admin/logs">Logs</a>
<!-- DB_HOST=mysql.internal DB_PASS=vulncorp_super_secret_2024 AWS_KEY=AKIAIOSFODNN7EXAMPLE -->
<div style="display:none">Internal API: http://10.0.0.5:8080/internal</div>
</body>
</html>`);
});

// Robots.txt with sensitive paths
app.get('/robots.txt', (req, res) => {
    res.type('text/plain').send(
`User-agent: *
Disallow: /admin/
Disallow: /api/debug/
Disallow: /backup/
Disallow: /.env
Disallow: /.git/`
    );
});

// Contact form (reflected XSS)
app.post('/contact', (req, res) => {
    const { name, message } = req.body;
    // VULNERABLE: Reflects user input
    res.send(`<p>Thank you ${name}! Your message: ${message}</p>`);
});

// Orders with credit cards (IDOR)
app.get('/api/orders/:id', async (req, res) => {
    try {
        const [rows] = await db.query(
            `SELECT * FROM orders WHERE id=${req.params.id}`
        );
        res.json(rows[0] || { error: 'Not found' });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// ════════════════════════════════════════
// Static error for additional info leak
// ════════════════════════════════════════
app.use((err, req, res, next) => {
    // VULNERABLE: Stack trace exposed
    res.status(500).json({
        error: err.message,
        stack: err.stack,
        path: req.path,
    });
});

// ════════════════════════════════════════
// Start
// ════════════════════════════════════════
const PORT = process.env.PORT || 3000;

initDB().then(() => {
    app.listen(PORT, '0.0.0.0', () => {
        console.log(`VulnCorp running on port ${PORT}`);
        console.log('WARNING: This app is intentionally vulnerable!');
    });
});
