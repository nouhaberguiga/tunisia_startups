import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    )
}


async def fetch_page_text(url: str) -> str:
    """
    Télécharge une page et extrait le texte utile.
    """

    try:

        async with httpx.AsyncClient(
            headers=HEADERS,
            timeout=40,
            follow_redirects=True,
            verify=False
        ) as client:

            response = await client.get(url)

            if response.status_code != 200:
                print(
                    f"[HTTP ERROR] {response.status_code} : {url}"
                )
                return ""

            html = response.text

        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(
            [
                "script",
                "style",
                "footer",
                "nav",
                "header",
                "noscript"
            ]
        ):
            tag.decompose()

        texts = []

        for tag in soup.find_all(
            [
                "h1",
                "h2",
                "h3",
                "p",
                "li"
            ]
        ):

            text = tag.get_text(" ", strip=True)

            if 20 <= len(text) <= 500:
                texts.append(text)

        page_text = "\n".join(texts)

        print(
            f"[SCRAPED] {url} -> {len(page_text)} chars"
        )

        return page_text

    except Exception as e:

        print("[SCRAPER ERROR]")
        print(e)

        return ""