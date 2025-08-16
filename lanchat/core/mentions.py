import re
from typing import List
MENTION_RE = re.compile(r'@([A-Za-z0-9_\-]{1,32})')
def extract_mentions(text: str) -> List[str]:
    return list(dict.fromkeys(MENTION_RE.findall(text)))
