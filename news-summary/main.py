from fastapi import FastAPI, HTTPException, Query
import requests
from bs4 import BeautifulSoup
import logging
import re
from gnewsclient import gnewsclient
import httpx
from PIL import Image, ImageDraw, ImageFont
from transformers import pipeline 

app = FastAPI()


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Replace with your actual Hugging Face API key
HUGGINGFACE_API_KEY = ""


@app.get("/")
def main():
    return {"message": "http://127.0.0.1:8000/docs "}


def fetch_news(url: str, max_chars: int = 1500):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Try to extract content from <article> tag, or fallback to <p> tags
        article_body = soup.find('article')
        if not article_body:
            article_body = soup.find('div', class_=['article-content', 'article-body', 'content-body']) or \
                soup.find('section', class_='main-content') or \
                soup.find('main')

        if not article_body:
            paragraphs = soup.find_all('p')
            content = ' '.join([p.get_text()
                               for p in paragraphs]).strip() if paragraphs else ''
        else:
            paragraphs = article_body.find_all('p')
            content = ' '.join([p.get_text() for p in paragraphs]).strip()

        # Further clean the content by removing excess whitespace and comments
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(
            r'(Comments|Topics mentioned in this article|Listen to the latest songs.*)', '', content)

        # Truncate content to the desired max length (e.g., 1500 characters)
        return content[:max_chars] if content else ""

    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        return ""

# Function to generate a catchy headline
def generate_headline(text: str):
    headers = {
        'Authorization': f'Bearer {HUGGINGFACE_API_KEY}',
    }
    # Updated prompt for more engaging headlines
    prompt = f"""
    Create a strong, attention-grabbing headline for the following news article. 
    Make sure the headline is short but conveys the most exciting or significant part of the story make sure don't take first line of article just grab the key point of article then generate a strong attention grabbing title.
    Here is the article: {text}
    """
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_length": 20,  # Explicit headline length limit for concise titles
            "min_length": 5,   # Ensure it's short and snappy
            "do_sample": False,
        },
    }

    try:
        modelUrl = " https://huggingface.co/google/flan-t5-large"
        model = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
        response = requests.post(model, headers=headers, json=payload)
        response.raise_for_status()  # Raise exception if the request was not successful
        return response.json()[0]['summary_text']
    except Exception as e:
        logger.error(f"Error generating headline: {e}")
        return "Error generating headline"
# Function to generate a 300-word summary with post-processing to remove repetition


# Load the summarization pipeline
summarizer = pipeline("summarization", model='facebook/bart-large-cnn')
def summarize_text(text: str):
    headers = {
        'Authorization': f'Bearer {HUGGINGFACE_API_KEY}',
    }
    prompt = f"""
    Please summarize the following article in 300 words or less. Focus on the key points, including important details such as major events, statistics, and quotes. Ensure that the summary is clear, informative, and avoids unnecessary repetition. 

    Additionally, please exclude any content related to advertisements or promotional material that may be present in the article.

    Article: {text}
    """
    # prompt = f"""
    # Summarize the following article in 300 words. Focus on key points, avoid repetition, and keep it informative and clear.
    
    # Article: {text}
    # """
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_length": 300,  # Explicit summary target length
            "min_length": 150,  # Ensure min < max
            "do_sample": False,
        },
    }

    try:
        modelUrl="https://huggingface.co/it5/it5-small-news-summarization"
        # modelUrl = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
        # modelUrl="'https://api-inference.huggingface.co/models/google/pegasus-cnn_dailymail"
        # response = requests.post(modelUrl, headers=headers, json=payload)
        # response.raise_for_status()  # Raise exception if the request was not successful
        # summary = response.json()[0]['summary_text']

        # Generate the summary using the pipeline
        summary_list = summarizer(text, max_length=100, min_length=30, do_sample=False)

        # Extract the summary text
        summary = summary_list[0]['summary_text']

        # Post-process the summary to remove repeated phrases
        # Remove duplicate words
        cleaned_summary = re.sub(r'\b(\w+)\s+\1\b', r'\1', summary)
        return cleaned_summary
    except Exception as e:
        logger.error(f"Error summarizing text: {e}")
        return "Error summarizing"


