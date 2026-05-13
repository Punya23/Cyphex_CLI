"""
CYPHEX — Fine-Tuning Dataset Generator

Generates training data for fine-tuning qwen2.5-coder:7b on
cybersecurity vulnerability patching tasks.

Output format: JSONL (one JSON object per line)
Each example: {"instruction": "...", "input": "...", "output": "..."}
"""

import json

# ═══════════════════════════════════════════════════════════════
# VULNERABILITY → PATCH TRAINING PAIRS
# Each pair teaches the model to: see vuln → generate fix
# ═══════════════════════════════════════════════════════════════

TRAINING_DATA = [
    # ─── SQL Injection Fixes ───
    {
        "instruction": "Fix the SQL injection vulnerability in this code.",
        "input": """# Python Flask - VULNERABLE
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    result = db.execute(query)
    return jsonify(result)""",
        "output": """# Python Flask - PATCHED (Parameterized Query)
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    query = "SELECT * FROM users WHERE username=? AND password=?"
    result = db.execute(query, (username, password))
    return jsonify(result)

# Fix: Used parameterized query with ? placeholders instead of f-string interpolation.
# This prevents SQL injection by treating user input as data, not SQL code."""
    },
    {
        "instruction": "Fix the SQL injection vulnerability in this Node.js code.",
        "input": """// Express.js - VULNERABLE
app.get('/users', (req, res) => {
    const id = req.query.id;
    const sql = "SELECT * FROM users WHERE id = " + id;
    db.query(sql, (err, results) => {
        res.json(results);
    });
});""",
        "output": """// Express.js - PATCHED (Prepared Statement)
app.get('/users', (req, res) => {
    const id = parseInt(req.query.id, 10);
    if (isNaN(id)) {
        return res.status(400).json({ error: 'Invalid ID' });
    }
    const sql = "SELECT * FROM users WHERE id = ?";
    db.query(sql, [id], (err, results) => {
        res.json(results);
    });
});

// Fix: Used prepared statement with ? placeholder and input validation.
// parseInt ensures the ID is a number before querying."""
    },
    {
        "instruction": "Fix the SQL injection in this PHP code.",
        "input": """<?php
// PHP - VULNERABLE
$search = $_GET['search'];
$query = "SELECT * FROM products WHERE name LIKE '%$search%'";
$result = mysqli_query($conn, $query);
?>""",
        "output": """<?php
// PHP - PATCHED (Prepared Statement with PDO)
$search = $_GET['search'];
$stmt = $conn->prepare("SELECT * FROM products WHERE name LIKE ?");
$searchParam = "%" . $search . "%";
$stmt->bind_param("s", $searchParam);
$stmt->execute();
$result = $stmt->get_result();
?>

// Fix: Used prepared statement with bind_param instead of string interpolation.
// The % wildcards are safely added to the parameter, not the query string."""
    },

    # ─── XSS Fixes ───
    {
        "instruction": "Fix the Cross-Site Scripting (XSS) vulnerability in this code.",
        "input": """# Python Flask - VULNERABLE
@app.route('/search')
def search():
    query = request.args.get('q', '')
    return f'<h1>Search results for: {query}</h1>'""",
        "output": """# Python Flask - PATCHED (Output Encoding)
from markupsafe import escape

@app.route('/search')
def search():
    query = request.args.get('q', '')
    return f'<h1>Search results for: {escape(query)}</h1>'

# Fix: Used markupsafe.escape() to HTML-encode user input before rendering.
# This converts < to &lt;, > to &gt;, preventing script injection."""
    },
    {
        "instruction": "Fix the reflected XSS vulnerability in this JavaScript code.",
        "input": """// Express.js - VULNERABLE
app.get('/profile', (req, res) => {
    const name = req.query.name;
    res.send(`<div class="profile"><h2>${name}</h2></div>`);
});""",
        "output": """// Express.js - PATCHED (HTML Entity Encoding)
const escapeHtml = (str) => {
    return str.replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;')
              .replace(/'/g, '&#39;');
};

app.get('/profile', (req, res) => {
    const name = escapeHtml(req.query.name || '');
    res.send(`<div class="profile"><h2>${name}</h2></div>`);
});

// Fix: Added escapeHtml function to encode HTML entities in user input.
// Also added fallback empty string for missing query parameter."""
    },

    # ─── Command Injection Fixes ───
    {
        "instruction": "Fix the command injection vulnerability in this code.",
        "input": """# Python - VULNERABLE
import os

@app.route('/ping')
def ping():
    host = request.args.get('host')
    output = os.popen(f'ping -c 3 {host}').read()
    return f'<pre>{output}</pre>'""",
        "output": """# Python - PATCHED (Input Validation + subprocess)
import subprocess
import re

@app.route('/ping')
def ping():
    host = request.args.get('host', '')

    # Validate: only allow hostnames and IPs
    if not re.match(r'^[a-zA-Z0-9._-]+$', host):
        return jsonify({'error': 'Invalid hostname'}), 400

    try:
        result = subprocess.run(
            ['ping', '-c', '3', host],
            capture_output=True, text=True, timeout=10
        )
        return f'<pre>{escape(result.stdout)}</pre>'
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Ping timed out'}), 408

# Fix: 1) Input validation with regex allowlist
#       2) subprocess.run with list args (no shell injection possible)
#       3) Timeout to prevent hanging
#       4) Output encoding to prevent XSS in response"""
    },

    # ─── Path Traversal / LFI Fixes ───
    {
        "instruction": "Fix the Local File Inclusion (LFI) vulnerability in this code.",
        "input": """# Python Flask - VULNERABLE
@app.route('/download')
def download():
    filename = request.args.get('file')
    return send_file(f'/var/uploads/{filename}')""",
        "output": """# Python Flask - PATCHED (Path Sanitization)
import os

UPLOAD_DIR = '/var/uploads'

@app.route('/download')
def download():
    filename = request.args.get('file', '')

    # Remove path traversal characters
    filename = os.path.basename(filename)

    # Resolve and validate the full path
    full_path = os.path.realpath(os.path.join(UPLOAD_DIR, filename))

    # Ensure the resolved path is within the upload directory
    if not full_path.startswith(os.path.realpath(UPLOAD_DIR)):
        return jsonify({'error': 'Access denied'}), 403

    if not os.path.isfile(full_path):
        return jsonify({'error': 'File not found'}), 404

    return send_file(full_path)

# Fix: 1) os.path.basename strips directory traversal (../)
#       2) os.path.realpath resolves symlinks
#       3) Prefix check ensures file is within allowed directory
#       4) File existence check prevents information leakage"""
    },

    # ─── Authentication Fixes ───
    {
        "instruction": "Fix the insecure authentication in this code.",
        "input": """# Python Flask - VULNERABLE (plaintext passwords)
@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    db.execute("INSERT INTO users (username, password) VALUES (?, ?)",
               (username, password))
    return 'Registered'""",
        "output": """# Python Flask - PATCHED (bcrypt hashing)
from werkzeug.security import generate_password_hash, check_password_hash

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']

    # Validate password strength
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400

    # Hash password with bcrypt (salt is auto-generated)
    password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
               (username, password_hash))
    return jsonify({'message': 'Registered successfully'})

# Fix: 1) Passwords are hashed with PBKDF2-SHA256 before storage
#       2) Salt is automatically generated per password
#       3) Minimum password length validation
#       4) Column renamed to password_hash for clarity"""
    },

    # ─── IDOR Fix ───
    {
        "instruction": "Fix the Insecure Direct Object Reference (IDOR) vulnerability.",
        "input": """# Python Flask - VULNERABLE
@app.route('/api/user/<int:user_id>')
def get_user(user_id):
    user = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return jsonify(user)""",
        "output": """# Python Flask - PATCHED (Authorization Check)
from flask_login import current_user, login_required

@app.route('/api/user/<int:user_id>')
@login_required
def get_user(user_id):
    # Only allow users to access their own data (or admins)
    if current_user.id != user_id and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    user = db.execute("SELECT id, username, email FROM users WHERE id=?",
                      (user_id,)).fetchone()
    if not user:
        return jsonify({'error': 'Not found'}), 404

    return jsonify(user)

# Fix: 1) Added @login_required decorator
#       2) Authorization check: user can only access own data
#       3) Admin override for legitimate admin access
#       4) Only return non-sensitive fields (no password hash)
#       5) 404 for missing users to prevent enumeration"""
    },

    # ─── Security Headers Fix ───
    {
        "instruction": "Add security headers to this Express.js application.",
        "input": """// Express.js - NO SECURITY HEADERS
const express = require('express');
const app = express();

app.get('/', (req, res) => {
    res.send('Hello World');
});

app.listen(3000);""",
        "output": """// Express.js - PATCHED (Security Headers with Helmet)
const express = require('express');
const helmet = require('helmet');
const app = express();

// Add security headers
app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'self'"],
            scriptSrc: ["'self'"],
            styleSrc: ["'self'", "'unsafe-inline'"],
            imgSrc: ["'self'", "data:"],
        },
    },
    crossOriginEmbedderPolicy: true,
    crossOriginOpenerPolicy: true,
    crossOriginResourcePolicy: { policy: "same-site" },
    dnsPrefetchControl: true,
    frameguard: { action: 'deny' },
    hidePoweredBy: true,
    hsts: { maxAge: 31536000, includeSubDomains: true },
    ieNoOpen: true,
    noSniff: true,
    referrerPolicy: { policy: 'strict-origin-when-cross-origin' },
    xssFilter: true,
}));

app.get('/', (req, res) => {
    res.send('Hello World');
});

app.listen(3000);

// Fix: Added helmet middleware with comprehensive security headers:
// - CSP prevents XSS and data injection
// - HSTS enforces HTTPS
// - X-Frame-Options prevents clickjacking
// - X-Content-Type-Options prevents MIME sniffing"""
    },

    # ─── Rate Limiting Fix ───
    {
        "instruction": "Add rate limiting to prevent brute-force attacks on this login endpoint.",
        "input": """# Python Flask - VULNERABLE (no rate limiting)
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    user = authenticate(username, password)
    if user:
        return jsonify({'token': generate_token(user)})
    return jsonify({'error': 'Invalid credentials'}), 401""",
        "output": """# Python Flask - PATCHED (Rate Limited)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import time

limiter = Limiter(app=app, key_func=get_remote_address)

# Track failed login attempts
failed_attempts = {}

@app.route('/login', methods=['POST'])
@limiter.limit("5 per minute")  # Max 5 login attempts per minute per IP
def login():
    username = request.form['username']
    password = request.form['password']
    ip = get_remote_address()

    # Check if IP is temporarily locked out
    if ip in failed_attempts:
        attempts, lockout_until = failed_attempts[ip]
        if lockout_until > time.time():
            remaining = int(lockout_until - time.time())
            return jsonify({'error': f'Too many attempts. Try again in {remaining}s'}), 429

    user = authenticate(username, password)
    if user:
        # Clear failed attempts on success
        failed_attempts.pop(ip, None)
        return jsonify({'token': generate_token(user)})

    # Track failed attempt
    attempts, _ = failed_attempts.get(ip, (0, 0))
    attempts += 1
    if attempts >= 5:
        lockout_until = time.time() + 300  # 5-minute lockout
    else:
        lockout_until = 0
    failed_attempts[ip] = (attempts, lockout_until)

    return jsonify({'error': 'Invalid credentials'}), 401

# Fix: 1) Flask-Limiter for IP-based rate limiting (5/min)
#       2) Progressive lockout after 5 failed attempts
#       3) Lockout clears on successful login
#       4) Returns remaining lockout time to user"""
    },

    # ─── Mass Assignment Fix ───
    {
        "instruction": "Fix the mass assignment vulnerability in this code.",
        "input": """# Python Flask - VULNERABLE
@app.route('/api/profile', methods=['PUT'])
@login_required
def update_profile():
    data = request.get_json()
    # Directly updates ALL fields from user input
    db.execute(
        "UPDATE users SET " +
        ", ".join(f"{k}=?" for k in data.keys()) +
        " WHERE id=?",
        list(data.values()) + [current_user.id]
    )
    return jsonify({'message': 'Updated'})""",
        "output": """# Python Flask - PATCHED (Allowlisted Fields)
ALLOWED_PROFILE_FIELDS = {'name', 'email', 'bio', 'avatar_url'}

@app.route('/api/profile', methods=['PUT'])
@login_required
def update_profile():
    data = request.get_json()

    # Only allow specific fields to be updated
    safe_data = {
        k: v for k, v in data.items()
        if k in ALLOWED_PROFILE_FIELDS
    }

    if not safe_data:
        return jsonify({'error': 'No valid fields to update'}), 400

    # Validate email format if provided
    if 'email' in safe_data:
        import re
        if not re.match(r'^[^@]+@[^@]+\\.[^@]+$', safe_data['email']):
            return jsonify({'error': 'Invalid email'}), 400

    db.execute(
        "UPDATE users SET " +
        ", ".join(f"{k}=?" for k in safe_data.keys()) +
        " WHERE id=?",
        list(safe_data.values()) + [current_user.id]
    )
    return jsonify({'message': 'Profile updated', 'fields_updated': list(safe_data.keys())})

# Fix: 1) Allowlist of updateable fields (prevents role/is_admin escalation)
#       2) Input validation for specific fields (email format)
#       3) Returns which fields were actually updated"""
    },
]


def generate_training_file(output_path: str):
    """Generate JSONL training file for fine-tuning."""
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in TRAINING_DATA:
            # Format for instruction fine-tuning
            entry = {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are CYPHEX, an expert cybersecurity AI that specializes in finding and patching web application vulnerabilities. When given vulnerable code, you generate the patched version with detailed comments explaining each fix."
                    },
                    {
                        "role": "user",
                        "content": f"{item['instruction']}\n\n```\n{item['input']}\n```"
                    },
                    {
                        "role": "assistant",
                        "content": f"```\n{item['output']}\n```"
                    }
                ]
            }
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

    print(f"✅ Generated {len(TRAINING_DATA)} training examples → {output_path}")
    print(f"   Covers: SQLi, XSS, CMDi, LFI, Auth, IDOR, Headers, Rate Limiting, Mass Assignment")


if __name__ == "__main__":
    generate_training_file("cyphex_training_data.jsonl")
