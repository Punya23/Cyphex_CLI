/**
 * CYPHEX VulnCorp — STANDALONE version (no Docker needed)
 * Uses sql.js (pure JS SQLite) — runs on Windows without native deps.
 * 
 * Run: node app_standalone.js
 * Then: python backend/main.py --target http://localhost:3000
 */

const express = require('express');
const jwt = require('jsonwebtoken');
const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');
const initSqlJs = require('sql.js');

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

let db;

// ═══ VULN #14: No security headers + Server info disclosure ═══
app.use((req, res, next) => {
    res.setHeader('X-Powered-By', 'Express/4.18.2');
    res.setHeader('Server', 'Apache/2.4.41 (Ubuntu)');
    next();
});

// ═══ JWT Secret — VULN #6: Weak secret ═══
const JWT_SECRET = 'secret123';

// Helper: run SQL query (returns array of objects)
function query(sql) {
    try {
        const stmt = db.prepare(sql);
        const rows = [];
        while (stmt.step()) {
            rows.push(stmt.getAsObject());
        }
        stmt.free();
        return rows;
    } catch (err) {
        throw err;
    }
}

function queryOne(sql) {
    const rows = query(sql);
    return rows.length > 0 ? rows[0] : null;
}

function runSql(sql) {
    db.run(sql);
}

// ═══ ROUTES ═══

// Homepage
app.get('/', (req, res) => {
    res.send(`<!DOCTYPE html>
<html><head><title>VulnCorp - Enterprise Portal</title></head>
<body>
<h1>VulnCorp Enterprise Portal</h1>
<p>Welcome to our enterprise portal.</p>
<nav>
    <a href="/login">Login</a> | <a href="/search">Search</a> | 
    <a href="/admin">Admin</a> | <a href="/api/users">API</a> |
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
</body></html>`);
});

// Login page
app.get('/login', (req, res) => {
    res.send(`<!DOCTYPE html>
<html><head><title>Login - VulnCorp</title></head>
<body>
<h2>Login</h2>
<form action="/api/login" method="POST">
    <input name="username" placeholder="Username"><br>
    <input name="password" type="password" placeholder="Password"><br>
    <button type="submit">Login</button>
</form>
<p>Forgot password? <a href="/reset">Reset</a></p>
<!-- TODO: remove test credentials admin/admin123 -->
</body></html>`);
});

// ═══ VULN #1: SQL Injection on login ═══
app.post('/api/login', (req, res) => {
    const { username, password } = req.body;
    try {
        // VULNERABLE: Direct string interpolation in SQL
        const sql = `SELECT * FROM users WHERE username='${username}' AND password='${password}'`;
        const rows = query(sql);
        
        if (rows.length > 0) {
            const user = rows[0];
            const token = jwt.sign(
                { id: user.id, username: user.username, role: user.role },
                JWT_SECRET
            );
            res.json({
                success: true, user: user.username, role: user.role,
                token: token,
                sql_debug: sql
            });
        } else {
            res.status(401).json({
                success: false, error: 'Invalid credentials',
                sql_debug: sql
            });
        }
    } catch (err) {
        res.status(500).json({
            error: err.message,
            sql_debug: `SELECT * FROM users WHERE username='${username}'`
        });
    }
});

// ═══ VULN #3: Reflected XSS on search ═══
app.get('/search', (req, res) => {
    const q = req.query.q || '';
    res.send(`<!DOCTYPE html>
<html><head><title>Search - VulnCorp</title></head>
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
</body></html>`);
});

