import sys, os
sys.path.append(os.getcwd())
from dotenv import load_dotenv
load_dotenv()
from src.tools.getKnowledgeContent import getKnowledgeContentTool

res = getKnowledgeContentTool(partner_name='Insper')
lines = res.splitlines()

in_section = False
for l in lines:
    if "10. PROCESSO DE " in l and "..." not in l:
        in_section = True
    if in_section:
        print(l)
    if in_section and l.startswith("11. "):
        break
