import unicodedata
import re
from typing import Optional

def clean_text(value: Optional[str], max_length: int) -> Optional[str]:
    if not value:
        return None
    
    value = value.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    
    chars = []
    for c in value:
        if unicodedata.category(c) not in ('Cc', 'Cf'):
            chars.append(c)
            
    cleaned = "".join(chars)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    if not cleaned:
        return None
        
    return cleaned[:max_length]
