"""
P2P Config Loader - Load và validate p2p_config.json
"""
import json
import os
from typing import Dict, List, Optional


class P2PConfig:
    """P2P Configuration"""

    def __init__(self, config_file: str = "config/p2p_config.json"):
        self.config_file = config_file
        self.this_central = {}
        self.peer_centrals = []
        self._load_config()

    def _load_config(self):
        """Load config from file"""
        # Tao config mac dinh neu file khong ton tai
        if not os.path.exists(self.config_file):
            self._create_default_config()

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            self.this_central = config.get("this_central", {})
            self.peer_centrals = config.get("peer_centrals", [])

            # Validate config
            self._validate_config()

        except Exception as e:
            print(f"Error loading P2P config: {e}")
            self._create_default_config()

    def _create_default_config(self):
        """Create default config file"""
        default_config = {
            "this_central": {
                "id": "central-1",
                "ip": "127.0.0.1",
                "api_port": 8000
            },
            "peer_centrals": []
        }

        # Create directory if not exists
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)

        self.this_central = default_config["this_central"]
        self.peer_centrals = default_config["peer_centrals"]

        print(f"Created default P2P config: {self.config_file}")

    def _validate_config(self):
        """Validate config"""
        # Validate this_central
        if not self.this_central.get("id"):
            raise ValueError("Missing 'id' in this_central")

        if not self.this_central.get("ip"):
            raise ValueError("Missing 'ip' in this_central")

        # Validate peer_centrals
        for peer in self.peer_centrals:
            if not peer.get("id"):
                raise ValueError("Missing 'id' in peer_centrals")

            if not peer.get("ip"):
                raise ValueError("Missing 'ip' in peer_centrals")

    def get_this_central_id(self) -> str:
        """Get this central ID"""
        return self.this_central.get("id", "central-1")

    def get_this_central_ip(self) -> str:
        """Get this central IP"""
        return self.this_central.get("ip", "127.0.0.1")

    def get_peer_centrals(self) -> List[Dict]:
        """Get list of peer centrals"""
        return self.peer_centrals

    def is_standalone(self) -> bool:
        """Check if running in standalone mode (no peers)"""
        return len(self.peer_centrals) == 0

    def save_config(self, config: Dict):
        """Save config to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            # Reload config
            self._load_config()
            return True

        except Exception as e:
            print(f"Error saving P2P config: {e}")
            return False

    def update_this_central(self, central_id: str, ip: str, api_port: int):
        """Update this central config"""
        config = {
            "this_central": {
                "id": central_id,
                "ip": ip,
                "api_port": api_port
            },
            "peer_centrals": self.peer_centrals
        }
        return self.save_config(config)

    def update_peers(self, peers: List[Dict]):
        """Update peer centrals config"""
        config = {
            "this_central": self.this_central,
            "peer_centrals": peers
        }
        return self.save_config(config)

    def to_dict(self) -> Dict:
        """Convert config to dictionary"""
        return {
            "this_central": self.this_central,
            "peer_centrals": self.peer_centrals
        }
