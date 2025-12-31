from datetime import datetime
from workflows.web_researcher import WebSearcherWorkflow, WebSearchQuery

# Load the default configuration file and start the workflow using the one-parameter API.
pipe = WebSearcherWorkflow("workflows/configs/web_searcher.yaml")

current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
query = WebSearchQuery(
    # prompt=f"Current time: {current_time}. Find the outstanding papers of ACL 2025, extract their title, author list, keywords, abstract, url in one sentence."
    prompt=f"Current time: {current_time}. Check website https://www.sqlite.org/cli.html and list some features, for each features, ."
)

pipe.run_sync(query)
