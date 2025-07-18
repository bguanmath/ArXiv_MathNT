import os
import time
import pytz
import shutil
import datetime
from typing import List, Dict
import urllib, urllib.request

import feedparser
from easydict import EasyDict


def remove_duplicated_spaces(text: str) -> str:
    return " ".join(text.split())

def _request_arxiv_api(url: str) -> List[Dict[str, str]]:
    """A helper function to make a request to the arXiv API and parse the response."""
    response = urllib.request.urlopen(url).read().decode('utf-8')
    feed = feedparser.parse(response)

    papers = []
    for entry in feed.entries:
        entry = EasyDict(entry)
        paper = EasyDict()
        paper.Title = remove_duplicated_spaces(entry.title.replace("\n", " "))
        paper.Abstract = remove_duplicated_spaces(entry.summary.replace("\n", " "))
        paper.Authors = [remove_duplicated_spaces(_["name"].replace("\n", " ")) for _ in entry.authors]
        paper.Link = remove_duplicated_spaces(entry.link.replace("\n", " "))
        paper.Tags = [remove_duplicated_spaces(_["term"].replace("\n", " ")) for _ in entry.tags]
        paper.Comment = remove_duplicated_spaces(entry.get("arxiv_comment", "").replace("\n", " "))
        paper.Date = entry.updated
        papers.append(paper)
    return papers

def request_paper_with_arXiv_api(keyword: str, max_results: int, link: str = "OR") -> List[Dict[str, str]]:
    """Requests papers from arXiv based on a keyword search."""
    assert link in ["OR", "AND"], "link should be 'OR' or 'AND'"
    keyword_query = "\"" + keyword + "\""
    url = "http://export.arxiv.org/api/query?search_query=ti:{0}+{2}+abs:{0}&max_results={1}&sortBy=lastUpdatedDate".format(keyword_query, max_results, link)
    url = urllib.parse.quote(url, safe="%/:=&?~#+!$,;'@()*[]")
    return _request_arxiv_api(url)

def request_paper_by_category(categories: List[str], max_results: int) -> List[Dict[str, str]]:
    """Requests papers from arXiv based on categories."""
    category_query = "+OR+".join([f"cat:{cat}" for cat in categories])
    url = f"http://export.arxiv.org/api/query?search_query={category_query}&max_results={max_results}&sortBy=lastUpdatedDate"
    url = urllib.parse.quote(url, safe="%/:=&?~#+!$,;'@()*[]")
    return _request_arxiv_api(url)

def filter_tags(papers: List[Dict[str, str]], target_tags: List[str]=["math.NT", "math.RT"]) -> List[Dict[str, str]]:
    """Filters papers to keep only those matching the target tags."""
    if not target_tags: # If target_tags is empty, return all papers
        return papers
    results = []
    for paper in papers:
        tags = paper.Tags
        for tag in tags:
            if tag in target_tags:
                results.append(paper)
                break
    return results

def get_papers_with_retries(api_func, *args, retries: int = 6) -> List[Dict[str, str]]:
    """A generic wrapper to retry an API call function."""
    for _ in range(retries):
        papers = api_func(*args)
        if papers:
            return papers
        print("Unexpected empty list, retrying...")
        time.sleep(60 * 30)
    return None

def get_daily_papers(column_names: List[str], max_result: int, keyword: str = None, categories: List[str] = None) -> List[Dict[str, str]]:
    """Fetches and filters daily papers either by keyword or by category."""
    if keyword:
        if len(keyword.split()) == 1: link = "AND"
        else: link = "OR"
        papers = get_papers_with_retries(request_paper_with_arXiv_api, keyword, max_result, link)
    elif categories:
        papers = get_papers_with_retries(request_paper_by_category, categories, max_result)
    else:
        return [] # Return empty list if no keyword or category is provided

    if not papers:
        return None

    # When searching by keyword, we still want to filter by specific tags if needed.
    # When searching by category, we've already gotten what we want, so no extra filtering is needed here.
    if keyword:
         papers = filter_tags(papers, target_tags=["math.NT", "math.RT"])

    papers = [{column_name: paper[column_name] for column_name in column_names} for paper in papers]
    return papers

def generate_table(papers: List[Dict[str, str]], ignore_keys: List[str] = []) -> str:
    if not papers:
        return "No new papers found today."
        
    formatted_papers = []
    keys = papers[0].keys()
    for paper in papers:
        formatted_paper = EasyDict()
        formatted_paper.Title = "**" + "[{0}]({1})".format(paper["Title"], paper["Link"]) + "**"
        formatted_paper.Date = paper["Date"].split("T")[0]
        
        for key in keys:
            if key in ["Title", "Link", "Date"] or key in ignore_keys:
                continue
            elif key == "Abstract":
                formatted_paper[key] = "<details><summary>Show</summary><p>{0}</p></details>".format(paper[key])
            elif key == "Authors":
                formatted_paper[key] = paper[key][0] + " et al." if len(paper[key]) > 1 else paper[key][0]
            elif key == "Tags":
                tags = ", ".join(paper[key])
                if len(tags) > 10:
                    formatted_paper[key] = "<details><summary>{0}...</summary><p>{1}</p></details>".format(tags[:5], tags)
                else:
                    formatted_paper[key] = tags
            elif key == "Comment":
                if paper[key] == "":
                    formatted_paper[key] = ""
                elif len(paper[key]) > 20:
                    formatted_paper[key] = "<details><summary>{0}...</summary><p>{1}</p></details>".format(paper[key][:5], paper[key])
                else:
                    formatted_paper[key] = paper[key]
        formatted_papers.append(formatted_paper)

    columns = formatted_papers[0].keys()
    header = "| " + " | ".join(["**" + column + "**" for column in columns]) + " |"
    header += "\n| " + " | ".join(["---"] * len(columns)) + " |"
    
    body = ""
    for paper in formatted_papers:
        body += "\n| " + " | ".join(paper.values()) + " |"
    return header + body

def back_up_files():
    if os.path.exists("README.md"):
        shutil.move("README.md", "README.md.bk")
    if os.path.exists(".github/ISSUE_TEMPLATE.md"):
        shutil.move(".github/ISSUE_TEMPLATE.md", ".github/ISSUE_TEMPLATE.md.bk")

def restore_files():
    if os.path.exists("README.md.bk"):
        shutil.move("README.md.bk", "README.md")
    if os.path.exists(".github/ISSUE_TEMPLATE.md.bk"):
        shutil.move(".github/ISSUE_TEMPLATE.md.bk", ".github/ISSUE_TEMPLATE.md")

def remove_backups():
    if os.path.exists("README.md.bk"):
        os.remove("README.md.bk")
    if os.path.exists(".github/ISSUE_TEMPLATE.md.bk"):
        os.remove(".github/ISSUE_TEMPLATE.md.bk")

def get_daily_date():
    beijing_timezone = pytz.timezone('Asia/Shanghai')
    today = datetime.datetime.now(beijing_timezone)
    return today.strftime("%B %d, %Y")
