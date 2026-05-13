const express = require('express');
const Datastore = require('nedb');
const util = require('util');
if (!util.isDate) util.isDate = (d) => d instanceof Date;
if (!util.isRegExp) util.isRegExp = (r) => r instanceof RegExp;
if (!util.isArray) util.isArray = Array.isArray;

const app = express();
const port = 3003;

app.use(express.urlencoded({ extended: false }));
app.use(express.json());

// --- Persistent DB for Stored XSS ---
// Stores blog comments & user messages without sanitization
const commentsDb = new Datastore({ filename: './comments.db', autoload: true });
const messagesDb = new Datastore({ filename: './messages.db', autoload: true });

// Seed initial comments
commentsDb.remove({}, { multi: true }, () => {
  commentsDb.insert([
    { author: 'Alice', body: 'Great article! Very informative.', date: '2026-04-01' },
    { author: 'Bob', body: 'I learned so much from this post.', date: '2026-04-02' },
  ]);
});

// =============================================
//  PREMIUM DESIGN SYSTEM
// =============================================
const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  :root {
    --bg-primary: #0a0a0f;
    --bg-secondary: #111118;
    --bg-card: rgba(255,255,255,0.04);
    --bg-card-hover: rgba(255,255,255,0.07);
    --border: rgba(255,255,255,0.08);
    --accent: #a855f7;
    --accent-2: #ec4899;
    --accent-glow: rgba(168,85,247,0.3);
    --text-primary: #f1f0f5;
    --text-secondary: #8b8a99;
    --danger: #ef4444;
    --success: #22c55e;
    --warning: #f59e0b;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: 'Inter', sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
  }

  /* NAV */
  nav {
    position: sticky;
    top: 0;
    z-index: 100;
    background: rgba(10,10,15,0.85);
    backdrop-filter: blur(20px);
    border-bottom: 1px solid var(--border);
    padding: 0 2rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 64px;
  }

  .nav-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    font-weight: 700;
    font-size: 1.1rem;
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-decoration: none;
  }

  .nav-brand .dot {
    width: 10px;
    height: 10px;
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    border-radius: 50%;
    -webkit-text-fill-color: initial;
    box-shadow: 0 0 10px var(--accent-glow);
  }

  .nav-links {
    display: flex;
    gap: 0.25rem;
    list-style: none;
  }

  .nav-links a {
    color: var(--text-secondary);
    text-decoration: none;
    font-size: 0.875rem;
    font-weight: 500;
    padding: 0.5rem 0.85rem;
    border-radius: 8px;
    transition: all 0.2s;
  }

  .nav-links a:hover {
    color: var(--text-primary);
    background: var(--bg-card);
  }

  .nav-badge {
    font-size: 0.65rem;
    font-weight: 600;
    background: var(--danger);
    color: white;
    padding: 2px 7px;
    border-radius: 999px;
    margin-left: 6px;
  }

  /* LAYOUT */
  .page {
    max-width: 1000px;
    margin: 0 auto;
    padding: 3rem 2rem;
  }

  .page-hero {
    margin-bottom: 3rem;
  }

  .tag {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--accent);
    background: rgba(168,85,247,0.12);
    border: 1px solid rgba(168,85,247,0.25);
    padding: 4px 12px;
    border-radius: 999px;
    margin-bottom: 1rem;
  }

  .tag.danger { color: var(--danger); background: rgba(239,68,68,0.1); border-color: rgba(239,68,68,0.25); }
  .tag.warning { color: var(--warning); background: rgba(245,158,11,0.1); border-color: rgba(245,158,11,0.25); }
  .tag.success { color: var(--success); background: rgba(34,197,94,0.1); border-color: rgba(34,197,94,0.25); }

  h1 {
    font-size: 2.5rem;
    font-weight: 700;
    line-height: 1.2;
    margin-bottom: 0.75rem;
  }

  h2 {
    font-size: 1.5rem;
    font-weight: 600;
    margin-bottom: 1rem;
  }

  h3 { font-size: 1.1rem; font-weight: 600; margin-bottom: 0.5rem; }

  p { color: var(--text-secondary); line-height: 1.7; margin-bottom: 1rem; }

  /* CARDS */
  .card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 2rem;
    margin-bottom: 1.5rem;
    transition: all 0.2s;
  }

  .card:hover {
    background: var(--bg-card-hover);
    border-color: rgba(168,85,247,0.2);
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(168,85,247,0.1);
  }

  .grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    margin-bottom: 1.5rem;
  }

  /* FORMS */
  .form-group {
    margin-bottom: 1.25rem;
  }

  label {
    display: block;
    font-size: 0.8rem;
    font-weight: 500;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.4rem;
  }

  input[type=text], input[type=search], input[type=password],
  textarea, select {
    width: 100%;
    background: rgba(255,255,255,0.05);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.7rem 1rem;
    color: var(--text-primary);
    font-family: 'Inter', sans-serif;
    font-size: 0.9rem;
    outline: none;
    transition: all 0.2s;
  }

  input:focus, textarea:focus {
    border-color: var(--accent);
    background: rgba(168,85,247,0.05);
    box-shadow: 0 0 0 3px var(--accent-glow);
  }

  textarea { min-height: 100px; resize: vertical; }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 0.65rem 1.5rem;
    border: none;
    border-radius: 10px;
    font-family: 'Inter', sans-serif;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    text-decoration: none;
  }

  .btn-primary {
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    color: white;
    box-shadow: 0 4px 15px var(--accent-glow);
  }

  .btn-primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px var(--accent-glow);
  }

  .btn-ghost {
    background: var(--bg-card);
    color: var(--text-primary);
    border: 1px solid var(--border);
  }

  .btn-ghost:hover { background: var(--bg-card-hover); }

  /* COMMENT CARD */
  .comment {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1rem;
  }

  .comment-meta {
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-bottom: 0.5rem;
  }

  .comment-author { font-weight: 600; color: var(--accent); }

  /* ALERT BOX */
  .alert {
    padding: 1rem 1.25rem;
    border-radius: 10px;
    font-size: 0.875rem;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: flex-start;
    gap: 10px;
  }

  .alert-danger { background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); color: #fca5a5; }
  .alert-info { background: rgba(168,85,247,0.1); border: 1px solid rgba(168,85,247,0.3); color: #d8b4fe; }
  .alert-success { background: rgba(34,197,94,0.1); border: 1px solid rgba(34,197,94,0.3); color: #86efac; }

  /* BADGE */
  .badge {
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 2px 10px;
    border-radius: 999px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .badge-red { background: rgba(239,68,68,0.2); color: #f87171; }
  .badge-yellow { background: rgba(245,158,11,0.2); color: #fbbf24; }
  .badge-purple { background: rgba(168,85,247,0.2); color: #c084fc; }

  /* STATS ROW */
  .stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
    margin-bottom: 2rem;
  }

  .stat-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
  }

  .stat-value {
    font-size: 2rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  .stat-label { font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px; }

  /* SEARCH RESULT */
  .search-result {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem 1.25rem;
    margin-top: 1rem;
    font-size: 0.9rem;
  }

  /* CODE */
  code {
    font-family: 'Courier New', monospace;
    font-size: 0.8rem;
    background: rgba(255,255,255,0.07);
    padding: 2px 7px;
    border-radius: 5px;
    color: var(--accent);
  }

  pre {
    background: #0d0d14;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.25rem;
    overflow-x: auto;
    font-family: 'Courier New', monospace;
    font-size: 0.8rem;
    color: #a78bfa;
    margin-bottom: 1.5rem;
  }

  /* FOOTER */
  footer {
    text-align: center;
    padding: 2rem;
    border-top: 1px solid var(--border);
    color: var(--text-secondary);
    font-size: 0.8rem;
    margin-top: 4rem;
  }

  /* HERO GRADIENT */
  .hero-gradient {
    background: radial-gradient(ellipse at top, rgba(168,85,247,0.12) 0%, transparent 60%);
    padding-top: 4rem;
    padding-bottom: 2rem;
  }

  .gradient-text {
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  /* XSS SINK DISPLAY */
  .xss-output {
    background: rgba(239,68,68,0.05);
    border: 1px dashed rgba(239,68,68,0.3);
    border-radius: 10px;
    padding: 1rem 1.25rem;
    min-height: 50px;
    margin-top: 1rem;
    font-size: 0.9rem;
    color: var(--text-secondary);
  }
`;

const renderLayout = (title, activePage, content, extraScript = '') => `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title} — NexusBlog</title>
  <style>${CSS}</style>
</head>
<body>
  <nav>
    <a href="/" class="nav-brand"><span class="dot"></span>NexusBlog</a>
    <ul class="nav-links">
      <li><a href="/">Home</a></li>
      <li><a href="/blog">Blog</a></li>
      <li><a href="/search">Search</a></li>
      <li><a href="/profile">Profile</a></li>
      <li><a href="/feedback">Feedback<span class="nav-badge">NEW</span></a></li>
      <li><a href="/admin">Admin</a></li>
    </ul>
  </nav>

  ${content}

  <footer>
    <p>© 2026 NexusBlog. Powering thoughts, one post at a time.</p>
  </footer>
  ${extraScript}
</body>
</html>
`;

// =============================================
//  PAGE 1: HOME
// =============================================
app.get('/', (req, res) => {
  const html = `
  <div class="hero-gradient page">
    <div class="page-hero">
      <div class="tag">⚡ XSS Showcase Target 2</div>
      <h1>Welcome to <span class="gradient-text">NexusBlog</span></h1>
      <p>Your modern platform for sharing ideas, publishing thoughts, and engaging with the community. Search posts, leave comments, and update your profile — all in one place.</p>
      <div style="display:flex; gap:1rem; margin-top:2rem; flex-wrap:wrap;">
        <a href="/blog" class="btn btn-primary">📝 Read the Blog</a>
        <a href="/search" class="btn btn-ghost">🔍 Search Posts</a>
      </div>
    </div>

    <div class="stats">
      <div class="stat-card">
        <div class="stat-value">3</div>
        <div class="stat-label">XSS Vulnerability Types</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">6</div>
        <div class="stat-label">Distinct Attack Vectors</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">11</div>
        <div class="stat-label">Total Payloads</div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="tag danger">🔴 Critical</div>
        <h3>Stored XSS</h3>
        <p>Malicious scripts are saved in the database and executed every time any user loads the infected page.</p>
        <a href="/blog" class="btn btn-ghost" style="margin-top:0.5rem;">View Blog Comments →</a>
      </div>
      <div class="card">
        <div class="tag warning">🟡 High</div>
        <h3>Reflected XSS</h3>
        <p>User input is reflected directly in HTTP responses. Injected scripts execute immediately on the victim's browser.</p>
        <a href="/search" class="btn btn-ghost" style="margin-top:0.5rem;">Try the Search Bar →</a>
      </div>
      <div class="card">
        <div class="tag warning">🟡 High</div>
        <h3>DOM-Based XSS</h3>
        <p>The DOM is modified client-side using unsafe sinks like <code>innerHTML</code> without server interaction.</p>
        <a href="/profile" class="btn btn-ghost" style="margin-top:0.5rem;">View Profile Page →</a>
      </div>
      <div class="card">
        <div class="tag">🟢 Test Ready</div>
        <h3>Feedback Form</h3>
        <p>The feedback page stores messages in the database without sanitization — a classic Stored XSS sink.</p>
        <a href="/feedback" class="btn btn-ghost" style="margin-top:0.5rem;">Submit Feedback →</a>
      </div>
    </div>
  </div>
  `;
  res.send(renderLayout('Home', 'home', html));
});


// =============================================
//  PAGE 2: BLOG (STORED XSS #1)
// =============================================
app.get('/blog', (req, res) => {
  commentsDb.find({}).sort({ date: -1 }).exec((err, comments) => {
    console.log("Found comments:", comments, "Err:", err);
    const commentHtml = (comments || []).map(c => `
      <div class="comment">
        <div class="comment-meta">
          <span class="comment-author">${c.author}</span>
          <span>${c.date}</span>
        </div>
        <!-- INTENTIONAL STORED XSS: Comment body is rendered directly to innerHTML without escaping -->
        <p style="color: var(--text-primary); margin:0;">${c.body}</p>
      </div>
    `).join('');

    const html = `
    <div class="page">
      <div class="tag danger">🔴 Stored XSS Vector</div>
      <h1>The <span class="gradient-text">Blog</span></h1>
      <p>Read the latest posts and community comments. New comments are saved and displayed to <strong>all visitors</strong>.</p>

      <div class="card">
        <h2>Latest Post: Understanding Web Security</h2>
        <p>Modern web applications face an ever-growing list of threats. From injection attacks to cross-site scripting, developers must be vigilant about sanitizing all user-supplied data before rendering it to the DOM...</p>
        <p><em style="font-size:0.8rem; color: var(--text-secondary);">Published April 11, 2026</em></p>
      </div>

      <h2 style="margin-bottom:1rem;">Community Comments</h2>
      <div class="alert alert-danger">
        ⚠️ <strong>Vulnerability Active:</strong> Comments are stored and rendered without HTML sanitization. A <code>&lt;script&gt;</code> tag posted here will execute for every visitor.
      </div>
      ${commentHtml || '<p>No comments yet.</p>'}

      <div class="card" style="margin-top:2rem;">
        <h3>Leave a Comment</h3>
        <!-- STORED XSS SINK -->
        <form method="POST" action="/blog/comment">
          <div class="form-group">
            <label>Your Name</label>
            <input type="text" name="author" placeholder="Enter your name" required />
          </div>
          <div class="form-group">
            <label>Your Comment</label>
            <textarea name="body" placeholder="Write your comment..."></textarea>
          </div>
          <button type="submit" class="btn btn-primary">Post Comment</button>
        </form>
      </div>
    </div>
    `;
    res.send(renderLayout('Blog', 'blog', html));
  });
});

// STORED XSS - Store comment without sanitization
app.post('/blog/comment', (req, res) => {
  const { author, body } = req.body;
  console.log("POST /blog/comment receiving:", req.body);
  // INTENTIONAL STORED XSS: No sanitization before inserting into DB
  commentsDb.insert({ author, body, date: new Date().toISOString().split('T')[0] }, (err) => {
    console.log("INSERT err:", err);
    res.redirect('/blog');
  });
});


// =============================================
//  PAGE 3: SEARCH (REFLECTED XSS)
// =============================================
app.get('/search', (req, res) => {
  const q = req.query.q || '';

  // INTENTIONAL REFLECTED XSS: query is echoed directly into the page HTML
  const resultHtml = q ? `
    <div class="search-result">
      <div class="tag warning" style="margin-bottom:0.75rem;">Reflected XSS Vector Active</div>
      <p style="margin:0; color: var(--text-secondary);">Showing results for: </p>
      <h3 style="margin-top:0.25rem;">${q}</h3>
    </div>
    <div class="card">
      <p>📄 <strong>Web Security Fundamentals</strong> — A comprehensive guide to protecting web applications...</p>
    </div>
    <div class="card">
      <p>📄 <strong>Understanding XSS Attacks</strong> — Cross-site scripting explained from the ground up...</p>
    </div>
  ` : '';

  const html = `
  <div class="page">
    <div class="tag warning">🟡 Reflected XSS Vector</div>
    <h1><span class="gradient-text">Search</span> Posts</h1>
    <p>Find articles and blog posts across all categories. Your search term is displayed directly in the results below.</p>

    <!-- REFLECTED XSS SINK: ?q= is reflected directly into page -->
    <div class="card">
      <form method="GET" action="/search">
        <div class="form-group">
          <label>Search Query</label>
          <input type="search" name="q" value="${q}" placeholder="Search for articles, topics..." />
        </div>
        <button type="submit" class="btn btn-primary">🔍 Search</button>
      </form>
    </div>

    ${q ? '' : `
    <div class="alert alert-info">
      💡 <strong>Hint for Agent 04:</strong> Try injecting <code>&lt;script&gt;alert(1)&lt;/script&gt;</code> via the <code>?q=</code> URL parameter. The value is reflected into the DOM without escaping.
    </div>
    `}

    ${resultHtml}
  </div>
  `;
  res.send(renderLayout('Search', 'search', html));
});


// =============================================
//  PAGE 4: PROFILE (DOM-BASED XSS)
// =============================================
app.get('/profile', (req, res) => {
  const domXssScript = `
  <script>
    // INTENTIONAL DOM XSS: location.hash is read and passed directly to innerHTML
    function loadTab() {
      const hash = decodeURIComponent(location.hash.substring(1));
      if (hash) {
        document.getElementById('tab-output').innerHTML = hash;
      }
    }
    window.addEventListener('load', loadTab);
    window.addEventListener('hashchange', loadTab);
  </script>
  `;

  const html = `
  <div class="page">
    <div class="tag warning">🟡 DOM-Based XSS Vector</div>
    <h1>My <span class="gradient-text">Profile</span></h1>
    <p>Manage your account and view personalized settings. Navigate between tabs using the buttons below.</p>

    <div class="grid-2">
      <div class="card">
        <h3>👤 Account Info</h3>
        <p><strong>Username:</strong> jsmith</p>
        <p><strong>Email:</strong> jsmith@nexusblog.com</p>
        <p><strong>Role:</strong> <span class="badge badge-purple">Contributor</span></p>
      </div>
      <div class="card">
        <h3>📊 Activity</h3>
        <p><strong>Posts:</strong> 12</p>
        <p><strong>Comments:</strong> 48</p>
        <p><strong>Joined:</strong> January 2026</p>
      </div>
    </div>

    <div class="card">
      <h3>Tab Navigation</h3>
      <p>Click a tab to load content dynamically via the URL hash — or inject your own content.</p>
      <div style="display:flex; gap:0.75rem; flex-wrap:wrap; margin-bottom:1rem;">
        <a href="#settings" class="btn btn-ghost">⚙️ Settings</a>
        <a href="#notifications" class="btn btn-ghost">🔔 Notifications</a>
        <a href="#billing" class="btn btn-ghost">💳 Billing</a>
      </div>
      <!-- INTENTIONAL DOM XSS SINK: innerHTML receives value of location.hash -->
      <div class="alert alert-danger" style="margin-bottom:1rem;">
        ⚠️ <strong>DOM Sink Active:</strong> The hash value is passed directly to <code>innerHTML</code>. Try: <code>#&lt;img src=x onerror=alert(1)&gt;</code>
      </div>
      <label>Tab Output (DOM XSS Sink):</label>
      <div id="tab-output" class="xss-output">No tab selected. Click a tab above.</div>
    </div>
  </div>
  `;
  res.send(renderLayout('Profile', 'profile', html, domXssScript));
});


// =============================================
//  PAGE 5: FEEDBACK (STORED XSS #2)
// =============================================
app.get('/feedback', (req, res) => {
  messagesDb.find({}).sort({ ts: -1 }).limit(10).exec((err, msgs) => {
    const msgHtml = (msgs || []).map(m => `
      <div class="comment">
        <div class="comment-meta">
          <span class="comment-author">${m.email}</span>
          <span>${new Date(m.ts).toLocaleString()}</span>
        </div>
        <!-- INTENTIONAL STORED XSS: Message rendered unescaped -->
        <p style="margin:0; color:var(--text-primary);">${m.message}</p>
      </div>
    `).join('') || '<p>No feedback received yet.</p>';

    const html = `
    <div class="page">
      <div class="tag danger">🔴 Stored XSS Vector #2</div>
      <h1>Send Us <span class="gradient-text">Feedback</span></h1>
      <p>We value your opinion! Share your thoughts about NexusBlog. All feedback is stored and displayed to our admin team.</p>

      <div class="alert alert-danger">
        ⚠️ <strong>Vulnerability Active:</strong> The message field is stored in the database and rendered to this page without sanitization. This is a Stored XSS sink.
      </div>

      <div class="card">
        <h3>Submit Feedback</h3>
        <form method="POST" action="/feedback">
          <div class="form-group">
            <label>Your Email</label>
            <input type="text" name="email" placeholder="your@email.com" required />
          </div>
          <div class="form-group">
            <label>Rating</label>
            <select name="rating">
              <option>⭐ 1 - Poor</option>
              <option>⭐⭐ 2 - Fair</option>
              <option selected>⭐⭐⭐ 3 - Good</option>
              <option>⭐⭐⭐⭐ 4 - Great</option>
              <option>⭐⭐⭐⭐⭐ 5 - Excellent</option>
            </select>
          </div>
          <div class="form-group">
            <label>Message</label>
            <textarea name="message" placeholder="Enter your feedback..."></textarea>
          </div>
          <button type="submit" class="btn btn-primary">📨 Submit Feedback</button>
        </form>
      </div>

      <h2 style="margin-bottom:1rem;">Recent Submissions</h2>
      ${msgHtml}
    </div>
    `;
    res.send(renderLayout('Feedback', 'feedback', html));
  });
});

// STORED XSS - Store message without sanitization
app.post('/feedback', (req, res) => {
  const { email, message, rating } = req.body;
  // INTENTIONAL STORED XSS: No sanitization
  messagesDb.insert({ email, message, rating, ts: Date.now() }, () => {
    res.redirect('/feedback');
  });
});


// =============================================
//  PAGE 6: ADMIN (REFLECTED XSS #2 + BROKEN ACCESS CONTROL)
// =============================================
app.get('/admin', (req, res) => {
  const notice = req.query.notice || '';

  // INTENTIONAL REFLECTED XSS: ?notice= is reflected directly into page (no auth check either)
  const html = `
  <div class="page">
    <div class="tag danger">🔴 Broken Access Control + Reflected XSS</div>
    <h1>Admin <span class="gradient-text">Dashboard</span></h1>
    <p>Welcome to the administrative panel. This area should be restricted to authenticated administrators only.</p>

    ${notice ? `
    <div class="alert alert-info">
      <!-- INTENTIONAL REFLECTED XSS SINK: ?notice= reflected here without escaping -->
      📢 System Notice: ${notice}
    </div>
    ` : `
    <div class="alert alert-danger">
      ⚠️ <strong>No Authentication Required.</strong> This page is publicly accessible. Try appending <code>?notice=&lt;script&gt;alert(1)&lt;/script&gt;</code> to the URL.
    </div>
    `}

    <div class="stats">
      <div class="stat-card">
        <div class="stat-value">3</div>
        <div class="stat-label">Active Users</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">2</div>
        <div class="stat-label">Blog Posts</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">5</div>
        <div class="stat-label">Feedback Messages</div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <h3>🗑️ Moderate Comments</h3>
        <p>Review and delete community comments from the blog. No audit log is maintained.</p>
        <a href="/blog" class="btn btn-ghost" style="margin-top:0.5rem;">View Comments</a>
      </div>
      <div class="card">
        <h3>📬 View Feedback</h3>
        <p>Read all user feedback submissions stored in the database.</p>
        <a href="/feedback" class="btn btn-ghost" style="margin-top:0.5rem;">View Feedback</a>
      </div>
    </div>
  </div>
  `;
  res.send(renderLayout('Admin Dashboard', 'admin', html));
});


app.listen(port, () => {
  console.log(`Target 2 (XSS Showcase) running on http://localhost:${port}`);
});
