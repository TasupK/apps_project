import os
import shutil

src_file = "agents/web_research_agent.py"
dest_dir = "agents/web_research"

with open(src_file, "r", encoding="utf-8") as f:
    lines = f.readlines()

def get_lines(start, end):
    # lineno is 1-indexed
    return "".join(lines[start-1:end])

os.makedirs(dest_dir, exist_ok=True)

base_imports = "".join(lines[2:15]) + "\n"

# config.py (L22 - L166)
config_content = base_imports + get_lines(22, 166)
with open(os.path.join(dest_dir, "config.py"), "w", encoding="utf-8") as f:
    f.write(config_content)

# validator.py
validator_content = base_imports + "from .config import *\n\n" + \
    get_lines(169, 193) + "\n" + get_lines(1023, 1066)
with open(os.path.join(dest_dir, "validator.py"), "w", encoding="utf-8") as f:
    f.write(validator_content)

# search_engine.py
search_engine_content = base_imports + "from .config import *\n\n" + \
    get_lines(329, 529)
with open(os.path.join(dest_dir, "search_engine.py"), "w", encoding="utf-8") as f:
    f.write(search_engine_content)

# scraper.py
scraper_content = base_imports + "from .config import *\n\n" + \
    get_lines(532, 583) + "\n" + get_lines(964, 967)
with open(os.path.join(dest_dir, "scraper.py"), "w", encoding="utf-8") as f:
    f.write(scraper_content)

# llm_client.py
llm_client_content = base_imports + "from .config import *\n\n" + \
    get_lines(196, 326) + "\n" + get_lines(639, 697)
with open(os.path.join(dest_dir, "llm_client.py"), "w", encoding="utf-8") as f:
    f.write(llm_client_content)

# extractor.py
extractor_content = base_imports + "from .config import *\n" + \
    "from .llm_client import extract_candidate_details_with_llm\n" + \
    "from .scraper import fetch_page_text, _search_result_text\n\n" + \
    get_lines(586, 636) + "\n" + get_lines(700, 865) + "\n" + get_lines(948, 961) + "\n" + get_lines(970, 1020)
with open(os.path.join(dest_dir, "extractor.py"), "w", encoding="utf-8") as f:
    f.write(extractor_content)

# agent.py
agent_content = base_imports + "from .config import *\n" + \
    "from .validator import load_shortage_event, validate_candidate_results\n" + \
    "from .search_engine import collect_search_results, get_verified_search_results\n" + \
    "from .llm_client import generate_query_candidates\n" + \
    "from .extractor import _enrich_candidate_from_page\n\n" + \
    get_lines(868, 945) + "\n" + get_lines(1069, 1168)
with open(os.path.join(dest_dir, "agent.py"), "w", encoding="utf-8") as f:
    f.write(agent_content)

# __init__.py
with open(os.path.join(dest_dir, "__init__.py"), "w", encoding="utf-8") as f:
    f.write("from .agent import run_web_research\n")

print("Refactoring script generated files in", dest_dir)
