import asyncio
import os
import sys

# Ensure backend modules can be imported
sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), "backend", "backend"))

from agents.terminal import AgentTerminal

async def main():
    print("[*] Initializing CYPHEX Terminal Engine...")
    terminal = AgentTerminal(agent_name="XSSAgent", target_url="https://httpbin.org", scan_id="test_scan")
    
    print("\n[*] Executing cross-platform pseudo-shell command via CVS...")
    # This curl command will be natively intercepted by cvs_shell.py
    cmd = 'curl -s -X GET https://httpbin.org/get -H "Test-Header: hello" | grep -i test'
    
    result = await terminal.run(cmd)
    
    print("\n[+] Execution Complete!")
    print(f"Exit Code: {result.exit_code}")
    print(f"Duration: {result.duration_ms}ms")
    print(f"STDOUT:\n{result.stdout}")
    print(f"STDERR:\n{result.stderr}")

if __name__ == "__main__":
    asyncio.run(main())