def create_image_card(title, summary, watermark, output_path):
    # Create a blank white image
    img = Image.new('RGB', (800, 400), color='white')
    
    # Initialize ImageDraw
    draw = ImageDraw.Draw(img)

    # Load fonts (You can adjust the paths to the .ttf files as needed)
    title_font = ImageFont.truetype("arial.ttf", 48)  # Large font for title
    summary_font = ImageFont.truetype("arial.ttf", 36)  # Slightly smaller font for summary
    watermark_font = ImageFont.truetype("arial.ttf", 24)  # Smaller font for watermark

    # Define text positions
    title_position = (50, 50)
    summary_position = (50, 120)
    watermark_position = (650, 360)  # Position for watermark

    # Add title and summary to the image
    draw.text(title_position, title, fill="black", font=title_font)
    draw.text(summary_position, summary, fill="black", font=summary_font)
    
    # Add watermark
    draw.text(watermark_position, watermark, fill="gray", font=watermark_font)

    # Save the image
    img.save(output_path)


# API route to get news summary and headline from URL
@app.get("/get_news_from_url")
async def get_news_from_url(url: str = Query(..., description="URL of the news article")):
    # Fetch and clean the news article content, truncating to max 1500 characters
    article = fetch_news(url, max_chars=1500)
    if not article:
        raise HTTPException(
            status_code=404, detail="No articles found or error fetching the URL.")

    # Clean the article text and remove unnecessary whitespace
    article = article.strip().replace("\n", " ").replace("\r", " ")

    # Generate a headline and summary
    headline = generate_headline(article)
    summary = summarize_text(article)

    # Return the generated headline and summary
    return {"news": {"title": headline, "summary": summary}}


# # weak version
# @app.get("/scrape-google-news")
# async def scrape_google_news(query: str = Query(..., description="Search term for Google News")):
#     headers = {
#         "User-Agent":
#         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36"
#     }
#     # Search Google News with the provided query
#     google_news_url = f"https://www.google.com/search?q={query}&gl=us&tbm=nws&num=100"

#     # Make a request to Google
#     response = requests.get(google_news_url, headers=headers)

#     if response.status_code != 200:
#         return {"error": "Failed to fetch news"}

#     # Parse the content
#     soup = BeautifulSoup(response.content, "html.parser")
#     news_results = []

#     # Use the same CSS selectors you provided to extract the data
#     for el in soup.select("div.SoaBEf"):
#         news_results.append({
#             "link": el.find("a")["href"],
#             "title": el.select_one("div.MBeuO").get_text() if el.select_one("div.MBeuO") else "No title available",
#             "snippet": el.select_one(".GI74Re").get_text() if el.select_one(".GI74Re") else "No snippet available",
#             "date": el.select_one(".LfVVr").get_text() if el.select_one(".LfVVr") else "No date available",
#             "source": el.select_one(".NUnG9d span").get_text() if el.select_one(".NUnG9d span") else "No source available"
#         })

#     return {"news": news_results}


def extract_article_content(url):
    headers = {
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36"
    }
    try:
        article_response = requests.get(url, headers=headers)
        if article_response.status_code != 200:
            return "Summary not available"

        # Parse the article page content
        article_soup = BeautifulSoup(article_response.content, "html.parser")

        # Extract the main content of the article (This might vary based on the news source)
        paragraphs = article_soup.find_all("p")
        # Get the first 5 paragraphs as a summary
        article_text = " ".join([p.get_text() for p in paragraphs[:5]])

        return article_text if article_text else "Summary not available"

    except Exception as e:
        return "Failed to fetch summary"


async def extract_article_content(url):
    headers = {
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36"
    }
    async with httpx.AsyncClient() as client:
        try:
            article_response = await client.get(url, headers=headers)
            if article_response.status_code != 200:
                return "Summary not available"
            
            # Parse the article page content
            article_soup = BeautifulSoup(article_response.content, "html.parser")
            
            # Extract the main content of the article (This might vary based on the news source)
            paragraphs = article_soup.find_all("p")
            article_text = " ".join([p.get_text() for p in paragraphs[:5]])  # Get the first 5 paragraphs as a summary
            
            return article_text if article_text else "Summary not available"
        
        except Exception as e:
            return "Failed to fetch summary"