// ═══ VULN #2: SQL Injection on search API ═══
app.get('/api/search', (req, res) => {
    const q = req.query.q || '';
    try {
        const sql = `SELECT * FROM products WHERE name LIKE '%${q}%' OR description LIKE '%${q}%'`;
        const rows = query(sql);
        res.json({ results: rows, query: sql });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// ═══ VULN #5: IDOR on user endpoint ═══
app.get('/api/user/:id', (req, res) => {
    try {
        const row = queryOne(
            `SELECT id, username, email, role, ssn, phone FROM users WHERE id=${req.params.id}`
        );
        if (row) res.json(row);
        else res.status(404).json({ error: 'User not found' });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.get('/api/users', (req, res) => {
    try {
        const rows = query(
            'SELECT id, username, email, role, password_hash FROM users'
        );
        res.json(rows);
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// ═══ VULN #4: Stored XSS on comments ═══
app.get('/comments', (req, res) => {
    const rows = query('SELECT * FROM comments ORDER BY created_at DESC');
    let commentsHtml = rows.map(c =>
        `<div class="comment"><b>${c.username}</b>: ${c.comment}</div>`
    ).join('');
    
    res.send(`<!DOCTYPE html>
<html><head><title>Comments - VulnCorp</title></head>
<body>
<h2>Comments</h2>
${commentsHtml}
<h3>Add Comment</h3>
<form action="/api/comments" method="POST">
    <input name="username" placeholder="Your name"><br>
    <textarea name="comment" placeholder="Your comment"></textarea><br>
    <button>Submit</button>
</form>
</body></html>`);
});

app.post('/api/comments', (req, res) => {
    const { username, comment } = req.body;
    try {
        runSql(`INSERT INTO comments (username, comment, page) VALUES ('${username}', '${comment}', '/comments')`);
        res.json({ success: true, message: `Thank you ${username}! Your comment: ${comment}` });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

// ═══ VULN #10: Command Injection on ping ═══
app.get('/api/ping', (req, res) => {
    const host = req.query.host || '127.0.0.1';
    const cmd = process.platform === 'win32' ? `ping -n 1 ${host}` : `ping -c 1 ${host}`;
    exec(cmd, { timeout: 10000 }, (err, stdout, stderr) => {
        res.json({
            host: host,
            output: stdout || stderr || (err ? err.message : 'No output'),
            command: cmd
        });
    });
});

// ═══ VULN #9: Directory Traversal ═══
app.get('/api/file', (req, res) => {
    const filePath = req.query.path || 'readme.txt';
    const fullPath = path.join(__dirname, filePath);
    try {
        const content = fs.readFileSync(fullPath, 'utf-8');
        res.send(content);
    } catch (err) {
        res.status(404).json({ error: `File not found: ${fullPath}` });
    }
});

// ═══ VULN #12: Mass Assignment ═══
app.post('/api/user/update', (req, res) => {
    const data = req.body;
    if (data.username) {
        try {
            const fields = Object.entries(data)
                .filter(([k]) => k !== 'id')
                .map(([k, v]) => `${k}='${v}'`)
                .join(', ');
            runSql(`UPDATE users SET ${fields} WHERE username='${data.username}'`);
            res.json({ success: true, updated: data });
        } catch (err) {
            res.status(500).json({ error: err.message });
        }
    } else {
        res.status(400).json({ error: 'username required' });
    }
});

// ═══ VULN #13: Open Redirect ═══
app.get('/redirect', (req, res) => {
    const url = req.query.url || '/';
    res.redirect(url);
});

// ═══ VULN #7: Exposed sensitive files ═══
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
API_KEY=cyph3x_internal_api_key_do_not_share`
    );
});

app.get('/.git/HEAD', (req, res) => {
    res.type('text/plain').send('ref: refs/heads/main');
});

app.get('/admin', (req, res) => {
    res.send(`<!DOCTYPE html>
<html><head><title>Admin - VulnCorp</title></head>
<body>
<h2>Admin Dashboard</h2>
<p>Server: Apache/2.4.41 (Ubuntu)</p>
<p>Node: ${process.version}</p>
<a href="/admin/phpinfo">PHP Info</a> | <a href="/admin/logs">Logs</a>
<!-- DB_HOST=mysql.internal DB_PASS=vulncorp_super_secret_2024 AWS_KEY=AKIAIOSFODNN7EXAMPLE -->
<div style="display:none">Internal API: http://10.0.0.5:8080/internal</div>
</body></html>`);
});

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

app.post('/contact', (req, res) => {
    const { name, message } = req.body;
    res.send(`<p>Thank you ${name}! Your message: ${message}</p>`);
});

app.get('/api/orders/:id', (req, res) => {
    try {
        const row = queryOne(`SELECT * FROM orders WHERE id=${req.params.id}`);
        res.json(row || { error: 'Not found' });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.use((err, req, res, next) => {
    res.status(500).json({ error: err.message, stack: err.stack });
});

// ═══ Start ═══
async function start() {
    const SQL = await initSqlJs();
    db = new SQL.Database();
    
    // Create tables
    db.run(`CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT,
        password_hash TEXT, email TEXT, role TEXT DEFAULT 'user', ssn TEXT, phone TEXT
    )`);
    db.run(`CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT,
        price REAL, category TEXT
    )`);
    db.run(`CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, comment TEXT,
        page TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )`);
    db.run(`CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_id INTEGER,
        credit_card TEXT, amount REAL, status TEXT
    )`);
    
    // Seed  
    db.run(`INSERT INTO users (username, password, password_hash, email, role, ssn, phone) VALUES
        ('admin','admin123','0192023a7bbd73250516f069df18b500','admin@vulncorp.com','superadmin','123-45-6789','555-0100'),
        ('john','password123','482c811da5d5b4bc6d497ffa98491e38','john@vulncorp.com','user','234-56-7890','555-0101'),
        ('jane','letmein','0d107d09f5bbe40cade3de5c71e9e9b7','jane@vulncorp.com','editor','345-67-8901','555-0102'),
        ('bob','qwerty','d8578edf8458ce06fbc5bb76a58c5ca4','bob@vulncorp.com','user','456-78-9012','555-0103')`);
    db.run(`INSERT INTO products (name, description, price, category) VALUES
        ('Enterprise License','Full enterprise software license',9999.99,'software'),
        ('Security Audit','Professional security audit',4999.99,'services'),
        ('Cloud Hosting','Annual cloud plan',2999.99,'cloud'),
        ('Training Course','Cybersecurity training',1499.99,'education')`);
    db.run(`INSERT INTO comments (username, comment, page) VALUES
        ('john','Great product!','/products'),
        ('jane','Need more docs','/products'),
        ('admin','Updated FAQ','/about')`);
    db.run(`INSERT INTO orders (user_id, product_id, credit_card, amount, status) VALUES
        (1,1,'4111-1111-1111-1111',9999.99,'completed'),
        (2,2,'4222-2222-2222-2222',4999.99,'completed'),
        (3,3,'4333-3333-3333-3333',2999.99,'pending')`);
    
    console.log('Database seeded.');
    
    const PORT = process.env.PORT || 3000;
    app.listen(PORT, '0.0.0.0', () => {
        console.log(`\n  VulnCorp running on http://localhost:${PORT}`);
        console.log('  WARNING: This app is intentionally vulnerable!\n');
    });
}

start().catch(console.error);
