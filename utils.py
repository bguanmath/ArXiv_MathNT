import os
import time
import pytz
import shutil
import datetime
from typing import List, Dict
import urllib, urllib.request
import re

import feedparser
from easydict import EasyDict

def remove_duplicated_spaces(text: str) -> str:
    return " ".join(text.split())

def _request_arxiv_api(url: str) -> List[Dict[str, str]]:
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
        
        # --- 数据提取 ---
        # 提取 ArXiv ID (从链接中)
        match = re.search(r'/abs/([^v]+)', paper.Link)
        paper['ArXiv ID'] = match.group(1) if match else 'N/A'
        # 提取主要分类 (Primary Category)
        paper['Category'] = entry.get('arxiv_primary_category', {}).get('term', 'N/A')
        
        papers.append(paper)
    return papers

def request_paper_with_arXiv_api(keyword: str, max_results: int, link: str = "OR") -> List[Dict[str, str]]:
    assert link in ["OR", "AND"], "link should be 'OR' or 'AND'"
    keyword_query = "\"" + keyword + "\""
    url = f"http://export.arxiv.org/api/query?search_query=ti:{keyword_query}+{link}+abs:{keyword_query}&max_results={max_results}&sortBy=lastUpdatedDate"
    url = urllib.parse.quote(url, safe="%/:=&?~#+!$,;'@()*[]")
    return _request_arxiv_api(url)

def request_paper_by_category(categories: List[str], max_results: int) -> List[Dict[str, str]]:
    category_query = "+OR+".join([f"cat:{cat}" for cat in categories])
    url = f"http://export.arxiv.org/api/query?search_query={category_query}&max_results={max_results}&sortBy=lastUpdatedDate"
    url = urllib.parse.quote(url, safe="%/:=&?~#+!$,;'@()*[]")
    return _request_arxiv_api(url)

def get_papers_with_retries(api_func, *args, retries: int = 6) -> List[Dict[str, str]]:
    for _ in range(retries):
        papers = api_func(*args)
        if papers:
            return papers
        print("Unexpected empty list, retrying...")
        time.sleep(60 * 30)
    return None

def get_daily_papers(column_names: List[str], max_result: int, keyword: str = None, categories: List[str] = None) -> List[Dict[str, str]]:
    papers_raw = []
    if keyword:
        if len(keyword.split()) == 1: link = "AND"
        else: link = "OR"
        papers_raw = get_papers_with_retries(request_paper_with_arXiv_api, keyword, max_result, link)
    elif categories:
        papers_raw = get_papers_with_retries(request_paper_by_category, categories, max_result)
    
    if not papers_raw:
        return None

    # **【错误修复】** 使用 .get() 来安全地创建字典，防止因缺少键而崩溃
    papers_processed = []
    for paper in papers_raw:
        processed_paper = {col: paper.get(col, '') for col in column_names}
        papers_processed.append(processed_paper)
        
    return papers_processed


def generate_table(papers: List[Dict[str, str]], ignore_keys: List[str] = []) -> str:
    if not papers:
        return "No new papers found today."

    # 1. 定义表格中要显示的列（第一行）
    display_keys = ["Date", "Title", "Authors", "Category", "ArXiv ID"]
    num_columns = len(display_keys)
    
    # 2. 生成表格的标题栏
    header = "| " + " | ".join([f"**{key}**" for key in display_keys]) + " |"
    header_separator = "| " + " | ".join(["---"] * num_columns) + " |"
    
    # 3. 遍历每篇论文，为每篇生成两行
    table_rows = []
    for paper in papers:
        # --- 生成第一行：主要信息 ---
        first_row_values = []
        for key in display_keys:
            value = paper.get(key, "")
            value_str = str(value).replace('|', r'\|') # 转义 '|'
            
            if key == "Title":
                link = paper.get("Link", "#")
                formatted_value = f"**<a href='{link}'>{value_str}</a>**"
            elif key == "Date":
                formatted_value = value_str.split("T")[0]
            elif key == "Authors":
                if isinstance(value, list):
                    formatted_value = ", ".join(value).replace('|', r'\|')
                else:
                    formatted_value = value_str
            else:
                formatted_value = value_str
            
            first_row_values.append(formatted_value)
        
        table_rows.append("| " + " | ".join(first_row_values) + " |")

        # --- 生成第二行：评论和摘要 ---
        details_parts = []
        
        # 先处理 Comment
        if 'Comment' not in ignore_keys and paper.get('Comment'):
            # 使用 blockquote 样式，并处理换行
            comment_text = f"<blockquote>{paper.get('Comment', '')}</blockquote>"
            details_parts.append(comment_text)
            
        # 再处理 Abstract
        if 'Abstract' not in ignore_keys and paper.get('Abstract'):
            abstract_text = paper.get('Abstract', '')
            processed_abstract = re.sub(r'\\\[(.*?)\\\]', r'$$\1$$', abstract_text, flags=re.DOTALL)
            abstract_html = f"<details><summary>Abstract</summary><p>{processed_abstract}</p></details>"
            details_parts.append(abstract_html)
        
        # 如果有评论或摘要，则创建第二行
        if details_parts:
            # 将评论和摘要合并到一个单元格中，用 <br> 分隔
            combined_details = "<br>".join(details_parts)
            # 其他单元格留空，实现“跨列”的视觉效果
            second_row_values = [combined_details] + [""] * (num_columns - 1)
            table_rows.append("| " + " | ".join(second_row_values) + " |")

    # 4. 将标题栏和所有论文行组合成一个完整的表格字符串
    return header + "\n" + header_separator + "\n" + "\n".join(table_rows)


def back_up_files():
    if os.path.exists("README.md"):
        shutil.move("README.md", "README.md.bk")
    if os.path.exists("new_issue_template.md"): # 确保备份正确的文件
        shutil.move("new_issue_template.md", "new_issue_template.md.bk")

def restore_files():
    if os.path.exists("README.md.bk"):
        shutil.move("README.md.bk", "README.md")
    if os.path.exists("new_issue_template.md.bk"):
        shutil.move("new_issue_template.md.bk", "new_issue_template.md")

def remove_backups():
    if os.path.exists("README.md.bk"):
        os.remove("README.md.bk")
    if os.path.exists("new_issue_template.md.bk"):
        os.remove("new_issue_template.md.bk")

def get_daily_date():
    beijing_timezone = pytz.timezone('Asia/Shanghai')
    today = datetime.datetime.now(beijing_timezone)
    return today.strftime("%B %d, %Y")
