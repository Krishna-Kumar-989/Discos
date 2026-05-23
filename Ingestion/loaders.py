import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from config import AppConfig
from objectStore import get_object_store

logger = logging.getLogger("ingestion.loaders")

class DiscordDataLoader:
    """Handles discovery and reading of scraped Discord data from the object store."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.store = get_object_store()

    def get_available_servers(self) -> List[str]:
        """Scan the object store and return all detected server IDs (folder names)."""
        objects = self.store.list_objects(prefix="discord_exports/")
        servers = set()
        for obj in objects:
            parts = obj.split('/')
            if len(parts) >= 3 and parts[0] == "discord_exports":
                servers.add(parts[1])
        return sorted(list(servers))

    def get_server_files(self, server_id: str) -> List[str]:
        """Get all supported export objects for a specific server ID."""
        files = []
        prefix = f"discord_exports/{server_id}/"
        objects = self.store.list_objects(prefix=prefix)
        
        for obj in objects:
            for ext in self.config.supported_extensions:
                if obj.endswith(ext):
                    files.append(obj)
                    break
        return sorted(files)

    def load_file_content(self, object_name: str) -> Dict[str, Any]:
        """Load and parse the JSON content of an object from the store."""
        try:
            raw_bytes = self.store.read_object(object_name)
            return json.loads(raw_bytes.decode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to read/parse JSON object {object_name}: {e}")
            raise

    def get_server_name(self, server_id: str) -> str:
        """Find the human-readable server name by inspecting the first JSON object in the server prefix."""
        files = self.get_server_files(server_id)
        if not files:
            return "Unknown Server"
            
        for obj_name in files:
            try:
                data = self.load_file_content(obj_name)
                guild = data.get("guild")
                if guild:
                    return guild
            except Exception:
                pass
        return "Unknown Server"

    def resolve_server_id(self, server_name_or_id: str) -> str:
        """Resolve a server name or ID string to the actual server folder name (guild ID)."""
        available_ids = self.get_available_servers()
        
      
        if server_name_or_id in available_ids:
            return server_name_or_id
            
        # Search by guild name
        for s_id in available_ids:
            name = self.get_server_name(s_id)
            if name.lower() == server_name_or_id.lower():
                return s_id
                
        return None

