import urllib.request
import urllib.parse
import os
import aiohttp
from bs4 import BeautifulSoup
from core.tool_registry import aria_tool

class SearchEngine:
    @aria_tool(name="web_search", description="Searches the web for a given query and returns titles, direct links, and snippets.")
    async def search(self, query: str) -> str:
        """Performs a web search using DuckDuckGo HTML Lite and returns parsed results."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        
        try:
            # Fetch asynchronously using aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=15) as response:
                    if response.status != 200:
                        return f"Search failed: DuckDuckGo returned status {response.status}"
                    html = await response.read()
            
            soup = BeautifulSoup(html, 'html.parser')
            results = []
            
            for div in soup.find_all('div', class_='result'):
                title_el = div.find('a', class_='result__a')
                snippet_el = div.find('a', class_='result__snippet')
                
                if title_el:
                    title = title_el.get_text(strip=True)
                    raw_link = title_el['href']
                    
                    # Resolve relative URLs
                    link = urllib.parse.urljoin("https://duckduckgo.com", raw_link)
                    
                    # Extract true destination from proxy redirects
                    parsed_url = urllib.parse.urlparse(link)
                    queries = urllib.parse.parse_qs(parsed_url.query)
                    if 'uddg' in queries:
                        link = queries['uddg'][0]
                            
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    results.append(f"Title: {title}\nLink: {link}\nDescription: {snippet}\n")
                    
            if not results:
                return f"No search results found for '{query}'."
                
            return "\n".join(results[:8])
            
        except Exception as e:
            return f"Search failed: {str(e)}"

    @aria_tool(name="web_fetch", description="Fetches and extracts clean readable text content from a URL.")
    async def web_fetch(self, url: str) -> str:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=15) as response:
                    if response.status != 200:
                        return f"Error: Received status code {response.status} from {url}"
                    html = await response.text(errors='ignore')
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script, style, navigation, footer, header, and form tags
            for element in soup(["script", "style", "nav", "footer", "header", "form"]):
                element.decompose()
                
            text = soup.get_text(separator='\n')
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = '\n'.join(chunk for chunk in chunks if chunk)
            
            if not clean_text:
                return "The page fetched successfully but contained no readable text content."
                
            if len(clean_text) > 8000:
                clean_text = clean_text[:8000] + "\n\n...[content truncated for size]..."
            return clean_text
            
        except Exception as e:
            return f"Failed to fetch content from {url}: {str(e)}"

    @aria_tool(name="read_pdf_document", description="Extracts readable text from a local PDF file.")
    async def read_pdf_document(self, filepath: str) -> str:
        if not os.path.exists(filepath):
            return f"Error: File not found at {filepath}"
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(filepath)
            text = []
            for i, page in enumerate(doc):
                page_text = page.get_text()
                text.append(f"--- Page {i+1} ---\n{page_text}")
            full_text = "\n".join(text)
            
            if len(full_text) > 10000:
                full_text = full_text[:10000] + "\n\n...[PDF content truncated due to length]..."
            return full_text
        except Exception as e:
            return f"Failed to read PDF: {str(e)}"

search_engine = SearchEngine()
