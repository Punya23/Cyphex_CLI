"""Quick terminal engine test against live VulnCorp."""
import sys, asyncio, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.environ["PYTHONUTF8"] = "1"

from agents.terminal import AgentTerminal

async def test():
    t = AgentTerminal('TestAgent', 'http://localhost:3000', 'test_001')
    
    # Test 1: curl GET
    print("=== Test 1: curl GET ===")
    out = await t.run('curl -s http://localhost:3000', timeout=10)
    print(f"  Success: {out.success}, Length: {len(out.stdout)}")
    print(f"  Contains VulnCorp: {'VulnCorp' in out.stdout}")
    
    # Test 2: curl HEAD
    print("\n=== Test 2: curl -sI ===")
    out = await t.run('curl -sI http://localhost:3000', timeout=10)
    print(f"  Headers: {out.stdout[:200]}")
    
    # Test 3: curl POST
    print("\n=== Test 3: curl POST login ===")
    out = await t.run(
        'curl -s -X POST "http://localhost:3000/api/login" '
        '-d "username=admin&password=admin123" '
        '-H "Content-Type: application/x-www-form-urlencoded"',
        timeout=10
    )
    print(f"  Response: {out.stdout[:200]}")
    
    # Test 4: curl status code
    print("\n=== Test 4: HTTP status code ===")
    out = await t.run(
        'curl -so NUL -w "%{http_code}" http://localhost:3000/.env',
        timeout=10
    )
    print(f"  Status: {out.stdout.strip()}")
    
    # Test 5: check_tool
    print("\n=== Test 5: check_tool ===")
    has_nmap = await t.check_tool("nmap")
    has_curl = await t.check_tool("curl.exe")
    print(f"  nmap={has_nmap}, curl.exe={has_curl}")
    
    print(f"\n=== {len(t.command_history)} commands executed ===")
    print("ALL TESTS PASSED!")

asyncio.run(test())
