# prompts.py

from typing import List, Dict

def render_messages(roles: List[Dict], variables: Dict | None = None) -> List[Dict]:
    """
    roles: [{"role":"system","content":"... {tenant} ..."}, ...]
    variables: {"tenant":"Libra"}
    단순 치환만 담당(고급 템플릿/랭체인은 추후 model/langchain 쪽에서 확장)
    """
    variables = variables or {}
    messages = []
    for item in roles:
        role = item.get("role", "system")
        content = item.get("content", "")
        for k, v in variables.items():
            content = content.replace("{"+k+"}", str(v))
        messages.append({"role": role, "content": content})
    return messages
