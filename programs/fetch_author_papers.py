import requests
import time
import csv

API_KEY = ''

HEADERS = {
    'x-api-key': API_KEY
}

def safe_request(url, params, max_retries=3, backoff_factor=5):
    for attempt in range(max_retries):
        response = requests.get(url, headers=HEADERS, params=params)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            wait_time = backoff_factor * (attempt + 1)
            print(f"Rate limit hit (429). Waiting {wait_time} seconds before retrying...")
            time.sleep(wait_time)
        else:
            response.raise_for_status()
    raise Exception(f"Failed after {max_retries} retries: {url}")

def get_author_name(author_id):
    url = f"https://api.semanticscholar.org/graph/v1/author/{author_id}"
    data = safe_request(url, {"fields": "name"})
    time.sleep(1.5)
    return data.get("name", "")

def get_papers_by_author(author_id):
    url = f"https://api.semanticscholar.org/graph/v1/author/{author_id}/papers"
    data = safe_request(url, {"fields": "paperId,title,fieldsOfStudy"})
    time.sleep(1.5)
    return data.get("data", [])

def main(author_ids):
    results = []
    paper_ids = []

    for author_id in author_ids:
        try:
            print(f"\nFetching data for author ID: {author_id}")
            author_name = get_author_name(author_id)
            print(f"Author name: {author_name}")
            papers = get_papers_by_author(author_id)

            for paper in papers:
                paper_id = paper.get("paperId")
                if paper_id:
                    results.append({
                        "authorId": author_id,
                        "authorName": author_name,
                        "paperId": paper_id,
                        "title": paper.get("title"),
                        "fieldsOfStudy": paper.get("fieldsOfStudy", [])
                    })
                    paper_ids.append(paper_id)

        except Exception as e:
            print(f"Error fetching data for {author_id}: {e}")

    return results, paper_ids

if __name__ == "__main__":
    author_ids = [
        "", "", "", "",
        "", "", "", ""
    ]

    data, paper_ids = main(author_ids)

    with open("papers_by_authors.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["authorId", "authorName", "paperId", "title", "fieldsOfStudy"])
        writer.writeheader()
        for row in data:
            writer.writerow(row)
    print("\nDetailed data saved to papers_by_authors.csv")

    with open("paper_ids.txt", "w", encoding="utf-8") as f:
        f.write(" ".join(paper_ids))
    print("Paper IDs saved to paper_ids.txt")
