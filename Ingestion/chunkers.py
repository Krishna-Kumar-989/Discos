import hashlib
import logging
from typing import List, Dict, Any

from config import AppConfig

logger = logging.getLogger("ingestion.chunkers")

class SlidingWindowChunker:
    """Chunks lists of Discord messages using a message-aligned sliding window."""
    
    def __init__(self, config: AppConfig):
        self.config = config.chunking

    def format_message(self, msg: Dict[str, Any]) -> str:
        """Format a single message into a clean string for embeddings."""
        author = msg.get("author", {}).get("display_name") or msg.get("author", {}).get("name", "Unknown")
        timestamp = msg.get("timestamp", "")
        content = (msg.get("content") or "").strip()
        
        # Format replies cleanly
        reply_info = ""
        if msg.get("reply_to"):
            reply_info = f"[Replying to Message ID {msg['reply_to']}] "
            
        # Format attachments
        attachments_info = ""
        attachments = msg.get("attachments", [])
        if attachments:
            att_names = ", ".join([a.get("filename", "") for a in attachments if a.get("filename")])
            if att_names:
                attachments_info = f" [Attachments: {att_names}]"
                
        # Format reactions
        reactions_info = ""
        reactions = msg.get("reactions", [])
        if reactions:
            react_list = [f"{r.get('emoji')}(x{r.get('count')})" for r in reactions if r.get("emoji")]
            if react_list:
                reactions_info = f" [Reactions: {', '.join(react_list)}]"

        return f"[{timestamp}] {author}: {reply_info}{content}{attachments_info}{reactions_info}".strip()

    def chunk_messages(self, data: Dict[str, Any], source_file: str) -> List[Dict[str, Any]]:
        """
        Group chronologically sorted messages into overlapping chunks based on character count.
        Returns a list of chunks, each with 'text' and 'metadata'.
        """
        guild = data.get("guild", "Unknown Server")
        channel = data.get("channel", "Unknown Channel")
        channel_id = data.get("channel_id", "")
        messages = data.get("messages", [])
        
        if not messages:
            return []

        # Sort messages by timestamp just in case
        try:
            sorted_messages = sorted(messages, key=lambda x: x.get("timestamp", ""))
        except Exception:
            sorted_messages = messages

        # Pre-format messages and compute lengths
        formatted_messages = []
        for msg in sorted_messages:
            formatted_text = self.format_message(msg)
            formatted_messages.append({
                "raw": msg,
                "text": formatted_text,
                "length": len(formatted_text)
            })

        chunks = []
        i = 0
        n = len(formatted_messages)
        chunk_idx = 0

        while i < n:
            current_chunk_msgs = []
            current_length = 0
            
            #Build the chunk 
            j = i
            while j < n:
                msg_len = formatted_messages[j]["length"]
            
                if current_length + msg_len + (1 if current_length > 0 else 0) <= self.config.chunk_size or j == i:
                    current_chunk_msgs.append(formatted_messages[j])
                    current_length += msg_len + (1 if current_length > 0 else 0)
                    j += 1
                else:
                    break
            
            end_index = j - 1
            chunk_text = "\n".join([m["text"] for m in current_chunk_msgs])
            
            #Skip chunk if shorter
            if len(chunk_text) >= self.config.min_chunk_length:
                # Compile metadata
                msg_ids = [m["raw"].get("id") for m in current_chunk_msgs if m["raw"].get("id")]
                
                #Extract authors
                authors = set()
                for m in current_chunk_msgs:
                    author_name = m["raw"].get("author", {}).get("display_name") or m["raw"].get("author", {}).get("name")
                    if author_name:
                        authors.add(author_name)
                
                start_ts = current_chunk_msgs[0]["raw"].get("timestamp", "")
                end_ts = current_chunk_msgs[-1]["raw"].get("timestamp", "")
                
                #Generate a unique chunk ID using source info and chunk index
                hash_input = f"{channel_id}_{source_file}_{chunk_idx}_{chunk_text}"
                chunk_id = hashlib.md5(hash_input.encode("utf-8")).hexdigest()

                chunks.append({
                    "id": chunk_id,
                    "text": chunk_text,
                    "metadata": {
                        "server": guild,
                        "channel": channel,
                        "channel_id": channel_id,
                        "start_timestamp": start_ts,
                        "end_timestamp": end_ts,
                        "message_ids": msg_ids,
                        "authors": list(authors),
                        "source_file": source_file,
                        "chunk_index": chunk_idx
                    }
                })
                chunk_idx += 1

           
            if end_index >= n - 1:
                break

            #Calculate start index for next chunk based on overlap
            # Scan backward from end_index to find the overlap start
            overlap_length = 0
            next_i = end_index
            while next_i > i:
                msg_len = formatted_messages[next_i]["length"]
                if overlap_length + msg_len + (1 if overlap_length > 0 else 0) <= self.config.overlap:
                    overlap_length += msg_len + (1 if overlap_length > 0 else 0)
                    next_i -= 1
                else:
                    break
            
            #prevent infinite loop if  didn't advance
            if next_i <= i:
                next_i = i + 1
                
            i = next_i

        return chunks
