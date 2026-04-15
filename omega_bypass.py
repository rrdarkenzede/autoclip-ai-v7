"""
omega_bypass.py - Sidecar Manager for AutoClipAI v7.0 OMEGA
Handles the lifecycle of the bgutil-pot process and provides 
configuration for yt-dlp including TLS fingerprinting.
"""

import subprocess
import os
import time
import logging
import platform
import requests

log = logging.getLogger("AutoClipAI.Omega")

def get_binary_path():
    base = os.path.dirname(os.path.abspath(__file__))
    is_linux = platform.system().lower() == "linux"
    binary_name = "bgutil-pot" if is_linux else "bgutil-pot.exe"
    path = os.path.join(base, binary_name)
    
    # Auto-fetch Linux binary if missing (Cloud survival)
    if is_linux and not os.path.exists(path):
        log.info("🌐 Linux detected. Fetching OMEGA binary (bgutil-pot)...")
        # URL for the latest Rust implementation binary
        url = "https://github.com/jim60105/bgutil-ytdlp-pot-provider-rs/releases/latest/download/bgutil-pot-linux-x86_64"
        try:
            r = requests.get(url, allow_redirects=True)
            with open(path, 'wb') as f:
                f.write(r.content)
            os.chmod(path, 0o755)
            log.info("✅ OMEGA Linux binary installed.")
        except Exception as e:
            log.error(f"❌ Failed to download OMEGA binary: {e}")
    
    return path

BINARY_PATH = get_binary_path()
PORT = 4416

class OmegaBypassManager:
    def __init__(self):
        self.process = None
        self.is_running = False

    def start_sidecar(self):
        """Launches the Rust bgutil-pot binary in a background process."""
        if not os.path.exists(BINARY_PATH):
            log.error(f"❌ OMEGA Binary not found at {BINARY_PATH}")
            return False

        log.info(f"🧬 Starting OMEGA Sidecar (PO-Token Generator) on port {PORT}...")
        try:
            # Command to run the binary as a server
            cmd = [BINARY_PATH, "server", "--address", f"127.0.0.1:{PORT}"]
            
            # Use subprocess.PIPE to avoid cluttering logs in GH Actions
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                text=True
            )
            
            # Wait a few seconds for server to bind
            time.sleep(2)
            if self.process.poll() is None:
                self.is_running = True
                log.info(f"✅ OMEGA Sidecar ACTIVE (PID: {self.process.pid})")
                return True
            else:
                out, err = self.process.communicate()
                log.error(f"❌ OMEGA crashed on startup: {err}")
                return False
        except Exception as e:
            log.error(f"❌ Failed to start OMEGA Sidecar: {e}")
            return False

    def stop_sidecar(self):
        if self.process:
            log.info("🛑 Stopping OMEGA Sidecar...")
            self.process.terminate()
            self.process.wait()
            self.is_running = False

    def get_ydl_opts(self, base_opts=None):
        """Returns yt-dlp options with OMEGA bypass settings."""
        if base_opts is None:
            base_opts = {}
        
        # OMEGA settings
        omega_args = {
            "extractor_args": {
                "youtube": {
                    "pot_provider": "bgutil",
                    "pot_server": f"http://127.0.0.1:{PORT}",
                    "player_client": ["tv_embedded", "ios", "webapp"],
                }
            },
            # TLS Impersonation (requires curl_cffi)
            "impersonate": "safari-ios-17",
        }

        # Merge
        result = base_opts.copy()
        for key, value in omega_args.items():
            if key in result and isinstance(result[key], dict):
                result[key].update(value)
            else:
                result[key] = value
        
        return result

# Singleton instance
omega = OmegaBypassManager()

if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    try:
        success = omega.start_sidecar()
        if success:
            print("Sidecar is running. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        omega.stop_sidecar()
