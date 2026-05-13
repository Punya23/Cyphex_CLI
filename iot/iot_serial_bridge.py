"""
CYPHEX Sentinel — IoT Serial Bridge

Runs on YOUR LAPTOP alongside the CYPHEX backend.
Connects to the Raspberry Pi Pico via USB serial and sends
real-time scan status updates so the LEDs/OLED/buzzer react live.

Usage:
  1. Connect Pi Pico via USB
  2. Find the COM port (e.g., COM3 on Windows)
  3. Run: python iot_serial_bridge.py --port COM3
  4. Start a CYPHEX scan — the Pi Pico will react in real-time

Protocol (sent over serial):
  STATUS:scanning:Agent 01 Recon:Checking headers
  STATUS:critical:3 Vulns Found:SQLi XSS Auth
  STATUS:secure:All patched:Score 92/100
  BEEP:2000:300
  OLED:Line1:Line2:Line3
"""

import serial
import asyncio
import json
import argparse
import sys
import websockets


class IoTBridge:
    """Bridges CYPHEX WebSocket events → Pi Pico serial commands."""

    def __init__(self, serial_port: str, baud: int = 115200):
        self.port = serial_port
        self.baud = baud
        self.ser = None

    def connect(self):
        """Open serial connection to Pi Pico."""
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            print(f"[BRIDGE] Connected to Pi Pico on {self.port}")
            return True
        except Exception as e:
            print(f"[BRIDGE] Failed to connect to {self.port}: {e}")
            return False

    def send(self, command: str):
        """Send a command to Pi Pico."""
        if self.ser and self.ser.is_open:
            self.ser.write((command + "\n").encode())
            print(f"[TX] {command}")

    def handle_event(self, event: dict):
        """Convert a CYPHEX WebSocket event into a Pi Pico serial command."""
        event_type = event.get("type", "")

        if event_type == "scan_start":
            self.send("STATUS:boot:Scan starting:Target found")

        elif event_type == "stage_start":
            stage = event.get("stage", 0)
            name = event.get("name", "")
            if stage <= 2:
                self.send(f"STATUS:scanning:Stage {stage}:{name}")
            elif stage == 3:
                self.send(f"STATUS:attacking:Stage 3:{name}")
            elif stage == 4:
                self.send(f"STATUS:ai:Stage 4:{name}")
            elif stage == 5:
                self.send(f"STATUS:patching:Stage 5:{name}")

        elif event_type == "agent_start":
            agent_name = event.get("agent_name", "Agent")
            task = event.get("task", "")
            self.send(f"OLED:{agent_name}:{task}:")

        elif event_type == "agent_complete":
            agent_name = event.get("agent_name", "Agent")
            vulns = event.get("vulns_found", 0)
            if vulns > 0:
                self.send(f"BEEP:2000:200")

        elif event_type == "vuln_found":
            vuln = event.get("vuln", {})
            severity = vuln.get("severity", "Medium")
            name = vuln.get("name", "Unknown")[:20]
            if severity == "Critical":
                self.send(f"STATUS:critical:{name}:CVSS {vuln.get('cvss_score', '?')}")
            elif severity == "High":
                self.send(f"STATUS:warning:{name}:High severity")

        elif event_type == "scan_complete":
            report = event.get("report", {})
            summary = report.get("summary", {})
            total = summary.get("total_vulns", 0)
            if total == 0:
                self.send("STATUS:secure:No vulns found:Score 100/100")
            elif summary.get("critical", 0) > 0:
                self.send(f"STATUS:critical:{total} vulnerabilities:Check dashboard")
            else:
                self.send(f"STATUS:warning:{total} vulns found:Check dashboard")

        elif event_type == "scan_error":
            self.send(f"STATUS:error:{event.get('error', 'Unknown')[:20]}:")

    async def listen_websocket(self, scan_id: str, ws_url: str = "ws://localhost:8000"):
        """Connect to CYPHEX WebSocket and forward events to Pi Pico."""
        uri = f"{ws_url}/ws/{scan_id}"
        print(f"[BRIDGE] Connecting to WebSocket: {uri}")

        try:
            async with websockets.connect(uri) as ws:
                print(f"[BRIDGE] WebSocket connected! Waiting for events...")
                self.send("STATUS:scanning:Connected:Waiting for scan")

                while True:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=20)
                        event = json.loads(msg)

                        # Skip keepalive/pong
                        if event.get("type") in ("keepalive", "pong"):
                            continue

                        self.handle_event(event)

                        # Stop if scan is done
                        if event.get("type") in ("scan_complete", "scan_error"):
                            print("[BRIDGE] Scan finished.")
                            break

                    except asyncio.TimeoutError:
                        # Send ping
                        await ws.send("ping")

        except Exception as e:
            print(f"[BRIDGE] WebSocket error: {e}")
            self.send(f"STATUS:error:WS disconnected:")

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("[BRIDGE] Serial port closed.")


async def main():
    parser = argparse.ArgumentParser(description="CYPHEX IoT Serial Bridge")
    parser.add_argument("--port", required=True, help="Serial port (e.g., COM3)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate")
    parser.add_argument("--scan-id", required=True, help="CYPHEX scan ID to monitor")
    parser.add_argument("--ws-url", default="ws://localhost:8000", help="CYPHEX WebSocket URL")
    parser.add_argument("--demo", action="store_true", help="Run demo mode (no WebSocket)")
    args = parser.parse_args()

    bridge = IoTBridge(args.port, args.baud)
    if not bridge.connect():
        sys.exit(1)

    if args.demo:
        # Demo mode: simulate events without a real scan
        import time
        print("[BRIDGE] Demo mode — simulating scan events...")
        demo_events = [
            {"type": "scan_start", "target": "http://192.168.1.50:3000"},
            {"type": "stage_start", "stage": 1, "name": "RECONNAISSANCE"},
            {"type": "agent_start", "agent_name": "Recon Agent", "task": "Scanning headers"},
            {"type": "agent_complete", "agent_name": "Recon Agent", "vulns_found": 0},
            {"type": "stage_start", "stage": 2, "name": "CRAWLING"},
            {"type": "agent_start", "agent_name": "Crawler Agent", "task": "Mapping endpoints"},
            {"type": "agent_complete", "agent_name": "Crawler Agent", "vulns_found": 0},
            {"type": "stage_start", "stage": 3, "name": "PARALLEL ATTACK"},
            {"type": "agent_start", "agent_name": "SQLi Agent", "task": "Injection tests"},
            {"type": "vuln_found", "vuln": {"name": "SQL Injection", "severity": "Critical", "cvss_score": 9.8}},
            {"type": "agent_start", "agent_name": "XSS Agent", "task": "Reflected XSS"},
            {"type": "vuln_found", "vuln": {"name": "Reflected XSS", "severity": "High", "cvss_score": 7.5}},
            {"type": "stage_start", "stage": 4, "name": "AI ANALYSIS"},
            {"type": "agent_start", "agent_name": "Analysis Agent", "task": "Mistral 7B processing"},
            {"type": "stage_start", "stage": 5, "name": "PATCH GENERATION"},
            {"type": "scan_complete", "report": {"summary": {"total_vulns": 3, "critical": 1, "high": 1, "medium": 1}}},
        ]
        for event in demo_events:
            bridge.handle_event(event)
            time.sleep(2)
    else:
        await bridge.listen_websocket(args.scan_id, args.ws_url)

    bridge.close()


if __name__ == "__main__":
    asyncio.run(main())
