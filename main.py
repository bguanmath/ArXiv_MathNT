import sys
import time
import pytz
import os
from datetime import datetime

from utils import get_daily_papers, generate_table, back_up_files, restore_files, remove_backups, get_daily_date

beijing_timezone = pytz.timezone('Asia/Shanghai')
current_date = datetime.now(beijing_timezone).strftime("%Y-%m-%d")

# --- DYNAMIC CONFIGURATION FROM GITHUB ACTIONS VARIABLES ---
# Read environment variables set in the YAML file
keywords_str = os.environ.get('KEYWORDS', '')
categories_str = os.environ.get('CATEGORIES', 'math.NT,math.RT') # Default if not set

# Parse comma-separated strings into lists, removing any empty strings or whitespace
keywords = [k.strip() for k in keywords_str.split(',') if k.strip()]
default_categories = [c.strip() for c in categories_str.split(',') if c.strip()]

# --- STATIC CONFIGURATION ---
max_result = 100
issues_result = 15
# Define the new column order: Date first, and add Authors, ArXiv ID, Category.
# 'Link' is needed for generating the title's hyperlink.
column_names = ["Date", "Title", "Authors", "ArXiv ID", "Category", "Link", "Abstract", "Comment"]

# --- SETUP ---
back_up_files()

try:
    # --- WRITE README HEADER ---
    with open("README.md", "w") as f_rm:
        f_rm.write("# Daily Papers\n")
        f_rm.write("The project automatically fetches the latest papers from arXiv.\n\n")
        f_rm.write(f"Last update: {current_date}\n\n")

        # --- PREPARE NEW ISSUE FILE ---
        with open("new_issue_template.md", "w") as f_is:
            f_is.write("---\n")
            f_is.write(f"title: Latest Papers - {get_daily_date()}\n")
            f_is.write("labels: documentation\n")
            f_is.write("---\n")
            
            repo_name = os.environ.get("GITHUB_REPOSITORY")
            if repo_name:
                repo_url = f"https://github.com/{repo_name}"
                f_is.write(f"**Please check the [Github]({repo_url}) page for more information and more papers.**\n\n")

            # --- MAIN LOGIC ---
            if keywords:
                # --- A: Search by Keywords ---
                print(f"Searching by keywords: {keywords}")
                f_rm.write("The subheadings in the README file represent the search keywords.\n\n")
                for keyword in keywords:
                    f_rm.write(f"## {keyword}\n")
                    f_is.write(f"## {keyword}\n")
                    
                    papers = get_daily_papers(column_names, max_result, keyword=keyword)
                    if papers is None:
                        print(f"Failed to get papers for keyword: {keyword}!")
                        continue

                    rm_table = generate_table(papers)
                    is_table = generate_table(papers[:issues_result], ignore_keys=["Abstract"])
                    f_rm.write("\n\n---\n\n" + rm_table + "\n\n")
                    f_is.write(is_table + "\n\n")
                    time.sleep(5)
            elif default_categories:
                # --- B: Search by Categories ---
                print(f"Keywords list is empty. Searching by categories: {default_categories}")
                f_rm.write(f"Displaying the latest papers from categories: {', '.join(default_categories)}\n\n")
                f_is.write(f"## Latest papers from {', '.join(default_categories)}\n")
                
                papers = get_daily_papers(column_names, max_result, categories=default_categories)
                if papers is None:
                    print("Failed to get papers by category!")
                    sys.exit("Failed to get papers by category!")
                
                rm_table = generate_table(papers)
                is_table = generate_table(papers[:issues_result], ignore_keys=["Abstract"])
                f_rm.write("\n\n---\n\n" + rm_table + "\n\n")
                f_is.write(is_table + "\n\n")
            else:
                print("Both KEYWORDS and CATEGORIES are empty. Nothing to do.")


except Exception as e:
    print(f"An error occurred: {e}")
    restore_files() # Restore original files on error
    sys.exit(1)
finally:
    remove_backups() # Clean up backup files