@app.get("/scrape-google-news")
async def scrape_google_news(query: str = Query(..., description="Search term for Google News")):
    headers = {
        "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36"
    }
    google_news_url = f"https://www.google.com/search?q={query}&gl=us&tbm=nws&num=100"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(google_news_url, headers=headers)
        
        if response.status_code != 200:
            return {"error": "Failed to fetch news"}
        
        soup = BeautifulSoup(response.content, "html.parser")
        news_results = []

        #getting only 5 results
        for el in soup.select("div.SoaBEf"):
            if len(news_results) >= 5:
                break  # Stop fetching after 5 articles
            
            link = el.find("a")["href"]
            title = el.select_one("div.MBeuO").get_text() if el.select_one("div.MBeuO") else "No title available"
            snippet = el.select_one(".GI74Re").get_text() if el.select_one(".GI74Re") else "No snippet available"
            date = el.select_one(".LfVVr").get_text() if el.select_one(".LfVVr") else "No date available"
            source = el.select_one(".NUnG9d span").get_text() if el.select_one(".NUnG9d span") else "No source available"
            
            #summary from the article link
            summary = await extract_article_content(link)  # Await the summary extraction
            
            news_results.append({
                "link": link,
                "title": title,
                "snippet": snippet,
                "date": date,
                "source": source,
                "summary": summarize_text(summary)
            })

        return {"news": news_results}
    


# synchronouse requests
# @app.get("/scrape-google-news")
# async def scrape_google_news(query: str = Query(..., description="Search term for Google News")):
#     headers = {
#         "User-Agent":
#         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36"
#     }
#     google_news_url = f"https://www.google.com/search?q={query}&gl=us&tbm=nws&num=100"

#     response = requests.get(google_news_url, headers=headers)

#     if response.status_code != 200:
#         return {"error": "Failed to fetch news"}

#     soup = BeautifulSoup(response.content, "html.parser")
#     news_results = []

#     # Loop through the articles and stop when the array length reaches 5
#     for el in soup.select("div.SoaBEf"):
#         if len(news_results) >= 5:
#             break  # Stop fetching after 5 articles

#         link = el.find("a")["href"]
#         title = el.select_one("div.MBeuO").get_text() if el.select_one(
#             "div.MBeuO") else "No title available"
#         snippet = el.select_one(".GI74Re").get_text() if el.select_one(
#             ".GI74Re") else "No snippet available"
#         date = el.select_one(".LfVVr").get_text() if el.select_one(
#             ".LfVVr") else "No date available"
#         source = el.select_one(".NUnG9d span").get_text() if el.select_one(
#             ".NUnG9d span") else "No source available"

#         # Extract summary from the article link
#         summary = extract_article_content(link)

#         news_results.append({
#             "link": link,
#             "title": generate_headline(summary),
#             "snippet": snippet,
#             "date": date,
#             "source": source,
#             "summary": summarize_text(summary)
#         })

#     return {"news": news_results}






# @app.get("/scrape-google-news")
# async def scrape_google_news(query: str = Query(..., description="Search term for Google News")):
#     headers = {
#         "User-Agent":
#         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36"
#     }
#     google_news_url = f"https://www.google.com/search?q={query}&gl=us&tbm=nws&num=100"

#     response = requests.get(google_news_url, headers=headers)

#     if response.status_code != 200:
#         return {"error": "Failed to fetch news"}

#     soup = BeautifulSoup(response.content, "html.parser")
#     news_results = []

#     for el in soup.select("div.SoaBEf"):
#         link = el.find("a")["href"]
#         title = el.select_one("div.MBeuO").get_text() if el.select_one(
#             "div.MBeuO") else "No title available"
#         snippet = el.select_one(".GI74Re").get_text() if el.select_one(
#             ".GI74Re") else "No snippet available"
#         date = el.select_one(".LfVVr").get_text() if el.select_one(
#             ".LfVVr") else "No date available"
#         source = el.select_one(".NUnG9d span").get_text() if el.select_one(
#             ".NUnG9d span") else "No source available"

#         # Extract summary from the article link
#         summary = extract_article_content(link)

#         news_results.append({
#             "link": link,
#             "title": title,
#             "snippet": snippet,
#             "date": date,
#             "source": source,
#             "summary": summary  # Add the full summary here
#         })
# # Limit the final array to 5 items
#     limited_news_results = news_results[:5]

#     return {"news": limited_news_results}
#     # return {"news": news_results}


# gnews scrap
@app.get("/scrape-gnewsclient")
async def scrape_gnewsclient(topic: str = Query("Technology", description="News topic")):
    client = gnewsclient.NewsClient(
        language='english', location='United States', topic=topic)
    news_items = client.get_news()

    news = []
    for item in news_items:
        news.append({
            "title": item['title'],
            # Summary not available, so link provided instead
            "summary": item['link']
        })

    return {"news": news}
